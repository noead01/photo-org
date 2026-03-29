from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_db_config_import_survives_deleted_working_directory(tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    vanished_cwd = tmp_path / "vanished-cwd"
    vanished_cwd.mkdir()

    script = """
import os
from pathlib import Path

vanished = Path(os.environ["PHOTO_ORG_VANISHED_CWD"])
os.chdir(vanished)
vanished.rmdir()

from app.db.config import DEFAULT_SQLITE_PATH

print(DEFAULT_SQLITE_PATH)
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PYTHONPATH": str(repo_root / "apps" / "api"),
            "PHOTO_ORG_VANISHED_CWD": str(vanished_cwd),
        },
        cwd=repo_root,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(repo_root / "apps" / "api" / "photoorg.db")
