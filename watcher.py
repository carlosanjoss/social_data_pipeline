"""
Watcher contínuo — monitora os diretórios dos scrapers e dispara o pipeline
automaticamente quando detecta arquivos JSON novos ou modificados.

Uso:
    python watcher.py                  # verifica a cada 60s, todas as plataformas
    python watcher.py --interval 300   # verifica a cada 5 minutos
    python watcher.py --platforms reddit twitter
    python watcher.py --once           # roda uma vez e sai (útil para cron externo)
"""
from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path

from config import setup_logging, get_logger
from config.settings import settings

logger = get_logger(__name__)

# Caminhos das pastas que cada scraper escreve
PLATFORM_PATHS: dict[str, list[Path]] = {
    "reddit":   [Path(settings.reddit_data_path)],
    "twitter":  [Path(settings.twitter_data_path)],
    "youtube":  [Path(settings.youtube_data_path)],
    "facebook": [Path(settings.facebook_data_path)],
    "instagram":[Path(settings.instagram_data_path)],
    "tiktok":   [Path(settings.tiktok_data_path)],
    "whatsapp": [Path(settings.farol_exports_path)],
    "telegram": [Path(settings.farol_exports_path)],
}


def _latest_mtime(paths: list[Path]) -> float:
    """Retorna o mtime mais recente entre todos os JSONs nas pastas indicadas."""
    latest = 0.0
    for base in paths:
        if not base.exists():
            continue
        for f in base.rglob("*.json"):
            try:
                mtime = f.stat().st_mtime
                if mtime > latest:
                    latest = mtime
            except OSError:
                pass
    return latest


def _run_platform(platform: str) -> bool:
    """Executa as três etapas do pipeline para uma plataforma. Retorna True se ok."""
    from pipelines.ingest_historical import ingest_platform
    from pipelines.load_postgres import run_load as pg_load
    from etl.load_postgres import finalize_comments
    from database.postgres.client import get_conn, close_conn
    from warehouse.load import run_load as dw_load

    logger.info("pipeline_start", platform=platform)

    result = ingest_platform(platform)
    if result.error:
        logger.error("ingest_failed", platform=platform, error=result.error)
        return False

    pg_load(platforms=[platform])

    conn = get_conn()
    finalize_comments(conn, [platform])
    close_conn()

    dw_load()

    logger.info("pipeline_done", platform=platform,
                posts=result.posts, comments=result.comments)
    return True


def watch(platforms: list[str], interval: int) -> None:
    """Loop principal: compara mtimes e dispara o pipeline quando há mudança."""
    # snapshot inicial — evita rodar logo ao iniciar
    snapshots: dict[str, float] = {
        p: _latest_mtime(PLATFORM_PATHS[p]) for p in platforms
    }
    logger.info("watcher_started", platforms=platforms, interval_s=interval)
    print(f"\nWatcher ativo. Verificando a cada {interval}s. Ctrl+C para parar.\n")

    running = True

    def _stop(sig, frame):
        nonlocal running
        print("\nParando watcher...")
        running = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    while running:
        time.sleep(interval)
        if not running:
            break

        changed: list[str] = []
        for platform in platforms:
            current = _latest_mtime(PLATFORM_PATHS[platform])
            if current > snapshots[platform]:
                changed.append(platform)
                snapshots[platform] = current

        if not changed:
            logger.debug("no_changes_detected")
            continue

        logger.info("changes_detected", platforms=changed)
        print(f"\n[{_ts()}] Mudanças detectadas em: {', '.join(changed)}")

        for platform in changed:
            print(f"  → rodando pipeline para {platform}...")
            ok = _run_platform(platform)
            print(f"  {'OK' if ok else 'ERRO'} — {platform}")

        print()


def run_once(platforms: list[str]) -> int:
    """Roda o pipeline uma vez para todas as plataformas (modo cron)."""
    errors = 0
    for platform in platforms:
        ok = _run_platform(platform)
        if not ok:
            errors += 1
    return errors


def _ts() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main() -> int:
    setup_logging()

    parser = argparse.ArgumentParser(description="Watcher contínuo do pipeline")
    parser.add_argument(
        "--platforms", nargs="+",
        choices=list(PLATFORM_PATHS.keys()),
        default=list(PLATFORM_PATHS.keys()),
        help="Plataformas a monitorar (padrão: todas)",
    )
    parser.add_argument(
        "--interval", type=int, default=60,
        help="Intervalo de verificação em segundos (padrão: 60)",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Roda o pipeline uma vez e sai, sem monitorar",
    )
    args = parser.parse_args()

    if args.once:
        errors = run_once(args.platforms)
        return 1 if errors else 0

    watch(args.platforms, args.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
