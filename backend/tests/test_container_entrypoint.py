from __future__ import annotations

import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
ENTRYPOINT = ROOT_DIR / "docker" / "invoice-entrypoint.sh"


def test_container_entrypoint_exists_and_has_valid_shell_syntax() -> None:
    assert ENTRYPOINT.exists()

    result = subprocess.run(
        ["sh", "-n", str(ENTRYPOINT)],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_web_command_runs_auto_migration_before_uvicorn() -> None:
    script = ENTRYPOINT.read_text(encoding="utf-8")
    web_branch_start = script.index("  web)")
    worker_branch_start = script.index("  worker)", web_branch_start)
    web_branch = script[web_branch_start:worker_branch_start]

    assert "AUTO_MIGRATE" in script
    assert "alembic -c /app/alembic.ini upgrade head" in script
    assert "run_migrations" in web_branch
    assert web_branch.index("run_migrations") < web_branch.index("exec uvicorn")
