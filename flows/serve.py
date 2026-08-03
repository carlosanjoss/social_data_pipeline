"""
Registra e serve todos os flows com seus agendamentos.

Requer o servidor Prefect rodando:
    docker compose --profile orchestration up -d

Iniciar o servidor de flows:
    python -m flows.serve

Isso cria os seguintes deployments no Prefect:
  - full-pipeline/daily-03h     → cron "0 3 * * *" (03:00 UTC = meia-noite BRT)
  - ingest-flow/manual          → sem agendamento (trigger manual)
  - validate-flow/manual        → sem agendamento
  - load-postgres-flow/manual   → sem agendamento
"""
from __future__ import annotations

from prefect.runner import Runner

from flows.pipeline_flow import pipeline_flow
from flows.ingest_flow import ingest_flow
from flows.validate_flow import validate_flow
from flows.load_flow import load_flow


def build_runner() -> Runner:
    runner = Runner(name="radar-odio-runner")

    # Pipeline diário às 03:00 UTC (meia-noite BRT / horário de Brasília)
    runner.add_flow(
        pipeline_flow,
        name="daily-03h",
        cron="0 3 * * *",
        tags=["radar-odio", "daily"],
        description="Pipeline completo diário: ingest → validate → load",
    )

    # Flows manuais (sem cron — disparados via UI ou CLI)
    runner.add_flow(ingest_flow,   name="manual", tags=["radar-odio", "ingest"])
    runner.add_flow(validate_flow, name="manual", tags=["radar-odio", "validate"])
    runner.add_flow(load_flow,     name="manual", tags=["radar-odio", "load"])

    return runner


if __name__ == "__main__":
    runner = build_runner()
    print("Iniciando Prefect Runner — flows registrados:")
    print("  full-pipeline/daily-03h  (cron: 0 3 * * *)")
    print("  ingest-flow/manual")
    print("  validate-flow/manual")
    print("  load-postgres-flow/manual")
    print("\nUI disponivel em: http://localhost:4200")
    runner.start()
