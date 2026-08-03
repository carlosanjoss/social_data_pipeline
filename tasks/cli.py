"""
CLI para enviar tarefas ao Celery worker.

Uso:
    python -m tasks.cli ingest reddit
    python -m tasks.cli ingest all
    python -m tasks.cli validate facebook
    python -m tasks.cli load twitter
    python -m tasks.cli pipeline youtube
    python -m tasks.cli pipeline all
    python -m tasks.cli dead-letter list
    python -m tasks.cli dead-letter replay <task_id>
"""
from __future__ import annotations

import sys
import json

PLATFORMS = ["reddit", "twitter", "youtube", "facebook", "tiktok", "whatsapp", "telegram"]


def _resolve_platforms(arg: str) -> list[str]:
    if arg == "all":
        return PLATFORMS
    if arg in PLATFORMS:
        return [arg]
    print(f"Plataforma invalida: {arg}. Opcoes: {PLATFORMS + ['all']}")
    sys.exit(1)


def cmd_ingest(args: list[str]) -> None:
    from tasks.ingest import ingest_platform_task, ingest_all_task
    platform = args[0] if args else "all"
    if platform == "all":
        task = ingest_all_task.delay()
        print(f"[ingest_all] task_id={task.id}")
    else:
        for p in _resolve_platforms(platform):
            task = ingest_platform_task.delay(p)
            print(f"[ingest:{p}] task_id={task.id}")


def cmd_validate(args: list[str]) -> None:
    from tasks.validate import validate_platform_task, validate_all_task
    platform = args[0] if args else "all"
    if platform == "all":
        task = validate_all_task.delay()
        print(f"[validate_all] task_id={task.id}")
    else:
        for p in _resolve_platforms(platform):
            task = validate_platform_task.delay(p)
            print(f"[validate:{p}] task_id={task.id}")


def cmd_load(args: list[str]) -> None:
    from tasks.load import load_platform_task, load_all_task
    platform = args[0] if args else "all"
    if platform == "all":
        task = load_all_task.delay()
        print(f"[load_all] task_id={task.id}")
    else:
        for p in _resolve_platforms(platform):
            task = load_platform_task.delay(p)
            print(f"[load:{p}] task_id={task.id}")


def cmd_pipeline(args: list[str]) -> None:
    from tasks.pipeline import run_platform_pipeline, run_full_pipeline
    platform = args[0] if args else "all"
    if platform == "all":
        task = run_full_pipeline.delay()
        print(f"[pipeline_full] task_id={task.id}")
    else:
        for p in _resolve_platforms(platform):
            task = run_platform_pipeline.delay(p)
            print(f"[pipeline:{p}] task_id={task.id}")


def cmd_dead_letter(args: list[str]) -> None:
    from tasks.dead_letter import list_dead_letters, replay_dead_letter
    sub = args[0] if args else "list"
    if sub == "list":
        docs = list_dead_letters(limit=20)
        if not docs:
            print("Dead-letter queue vazia.")
        for d in docs:
            print(json.dumps(d, default=str, ensure_ascii=False))
    elif sub == "replay" and len(args) >= 2:
        ok = replay_dead_letter(args[1])
        print("Reenfileirado." if ok else "Task nao encontrada.")
    else:
        print("Uso: dead-letter list | dead-letter replay <task_id>")


COMMANDS = {
    "ingest":      cmd_ingest,
    "validate":    cmd_validate,
    "load":        cmd_load,
    "pipeline":    cmd_pipeline,
    "dead-letter": cmd_dead_letter,
}


def main() -> None:
    argv = sys.argv[1:]
    if not argv or argv[0] not in COMMANDS:
        print("Comandos:", list(COMMANDS))
        sys.exit(1)
    COMMANDS[argv[0]](argv[1:])


if __name__ == "__main__":
    main()
