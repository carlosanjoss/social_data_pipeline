# Radar Ódio — Social Data Pipeline

Pipeline de coleta e processamento de dados de discurso de ódio em redes sociais brasileiras (Reddit, Twitter, YouTube, Facebook, TikTok, WhatsApp e Telegram).

## Arquitetura

```
Scrapers JSON (Reddit/Twitter/YouTube/Facebook/TikTok) ─┐
Farol Digital JSON (WhatsApp/Telegram) ─────────────────┤
Reddit Pipeline (PostgreSQL próprio) ──────────────────┤
                                                       ▼
  MongoDB (raw lake)          ← dados brutos, sem transformação
        │
        ▼
  PostgreSQL (IS-A schema)    ← dados normalizados e validados
        │
        ▼
  DuckDB (star schema DW)     ← data warehouse analítico
```

Os scrapers rodam de forma independente e salvam JSONs em disco. O projeto irmão
`../reddit_pipeline` mantém outra coleta em um PostgreSQL próprio. A ingestão do
Reddit une as duas fontes no MongoDB e as deduplica pelo ID nativo do Reddit.

O PostgreSQL final tem uma única restrição de escopo: somente textos detectados
como português, persistidos com `language = 'pt-BR'`. Não existe limite de data;
`published_at` pode conter qualquer data ou ser nulo. Uma restrição `CHECK`
impede que cargas futuras gravem outro idioma.

**Posts-âncora (`is_anchor = TRUE`).** Um comentário português pode pertencer a
um post cujo texto não foi detectado como português (títulos curtos ou em
MAIÚSCULAS enganam o `langdetect`) ou que não tem texto nenhum. Para não deixar
o comentário órfão, o pipeline reinsere esse post **apenas como âncora da FK**,
marcado com `is_anchor = TRUE`, guardando o idioma real detectado. O escopo
pt-BR continua valendo para o corpus (`is_anchor = FALSE`) e para todos os
comentários; a `CHECK` correspondente é `is_anchor OR language = 'pt-BR'`.

---

## Pré-requisitos

- Python 3.10+
- Docker + Docker Compose
- Windows 10/11 (este guia assume Windows com PowerShell)

> **Atenção (Windows):** o Windows já instala MongoDB na porta 27017 e PostgreSQL na porta 5432. Por isso os containers do projeto usam **27018** (Mongo) e **5433** (Postgres). Isso já está configurado no `.env`.

---

## Configuração inicial

### 1. Copiar e ajustar o `.env`

```powershell
cd "Trabalho Radar Ódio\social_data_pipeline"
Copy-Item .env.example .env
```

Edite o `.env`. As variáveis mais importantes:

| Variável | Valor padrão | O que é |
|---|---|---|
| `MONGO_PORT` | `27018` | Porta do MongoDB no host |
| `POSTGRES_PORT` | `5433` | Porta do PostgreSQL no host |
| `REDIS_PORT` | `6379` | Porta do Redis |
| `MONGO_PASSWORD` | `change_me` | Senha do MongoDB |
| `POSTGRES_PASSWORD` | `change_me` | Senha do PostgreSQL |
| `REDDIT_DATA_PATH` | `../reddit_scrapper/src/reddit_pipeline/data` | Onde estão os JSONs do Reddit |
| `REDDIT_PIPELINE_ENABLED` | `true` | Inclui o PostgreSQL do projeto `../reddit_pipeline` |
| `REDDIT_PIPELINE_ENV_PATH` | `../reddit_pipeline/.env` | Credenciais da fonte Reddit adicional |
| `REDDIT_PIPELINE_URI` | vazio | URI opcional que substitui o arquivo `.env` da fonte |
| `TWITTER_DATA_PATH` | `../twitter_scraper_project/data/json` | JSONs do Twitter |
| `YOUTUBE_DATA_PATH` | `../youtube_scraper/data` | JSONs do YouTube |
| `FACEBOOK_DATA_PATH` | `../facebook_scrapper/data/output` | JSONs do Facebook |
| `TIKTOK_DATA_PATH` | `../tiktok_scrapper/data` | JSONs do TikTok |
| `FAROL_EXPORTS_PATH` | `../farol_digital_json_api/exports` | Exports do WhatsApp e Telegram |

### 2. Subir os containers

```powershell
docker compose up -d mongodb postgres redis
```

Verificar se estão rodando:

```powershell
docker compose ps
```

### 3. Criar e ativar o ambiente virtual

```powershell
# Criar o venv (só na primeira vez)
python -m venv .venv

# Ativar (toda vez que abrir um novo terminal)
.venv\Scripts\Activate.ps1
```

Se o PowerShell bloquear a execução de scripts, rode isso uma vez:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Quando o venv estiver ativo, o terminal mostra `(.venv)` no início da linha.

### 4. Instalar dependências Python

```powershell
pip install -r requirements.txt
```

> Se der erro no Prefect, fixe o Pydantic:
> ```powershell
> pip install "pydantic==2.7.1" "pydantic-settings==2.3.1"
> ```

---

## Rodando o pipeline

O pipeline tem três etapas que devem ser executadas na ordem. Todos os comandos são executados na pasta `social_data_pipeline`.

### Etapa 1 — Ingestão: Scrapers → MongoDB

Lê os arquivos JSON dos scrapers e salva no MongoDB (coleção `raw_posts` /
`raw_comments`). Para Reddit, também lê `reddit_posts` e
`reddit_clean_comments` do PostgreSQL do projeto `../reddit_pipeline`. Para
WhatsApp e Telegram, mescla os snapshots repetidos e deduplica as mensagens
pelo campo `id` antes de gravá-las em `raw_posts` como `content_type=message`.

```powershell
# Todas as plataformas
python -m pipelines.ingest_historical

# Ou plataforma específica
python -m pipelines.ingest_historical --platforms reddit
python -m pipelines.ingest_historical --platforms twitter youtube
```

### Etapa 2 — Carga: MongoDB → PostgreSQL

Normaliza os dados do MongoDB e carrega no PostgreSQL com schema IS-A. Nesta
fronteira, o pipeline detecta o idioma do texto e descarta somente o que não é
português. Não há filtro temporal.

A detecção de idioma (`langdetect`, CPU-bound) roda em um pool de processos com
`cpus − 1` workers — o resultado é idêntico ao modo sequencial (mesmo
`decide_target`, seed fixa), só muito mais rápido em corpora grandes. Para
ajustar:

```powershell
# Forçar um número fixo de workers (0 ou 1 desliga o paralelismo)
$env:LOAD_WORKERS = "8"; python -m pipelines.load_postgres
```

```powershell
# Todas as plataformas
python -m pipelines.load_postgres

# Ou plataformas específicas
python -m pipelines.load_postgres --platforms reddit twitter
```

Resolve automaticamente as FKs entre comentários e posts ao final e, antes
disso, recupera os **posts-âncora**: comentários cujo post pai é português/não
tem texto mas foi descartado na fronteira de idioma passam a ter o pai
reinserido (`is_anchor = TRUE`) e o `post_pk` resolvido.

Para auditar as garantias do banco:

```powershell
Get-Content database/postgres/audit_final_scope.sql |
  docker exec -i radar_postgres psql -U radar -d radar_odio
```

As linhas `comments` e `posts (corpus)` devem mostrar `violacoes = 0`. A linha
`posts (âncora)` não é violação — são os pais reinseridos só para sustentar a FK.

### Etapa 3 — Data Warehouse: PostgreSQL → DuckDB

Carrega o star schema analítico no DuckDB.

```powershell
# Só a carga
python -m warehouse.load

# Carga + relatório analítico
python -m warehouse.load --report
```

O arquivo DuckDB fica em `data/radar_odio.duckdb`.

---

## Normalização por período (tabela dedicada)

`normalize_periodo.py` copia os registros de `posts`/`comments` cujo
`collected_at` cai num período configurável para uma tabela dedicada, aplicando
o pré-processamento e a anonimização do **Radar Ódio v0.1**.

**Como usar:** edite o bloco `CONFIGURAÇÃO` no topo do script e rode.

```python
PERIODO_INICIO = "2026-09-30"   # inclusivo
PERIODO_FIM    = "2026-10-06"   # exclusivo: inclui todo o dia 05/10
FUSO_HORARIO   = "UTC"          # ou "America/Sao_Paulo"

# "published_at" → data do CONTEÚDO   |   "collected_at" → data da COLETA
COLUNA_PERIODO = "published_at"

TABELA_DESTINO = "periodo_eleicoes_1_turno"
MANTER_APENAS_O_PERIODO = True
```

```powershell
.venv311\Scripts\python.exe normalize_periodo.py

# ou por linha de comando, sem editar o arquivo
.venv311\Scripts\python.exe normalize_periodo.py --inicio 2026-10-01 --fim 2026-11-01
.venv311\Scripts\python.exe normalize_periodo.py --coluna-periodo collected_at
.venv311\Scripts\python.exe normalize_periodo.py --plataformas youtube twitter
.venv311\Scripts\python.exe normalize_periodo.py --fuso America/Sao_Paulo
```

### Sincronização do período (não usa TRUNCATE)

Com `MANTER_APENAS_O_PERIODO = True` (padrão) a tabela passa a refletir
**exatamente** o período configurado: faz upsert dos registros que entram no
período e apaga os que ficaram de fora.

A remoção é um `DELETE` — **não** `TRUNCATE` — justamente para **preservar os IDs
das linhas que permanecem**. Isso importa porque a tabela
`periodo_eleicoes_1_turno_bert` (pipeline `bert_radar_odio/`) referencia
`id` com `ON DELETE CASCADE`: linhas que saem do período levam suas inferências
junto; linhas que ficam mantêm as suas.

> ⚠️ Antes de rodar com um período diferente, **pare o pipeline de inferência**
> (`bert_radar_odio/run_resto.py`). Escrever enquanto a recarga remove/insere
> linhas gera conflito de lock e pode levar a deadlock.

Chamar com `--acumular` desliga a remoção (só faz upsert).

### O que o texto sofre

Normalização (`services/text_normalization.py`): Unicode **NFC**; `\r\n` e `\r`
→ `\n`; `\t` → espaço; colapso de 2+ espaços ASCII. **Nada mais é alterado** —
caixa, pontuação, emojis, hashtags, erros de digitação, abreviações e `U+FFFD`
são preservados; sem lowercase, stemming, lematização, remoção de stopwords,
correção ortográfica ou tradução.

Anonimização, nesta ordem: marcadores legados (`[URL]`→`<URL>` etc.) → URLs →
`<EMAIL>` → CPF formalmente válido → `<ID>` → telefone validado → `<PHONE>` →
menções → `<USER>`. Telefone segue a regra conservadora (DDD brasileiro válido,
celular de 9 dígitos começando por `9`, fixo só com evidência estrutural,
separadores apenas espaço/ponto/hífen, CPF antes de telefone).

### Colunas da tabela

`id`, `kind` (`post`|`comment`), `source_id`, `platform`, `content_type`,
`external_id`, `post_external_id`, `parent_external_id`, `author`, `title`,
`url`, `language`, `is_anchor`, `published_at`, `collected_at`, `text_raw`
(**bruto, preservado sem alterações**), `text_normalized`, `normalized_at`.

### Validação automática (ao final de cada execução)

Confere registros lidos = gravados, nenhum texto esvaziado, ausência de `\r`,
`\t` e espaços duplos, e igualdade de contagem de emojis e hashtags antes/depois.
Se algo falhar, o script sai com código 1 e lista o motivo.

---

## Verificando os bancos

### MongoDB

```powershell
# Conectar no container
docker exec -it radar_mongo mongosh -u admin -p admin123 --authenticationDatabase admin

# No shell do mongosh:
use radar_odio
db.raw_posts.countDocuments()
db.raw_comments.countDocuments()
db.raw_posts.aggregate([{$group:{_id:"$platform", total:{$sum:1}}}])

# Sair
exit
```

### PostgreSQL

```powershell
# Conectar no container
docker exec -it radar_postgres psql -U radar -d radar_odio

# No shell do psql:
\dt                                                    -- lista todas as tabelas
SELECT platform, COUNT(*) FROM posts GROUP BY platform;
SELECT platform, COUNT(*) FROM comments GROUP BY platform;
SELECT * FROM posts LIMIT 5;
\q                                                     -- sair
```

Ou conectar por fora do Docker com qualquer cliente (DBeaver, TablePlus, psql local):
- **Host:** `localhost`
- **Porta:** `5433`
- **Banco:** `radar_odio`
- **Usuário:** `radar`
- **Senha:** `admin123`

### DuckDB

```powershell
# Opção 1 — via Python (mais simples)
python -c "
import duckdb
conn = duckdb.connect('data/radar_odio.duckdb')
print(conn.execute('SHOW TABLES').fetchdf())
print(conn.execute('SELECT platform_key, COUNT(*) FROM fact_posts GROUP BY 1').fetchdf())
print(conn.execute('SELECT COUNT(*) FROM fact_comments').fetchone())
"

# Opção 2 — CLI do DuckDB (se instalado)
duckdb data/radar_odio.duckdb
# .tables
# SELECT * FROM dim_platform;
# .quit
```

Tabelas do star schema:

| Tabela | Descrição |
|---|---|
| `dim_date` | Spine de datas (2016–2030) |
| `dim_platform` | Reddit / Twitter / YouTube / Facebook / TikTok |
| `dim_content_type` | post / tweet / video / comment / reply |
| `dim_location` | Subreddit / canal / página |
| `dim_author` | Autores (SCD Type 2) |
| `fact_posts` | 1 linha por post/vídeo/tweet |
| `fact_comments` | 1 linha por comentário/reply |

---

## Ingerindo novos dados

Quando os scrapers gerarem novos arquivos JSON, basta rodar as três etapas do pipeline de novo — todas são **idempotentes** (usam upsert, não duplicam registros existentes):

```powershell
# Ativar o venv se ainda não estiver ativo
.venv\Scripts\Activate.ps1

# 1. JSONs dos scrapers → MongoDB
python -m pipelines.ingest_historical

# 2. MongoDB → PostgreSQL
python -m pipelines.load_postgres

# 3. PostgreSQL → DuckDB
python -m warehouse.load
```

Para atualizar só uma plataforma específica:

```powershell
python -m pipelines.ingest_historical --platforms reddit
python -m pipelines.load_postgres --platforms reddit
python -m warehouse.load   # DuckDB sempre recarrega tudo (rápido, ~2 min)
```

Os arquivos lidos pelo pipeline ficam nos caminhos configurados no `.env`:

| Plataforma | Variável no `.env` | Arquivo lido |
|---|---|---|
| Reddit | `REDDIT_DATA_PATH` + `REDDIT_PIPELINE_ENV_PATH` | JSONs e PostgreSQL do projeto irmão |
| Twitter | `TWITTER_DATA_PATH` | arquivos `.json` na pasta |
| YouTube | `YOUTUBE_DATA_PATH` | arquivos `.json` na pasta |
| Facebook | `FACEBOOK_DATA_PATH` | arquivos `.json` na pasta |
| TikTok | `TIKTOK_DATA_PATH` | `{aweme_id}.json` por vídeo |
| WhatsApp | `FAROL_EXPORTS_PATH` | `fd_whatsapp__tb_messages__*.json` |
| Telegram | `FAROL_EXPORTS_PATH` | `fd_telegram__tb_messages__*.json` |

---

## Contagens atuais (última carga)

Carga executada em 06/10/2026 (`python -m pipelines.ingest_historical` +
`python -m pipelines.load_postgres`), com Instagram incluído, detecção de idioma
paralelizada e recuperação de posts-âncora. Auditoria de escopo: `violacoes = 0`
em `comments` e em `posts (corpus)`.

| Nível | Plataforma | Posts (corpus) | Posts (âncora) | Comentários |
|---|---:|---:|---:|---:|
| MongoDB (raw, sem filtro linguístico) | Todas | 297.364 | — | 4.885.274 |
| PostgreSQL (`pt-BR`, sem limite de data) | Todas | 226.356 | 3.923 | 3.588.752 |
| PostgreSQL | Facebook | 912 | 301 | 152.072 |
| PostgreSQL | Instagram | 4.493 | 256 | 64.167 |
| PostgreSQL | Reddit | 8.144 | 357 | 119.207 |
| PostgreSQL | Telegram | 99.813 | 0 | 0 |
| PostgreSQL | TikTok | 3.936 | 1.519 | 261.896 |
| PostgreSQL | Twitter | 5.852 | 313 | 62.049 |
| PostgreSQL | WhatsApp | 93.235 | 0 | 0 |
| PostgreSQL | YouTube | 9.971 | 1.177 | 2.929.361 |

Comentários com `post_pk` resolvido: **3.583.981 de 3.588.752 (99,87%)**. Os
4.771 órfãos restantes são todos do Twitter: 3.818 sob 207 tweets que não existem
no MongoDB (nunca coletados) e 953 registros de um gabarito de anotação sem
`post_external_id` na origem.


WhatsApp tem 122.092 mensagens brutas e Telegram tem 123.362 no MongoDB. No PostgreSQL,
somente as mensagens detectadas como português são mantidas. Como os JSONs dessas
plataformas não fornecem campos de resposta ou mensagem-pai, cada item é representado
como uma mensagem autônoma em `posts`, com os metadados específicos nas tabelas
`whatsapp_messages` e `telegram_messages`.

### Coleta de linguagem codificada — 21/07/2026

| Plataforma | Correspondências brutas | Aceitas como `pt-BR` |
|---|---:|---:|
| WhatsApp | 102.092 | 87.444 |
| Telegram | 103.939 | 89.186 |
| **Total** | **206.031** | **176.630** |

Cada mensagem da coleta mantém os vetores `matched_terms` e `collection_periods` na tabela de
extensão da plataforma. Os períodos sem linhas na origem também foram preservados no manifesto:
WhatsApp não retornou mensagens em Pré-eleições 2026; Telegram não retornou mensagens nos três
períodos anteriores a 2022.

Contagens auditadas em 21/07/2026. O DuckDB não foi recarregado nesta alteração;
rode `python -m warehouse.load` quando quiser refletir o novo PostgreSQL no DW.

---

## Pipeline contínuo (alimentação automática)

Para deixar o pipeline rodando continuamente — à medida que os scrapers geram novos dados, o pipeline é disparado automaticamente — use o `watcher.py`.

Ele monitora as pastas de saída de cada scraper e, quando detecta um arquivo JSON novo ou modificado, executa as três etapas do pipeline para aquela plataforma.

```powershell
# Ativar venv primeiro
.venv\Scripts\Activate.ps1

# Monitorar todas as plataformas, verificando a cada 60s (padrão)
python watcher.py

# Verificar a cada 5 minutos
python watcher.py --interval 300

# Monitorar só o Reddit e Twitter
python watcher.py --platforms reddit twitter

# Rodar uma vez e sair (útil para agendar no Agendador de Tarefas do Windows)
python watcher.py --once
```

**Como funciona:**
1. Ao iniciar, registra o timestamp dos arquivos JSON de cada scraper
2. A cada intervalo, compara os timestamps com o registrado
3. Se algum arquivo mudou, roda automaticamente: ingestão → PostgreSQL → DuckDB
4. Plataformas sem mudança são ignoradas naquele ciclo
5. `Ctrl+C` para parar com segurança

**Fluxo típico de uso:**
```
Terminal 1: rode o scraper do Reddit normalmente
Terminal 2: python watcher.py --interval 120

→ Quando o Reddit terminar de coletar e atualizar o posts.json,
  o watcher detecta a mudança e dispara o pipeline automaticamente.
```

### Agendar no Windows (alternativa ao watcher)

Se preferir rodar em horários fixos em vez de monitorar por mudanças, use o Agendador de Tarefas do Windows com o modo `--once`:

```powershell
# Cria uma tarefa que roda o pipeline todo dia às 06h
$projectRoot = (Resolve-Path ".\social_data_pipeline").Path
$pythonPath = Join-Path $projectRoot ".venv311\Scripts\python.exe"
$watcherPath = Join-Path $projectRoot "watcher.py"
$action = New-ScheduledTaskAction `
    -Execute $pythonPath `
    -Argument "`"$watcherPath`" --once" `
    -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -Daily -At "06:00"
Register-ScheduledTask -TaskName "RadarOdio-Pipeline" -Action $action -Trigger $trigger
```

---

## Automação com Celery (opcional)

Requer Redis rodando (`docker compose up -d redis`).

```powershell
# Terminal 1 — worker
celery -A tasks.app worker --loglevel=info -Q ingest,validate,load,pipeline

# Terminal 2 — disparar tarefas
python -m tasks.cli ingest all           # ingere todas as plataformas
python -m tasks.cli pipeline reddit      # pipeline completo só do Reddit
python -m tasks.cli dead-letter list     # ver tarefas com falha
```

## Agendamento com Prefect (opcional)

```powershell
# Rodar o runner (executa o pipeline diariamente às 03h UTC)
python -m flows.serve

# Ou disparar um flow manualmente via Python
python -c "
from flows.pipeline_flow import pipeline_flow
pipeline_flow()
"
```

Interface web do Prefect: `http://localhost:4200` (se subiu com `--profile orchestration`).

---

## Estrutura do projeto

```
social_data_pipeline/
├── connectors/          # leitura dos JSONs de cada scraper
├── normalizers/         # transforma raw → schema normalizado
├── repositories/        # upserts no PostgreSQL
├── pipelines/           # scripts de orquestração (ingest + load)
├── database/
│   ├── mongo/           # client + collections
│   └── postgres/        # client + schema.sql
├── warehouse/           # DuckDB: client, ETL, queries, schema
│   └── etl/
│       ├── dims.py      # carga das dimensões
│       └── facts.py     # carga das tabelas fato
├── tasks/               # Celery: tasks + dead-letter + CLI
├── flows/               # Prefect: flows + runner
├── config/              # settings, logging
├── data/
│   └── radar_odio.duckdb
├── docker-compose.yml
├── requirements.txt
└── .env
```

---

## Coletando dados com o TikTok scraper

O scraper fica em `tiktok_scrapper/`. Para coletar:

```powershell
cd "..\tiktok_scrapper"
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Adicione URLs ou IDs de vídeo em links.txt (um por linha)
# Exemplo: https://www.tiktok.com/@usuario/video/7418294751977327878

# Coletar todos os vídeos do links.txt
python main.py

# Coletar um vídeo específico
python main.py --aweme_id 7418294751977327878

# Re-coletar mesmo se já existir arquivo salvo
python main.py --overwrite
```

Os JSONs são salvos em `tiktok_scrapper/data/{aweme_id}.json`. Cada arquivo contém o vídeo e todos os seus comentários (incluindo replies aninhados).

> **Atenção:** o scraper usa a API interna do TikTok (sem autenticação). Funciona para coletas pontuais mas pode ser bloqueado por rate-limit em uso intensivo.

Depois de coletar, rode o pipeline normalmente:

```powershell
cd "..\social_data_pipeline"
python -m pipelines.ingest_historical --platforms tiktok
python -m pipelines.load_postgres --platforms tiktok
python -m warehouse.load
```

---

## Problemas conhecidos

**Erro de conexão no PostgreSQL**
Se der `connection refused` na porta 5432, é o PostgreSQL local do Windows interferindo. Confirme que o `.env` tem `POSTGRES_PORT=5433` e que o container subiu na porta certa (`docker compose ps`).

**Prefect quebra com Pydantic > 2.7**
Sempre que reinstalar dependências, verifique: `pip show pydantic` deve mostrar `2.7.1`. Se estiver em versão maior, rode:
```powershell
pip install "pydantic==2.7.1" "pydantic-settings==2.3.1"
```

**DuckDB não conecta no PostgreSQL**
O DuckDB usa a extensão `postgres` para ler direto do PostgreSQL. Ela é baixada automaticamente na primeira execução. Se falhar, verifique se o PostgreSQL está acessível na porta 5433.
