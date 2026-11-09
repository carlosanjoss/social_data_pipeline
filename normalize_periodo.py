"""
Radar Ódio — normalização por período para uma tabela dedicada.

Lê `posts` e `comments` do PostgreSQL cujo `collected_at` cai no período
configurado e grava uma **nova tabela** com o texto bruto preservado e o texto
normalizado/anonimizado conforme o pré-processamento do Radar Ódio v0.1
(`services/text_normalization.normalize_document`).

COMO USAR
---------
1. Ajuste o período no bloco CONFIGURAÇÃO abaixo (ou passe --inicio/--fim).
2. Rode:

       .venv311\\Scripts\\python.exe normalize_periodo.py

   Opcional: recorte por rede social

       .venv311\\Scripts\\python.exe normalize_periodo.py --plataformas youtube twitter

O script é idempotente (`ON CONFLICT (kind, source_id) DO UPDATE`): reexecutar
com o mesmo período não duplica; ampliar o período adiciona os novos registros.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime, time as dtime, timezone
from zoneinfo import ZoneInfo

import psycopg

from config import settings, setup_logging, get_logger
from database.postgres import get_conn, close_conn
from services.text_normalization import normalize_document

logger = get_logger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURAÇÃO — altere apenas isto quando quiser normalizar outro período
# ══════════════════════════════════════════════════════════════════════════════

PERIODO_INICIO = "2026-09-30"   # data inicial (inclusiva), formato AAAA-MM-DD
PERIODO_FIM    = "2026-10-06"   # data final EXCLUSIVA: inclui todo o dia 05/10
FUSO_HORARIO   = "UTC"          # "UTC" ou "America/Sao_Paulo"

# Qual data define o período:
#   "published_at" → data do CONTEÚDO (quando foi publicado)
#   "collected_at" → data da COLETA (quando o scraper capturou)
COLUNA_PERIODO = "published_at"

TABELA_DESTINO = "periodo_eleicoes_1_turno"

# True  = a tabela reflete exatamente o período configurado: faz upsert dos
#         registros do período e REMOVE os que ficaram de fora. Preserva os IDs
#         das linhas que permanecem, então resultados a jusante (ex.: a tabela
#         periodo_eleicoes_1_turno_bert) sobrevivem para essas linhas.
# False = apenas faz upsert do período, sem remover nada (acumula).
MANTER_APENAS_O_PERIODO = True

# ══════════════════════════════════════════════════════════════════════════════

COLUNAS_PERIODO_VALIDAS = ("published_at", "collected_at")

TAMANHO_LOTE = 2_000

_NOME_VALIDO = re.compile(r"^[a-z_][a-z0-9_]*$")

_COLUNAS = [
    "kind", "source_id", "platform", "content_type", "external_id",
    "post_external_id", "parent_external_id", "author", "title", "url",
    "language", "is_anchor", "published_at", "collected_at",
    "text_raw", "text_normalized",
]


def _ddl(tabela: str) -> str:
    return f"""
    CREATE TABLE IF NOT EXISTS {tabela} (
        id                 BIGSERIAL PRIMARY KEY,
        kind               TEXT        NOT NULL CHECK (kind IN ('post', 'comment')),
        source_id          INTEGER     NOT NULL,
        platform           TEXT        NOT NULL,
        content_type       TEXT,
        external_id        TEXT,
        post_external_id   TEXT,
        parent_external_id TEXT,
        author             TEXT,
        title              TEXT,
        url                TEXT,
        language           TEXT,
        is_anchor          BOOLEAN     NOT NULL DEFAULT FALSE,
        published_at       TIMESTAMPTZ,
        collected_at       TIMESTAMPTZ,
        text_raw           TEXT,
        text_normalized    TEXT,
        normalized_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_{tabela}_kind_source UNIQUE (kind, source_id)
    );
    CREATE INDEX IF NOT EXISTS idx_{tabela}_platform     ON {tabela} (platform);
    CREATE INDEX IF NOT EXISTS idx_{tabela}_collected_at ON {tabela} (collected_at);
    CREATE INDEX IF NOT EXISTS idx_{tabela}_published_at ON {tabela} (published_at);
    """


_SQL_POSTS = """
    SELECT id, platform, content_type, external_id,
           NULL::text AS post_external_id,
           NULL::text AS parent_external_id, author, title, url, language,
           is_anchor, published_at, collected_at, text
    FROM posts
    WHERE {coluna} >= %(ini)s AND {coluna} < %(fim)s
      {filtro}
    ORDER BY id
"""

_SQL_COMMENTS = """
    SELECT id, platform, content_type, external_id, post_external_id,
           parent_external_id, author, NULL::text AS title, NULL::text AS url,
           language, FALSE AS is_anchor, published_at, collected_at, text
    FROM comments
    WHERE {coluna} >= %(ini)s AND {coluna} < %(fim)s
      {filtro}
    ORDER BY id
"""


def _limites(inicio: str, fim: str, fuso: str) -> tuple[datetime, datetime]:
    tz = timezone.utc if fuso.upper() == "UTC" else ZoneInfo(fuso)
    d0 = datetime.combine(datetime.fromisoformat(inicio).date(), dtime.min, tzinfo=tz)
    d1 = datetime.combine(datetime.fromisoformat(fim).date(), dtime.min, tzinfo=tz)
    if d1 <= d0:
        raise SystemExit("PERIODO_FIM deve ser posterior a PERIODO_INICIO.")
    return d0, d1


class Auditoria:
    """Contadores para a validação final."""

    def __init__(self) -> None:
        self.lidos = 0
        self.gravados = 0
        self.textos_vazios = 0
        self.cr_restante = 0
        self.tab_restante = 0
        self.espaco_duplo = 0
        self.emoji_antes = 0
        self.emoji_depois = 0
        self.emoji_no_removido = 0
        self.hashtag_antes = 0
        self.hashtag_depois = 0
        self.hashtag_no_removido = 0
        self.urld = self.emaild = self.cpfd = self.phoned = self.userd = 0

    def acumula(
        self,
        bruto: str | None,
        saida: str | None,
        removidos: list[str] | None = None,
    ) -> None:
        self.lidos += 1
        if (bruto or "").strip() and not (saida or "").strip():
            self.textos_vazios += 1
        if saida is None:
            return
        if "\r" in saida:
            self.cr_restante += 1
        if "\t" in saida:
            self.tab_restante += 1
        if "  " in saida:
            self.espaco_duplo += 1

        self.emoji_antes += _conta_emoji(bruto or "")
        self.emoji_depois += _conta_emoji(saida)
        self.hashtag_antes += (bruto or "").count("#")
        self.hashtag_depois += saida.count("#")

        # Emoji/hashtag dentro de um trecho anonimizado (URL, e-mail, menção…)
        # desaparece junto com ele — é perda esperada, não remoção indevida.
        removido = "".join(removidos or [])
        self.emoji_no_removido += _conta_emoji(removido)
        self.hashtag_no_removido += removido.count("#")

        self.urld += saida.count("<URL>")
        self.emaild += saida.count("<EMAIL>")
        self.cpfd += saida.count("<ID>")
        self.phoned += saida.count("<PHONE>")
        self.userd += saida.count("<USER>")


def _conta_emoji(texto: str) -> int:
    total = 0
    for ch in texto:
        cp = ord(ch)
        if (0x1F000 <= cp <= 0x1FAFF) or (0x2600 <= cp <= 0x27BF) or cp in (0x2764, 0xFE0F):
            total += 1
    return total


def _processa(
    origem: psycopg.Connection,
    destino: psycopg.Connection,
    tabela: str,
    kind: str,
    sql: str,
    params: dict,
    audit: Auditoria,
) -> int:
    inseridos = 0
    cols = ", ".join(_COLUNAS)
    placeholders = ", ".join(f"%({c})s" for c in _COLUNAS)
    update = ", ".join(
        f"{c} = EXCLUDED.{c}" for c in _COLUNAS if c not in ("kind", "source_id")
    )
    upsert = (
        f"INSERT INTO {tabela} ({cols}, normalized_at) "
        f"VALUES ({placeholders}, NOW()) "
        f"ON CONFLICT (kind, source_id) DO UPDATE SET {update}, normalized_at = NOW()"
    )

    # Cursor server-side para não carregar milhões de linhas na memória.
    with origem.cursor(name=f"src_{kind}") as cur:
        cur.itersize = TAMANHO_LOTE
        cur.execute(sql, params)

        lote: list[dict] = []
        for (sid, platform, content_type, external_id, post_ext, parent_ext,
             author, title, url, language, is_anchor, published, collected, text) in cur:

            removidos: list[str] = []
            saida = normalize_document(text, removidos)
            audit.acumula(text, saida, removidos)

            lote.append({
                "kind": kind,
                "source_id": sid,
                "platform": platform,
                "content_type": content_type,
                "external_id": external_id,
                "post_external_id": post_ext,
                "parent_external_id": parent_ext,
                "author": author,
                "title": title,
                "url": url,
                "language": language,
                "is_anchor": is_anchor,
                "published_at": published,
                "collected_at": collected,
                "text_raw": text,
                "text_normalized": saida,
            })

            if len(lote) >= TAMANHO_LOTE:
                with destino.cursor() as w:
                    w.executemany(upsert, lote)
                destino.commit()
                inseridos += len(lote)
                lote.clear()
                print(f"    {kind}: {inseridos:,} registros...", flush=True)

        if lote:
            with destino.cursor() as w:
                w.executemany(upsert, lote)
            destino.commit()
            inseridos += len(lote)

    audit.gravados += inseridos
    return inseridos


def _descarta_fora_do_periodo(
    conn: psycopg.Connection,
    tabela: str,
    coluna: str,
    ini,
    fim,
    plataformas: list[str] | None = None,
) -> int:
    """Remove da tabela o que não pertence ao período configurado.

    Preserva os IDs das linhas que permanecem (ao contrário de TRUNCATE), para
    não invalidar resultados a jusante que referenciam `id`.
    """
    condicao = f"{coluna} < %(ini)s OR {coluna} >= %(fim)s OR {coluna} IS NULL"
    params: dict = {"ini": ini, "fim": fim}
    if plataformas:
        condicao += " OR platform <> ALL(%(plataformas)s)"
        params["plataformas"] = plataformas

    with conn.cursor() as cur:
        cur.execute(f"DELETE FROM {tabela} WHERE {condicao}", params)
        removidos = cur.rowcount
    conn.commit()
    return removidos


def _valida_destino(conn: psycopg.Connection, tabela: str, coluna: str, ini, fim) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                count(*),
                count(*) FILTER (WHERE text_raw <> '' AND coalesce(text_normalized,'') = ''),
                count(*) FILTER (WHERE strpos(text_normalized, chr(13)) > 0),
                count(*) FILTER (WHERE strpos(text_normalized, chr(9)) > 0),
                count(*) FILTER (WHERE strpos(text_normalized, '  ') > 0)
            FROM {tabela}
            WHERE {coluna} >= %s AND {coluna} < %s
            """,
            (ini, fim),
        )
        total, vazios, cr, tab, esp = cur.fetchone()
    return {"total": total, "vazios": vazios, "cr": cr, "tab": tab, "espaco_duplo": esp}


def main(argv: list[str] | None = None) -> int:
    setup_logging()

    parser = argparse.ArgumentParser(description="Normaliza um período para tabela dedicada")
    parser.add_argument("--inicio", default=PERIODO_INICIO, help="AAAA-MM-DD (inclusivo)")
    parser.add_argument("--fim", default=PERIODO_FIM, help="AAAA-MM-DD (exclusivo)")
    parser.add_argument("--fuso", default=FUSO_HORARIO)
    parser.add_argument("--tabela", default=TABELA_DESTINO)
    parser.add_argument("--plataformas", nargs="+", help="Recorte por rede social")
    parser.add_argument(
        "--coluna-periodo", default=COLUNA_PERIODO,
        choices=list(COLUNAS_PERIODO_VALIDAS),
        help="Data que define o período (padrão: %(default)s)",
    )
    parser.add_argument(
        "--acumular", action="store_true",
        help="Não trunca a tabela antes (padrão: recarrega o período do zero)",
    )
    args = parser.parse_args(argv)

    tabela = args.tabela
    if not _NOME_VALIDO.match(tabela):
        raise SystemExit(f"Nome de tabela inválido: {tabela!r}")

    coluna = args.coluna_periodo
    if coluna not in COLUNAS_PERIODO_VALIDAS:
        raise SystemExit(f"Coluna de período inválida: {coluna!r}")

    sincronizar = MANTER_APENAS_O_PERIODO and not args.acumular

    ini, fim = _limites(args.inicio, args.fim, args.fuso)

    rotulo = "data do conteúdo (published_at)" if coluna == "published_at" \
        else "data da coleta (collected_at)"

    print("=" * 66)
    print("NORMALIZAÇÃO POR PERÍODO — Radar Ódio v0.1")
    print("=" * 66)
    print(f"  tabela destino : {tabela}")
    print(f"  período        : {ini.isoformat()}  →  {fim.isoformat()}  ({args.fuso})")
    print(f"  filtro por     : {rotulo}")
    print(f"  plataformas    : {', '.join(args.plataformas) if args.plataformas else 'todas'}")
    print(f"  modo           : {'sincronizar período (preserva IDs)' if sincronizar else 'acumular (upsert)'}")
    print("=" * 66)

    filtro = ""
    params: dict = {"ini": ini, "fim": fim}
    if args.plataformas:
        filtro = "AND platform = ANY(%(plataformas)s)"
        params["plataformas"] = args.plataformas

    destino = get_conn()
    with destino.cursor() as cur:
        cur.execute(_ddl(tabela))
    destino.commit()

    origem = psycopg.connect(settings.postgres_uri)
    audit = Auditoria()
    t0 = time.perf_counter()

    try:
        _processa(origem, destino, tabela, "post",
                  _SQL_POSTS.format(filtro=filtro, coluna=coluna), params, audit)
        _processa(origem, destino, tabela, "comment",
                  _SQL_COMMENTS.format(filtro=filtro, coluna=coluna), params, audit)
    finally:
        origem.close()

    removidos = 0
    if sincronizar:
        removidos = _descarta_fora_do_periodo(
            destino, tabela, coluna, ini, fim, args.plataformas
        )

    db = _valida_destino(destino, tabela, coluna, ini, fim)
    elapsed = time.perf_counter() - t0

    _relatorio(args, tabela, audit, db, elapsed, removidos)

    close_conn()

    falhas = []
    if audit.lidos != audit.gravados:
        falhas.append(f"registros lidos ({audit.lidos}) != gravados ({audit.gravados})")
    if audit.textos_vazios:
        falhas.append(f"{audit.textos_vazios} texto(s) ficaram vazios")
    if db["cr"] or db["tab"] or db["espaco_duplo"]:
        falhas.append("sobraram \\r, \\t ou espaços duplos")
    perda_emoji = audit.emoji_antes - audit.emoji_depois
    if perda_emoji != audit.emoji_no_removido:
        falhas.append(
            f"emojis: perdidos={perda_emoji}, mas só {audit.emoji_no_removido} "
            "estavam dentro de trechos anonimizados"
        )
    perda_hashtag = audit.hashtag_antes - audit.hashtag_depois
    if perda_hashtag != audit.hashtag_no_removido:
        falhas.append(
            f"hashtags: perdidas={perda_hashtag}, mas só {audit.hashtag_no_removido} "
            "estavam dentro de trechos anonimizados"
        )

    if falhas:
        print("\nVALIDAÇÃO: FALHOU")
        for f in falhas:
            print(f"  - {f}")
        return 1

    print("\nVALIDAÇÃO: OK — bruto preservado, texto normalizado, nada foi perdido.")
    return 0


def _relatorio(args, tabela, audit: Auditoria, db: dict, elapsed: float, removidos: int) -> None:
    print("\n" + "=" * 66)
    print("RELATÓRIO")
    print("=" * 66)
    print(f"  registros lidos       : {audit.lidos:,}")
    print(f"  registros gravados    : {audit.gravados:,}")
    print(f"  removidos (fora do período): {removidos:,}")
    print(f"  linhas no período     : {db['total']:,}   ({tabela}, por {args.coluna_periodo})")
    print(f"  tempo                 : {elapsed:.1f}s")
    print("\n  Anonimização (ocorrências no texto normalizado):")
    print(f"    <URL>   : {audit.urld:,}")
    print(f"    <EMAIL> : {audit.emaild:,}")
    print(f"    <ID>    : {audit.cpfd:,}")
    print(f"    <PHONE> : {audit.phoned:,}")
    print(f"    <USER>  : {audit.userd:,}")
    print("\n  Validação:")
    print(f"    textos esvaziados    : {audit.textos_vazios}")
    print(f"    \\r restantes         : {db['cr']}")
    print(f"    \\t restantes         : {db['tab']}")
    print(f"    espaços duplos       : {db['espaco_duplo']}")
    print(f"    emojis               : {audit.emoji_antes:,} → {audit.emoji_depois:,}"
          f"   ({audit.emoji_no_removido:,} dentro de trechos anonimizados)")
    print(f"    hashtags             : {audit.hashtag_antes:,} → {audit.hashtag_depois:,}"
          f"   ({audit.hashtag_no_removido:,} dentro de trechos anonimizados)")
    print("=" * 66)


if __name__ == "__main__":
    sys.exit(main())
