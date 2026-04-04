import os
import subprocess
from pathlib import Path


def _make_variable(target: str, variable: str, environment: str, *extra_args: str) -> str:
    child_env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("PHOTO_ORG_")
    }
    completed = subprocess.run(
        ["make", "-pn", target, f"PHOTO_ORG_ENVIRONMENT={environment}", *extra_args],
        check=True,
        text=True,
        capture_output=True,
        env=child_env,
    )
    for line in completed.stdout.splitlines():
        for operator in (" = ", " := "):
            prefix = f"{variable}{operator}"
            if line.startswith(prefix):
                return line[len(prefix):]
    raise AssertionError(f"missing make variable {variable}")


def test_compose_db_service_uses_dedicated_database_url_env_var():
    compose = Path("compose.yaml").read_text(encoding="utf-8")

    assert "PHOTO_ORG_DB_SERVICE_DATABASE_URL" in compose
    assert "${DB_SERVICE_DATABASE_URL:-" not in compose
    assert "${DATABASE_URL:-" not in compose


def test_compose_uses_namespaced_runtime_variables():
    compose = Path("compose.yaml").read_text(encoding="utf-8")

    assert "PHOTO_ORG_POSTGRES_HOST_PORT" in compose
    assert "PHOTO_ORG_API_HOST_PORT" in compose
    assert "POSTGRES_PORT" not in compose


def test_makefile_documents_compose_targets():
    makefile = Path("Makefile").read_text(encoding="utf-8")
    assert "env-create:" in makefile
    assert "compose-up:" in makefile
    assert "compose-migrate:" in makefile
    assert "compose-down:" in makefile
    assert "compose-down-volumes:" in makefile


def test_compose_uses_persistent_postgres_volume_by_default():
    compose = Path("compose.yaml").read_text(encoding="utf-8")

    assert "/var/lib/postgresql/data" in compose


def test_ephemeral_compose_override_exists_for_smoke_workflows():
    compose_override = Path("compose.ephemeral.yaml")

    assert compose_override.exists()
    assert compose_override.read_text(encoding="utf-8")


def test_make_derives_distinct_runtime_settings_per_environment():
    alice_project = _make_variable("compose-up", "PHOTO_ORG_COMPOSE_PROJECT_NAME", "alice")
    bob_project = _make_variable("compose-up", "PHOTO_ORG_COMPOSE_PROJECT_NAME", "bob")
    alice_pg_port = _make_variable("compose-up", "PHOTO_ORG_POSTGRES_HOST_PORT", "alice")
    bob_pg_port = _make_variable("compose-up", "PHOTO_ORG_POSTGRES_HOST_PORT", "bob")
    alice_api_port = _make_variable("compose-up", "PHOTO_ORG_API_HOST_PORT", "alice")
    bob_api_port = _make_variable("compose-up", "PHOTO_ORG_API_HOST_PORT", "bob")

    assert alice_project == "photo-org-alice"
    assert bob_project == "photo-org-bob"
    assert alice_pg_port != bob_pg_port
    assert alice_api_port != bob_api_port


def test_env_create_persists_immutable_storage_mode(tmp_path):
    registry_dir = tmp_path / "environments"

    created = subprocess.run(
        [
            "make",
            "env-create",
            "PHOTO_ORG_ENVIRONMENT=Scratch Check",
            "PHOTO_ORG_ENV_STORAGE_MODE=ephemeral",
            f"PHOTO_ORG_ENV_REGISTRY_DIR={registry_dir}",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert created.returncode == 0, created.stderr

    registry_file = registry_dir / "scratch-check.mk"
    assert registry_file.exists()
    assert "PHOTO_ORG_ENV_STORAGE_MODE := ephemeral" in registry_file.read_text(encoding="utf-8")

    changed = subprocess.run(
        [
            "make",
            "env-create",
            "PHOTO_ORG_ENVIRONMENT=Scratch Check",
            "PHOTO_ORG_ENV_STORAGE_MODE=persistent",
            f"PHOTO_ORG_ENV_REGISTRY_DIR={registry_dir}",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert changed.returncode != 0
    assert "immutable" in (changed.stderr + changed.stdout).lower()


def test_make_uses_registered_storage_mode_for_compose_selection(tmp_path):
    registry_dir = tmp_path / "environments"
    registry_dir.mkdir()
    (registry_dir / "smoke.mk").write_text("PHOTO_ORG_ENV_STORAGE_MODE := ephemeral\n", encoding="utf-8")
    (registry_dir / "dev.mk").write_text("PHOTO_ORG_ENV_STORAGE_MODE := persistent\n", encoding="utf-8")

    persistent_stack = _make_variable(
        "compose-up",
        "COMPOSE_STACK",
        "dev",
        f"PHOTO_ORG_ENV_REGISTRY_DIR={registry_dir}",
    )
    ephemeral_stack = _make_variable(
        "compose-up",
        "COMPOSE_STACK",
        "smoke",
        f"PHOTO_ORG_ENV_REGISTRY_DIR={registry_dir}",
    )

    assert "-f compose.yaml" in persistent_stack
    assert "compose.ephemeral.yaml" not in persistent_stack
    assert "-f compose.yaml" in ephemeral_stack
    assert "compose.ephemeral.yaml" in ephemeral_stack


def test_docs_point_to_compose_workflow():
    readme = Path("README.md").read_text(encoding="utf-8")
    contributing = Path("CONTRIBUTING.md").read_text(encoding="utf-8")

    assert "env-create" in readme
    assert "env-create" in contributing
    assert "PHOTO_ORG_ENVIRONMENT" in readme
    assert "PHOTO_ORG_ENVIRONMENT" in contributing
    assert "compose-up" in contributing


def test_makefile_documents_compose_smoke_workflow():
    makefile = Path("Makefile").read_text(encoding="utf-8")
    contributing = Path("CONTRIBUTING.md").read_text(encoding="utf-8")

    assert "compose-smoke:" in makefile
    assert "compose-e2e-smoke:" in makefile
    assert "compose.ephemeral.yaml" in makefile
    assert "./scripts/photo-org seed-corpus validate" in makefile
    assert "ingest_directory('/photos')" in makefile
    assert "http://127.0.0.1:$(PHOTO_ORG_API_HOST_PORT)/healthz" in makefile
    assert "/api/v1/internal/ingest-queue/process" in makefile
    assert 'print("retryable_errors=%s" % result["retryable_errors"])' in makefile
    assert "faces_detected=" in makefile
    assert "face_rows=" in makefile
    assert "make test-e2e" in makefile
    assert "compose-down-volumes" in makefile
    assert "compose-smoke" in contributing
    assert "compose-e2e-smoke" in contributing


def test_makefile_compose_e2e_smoke_generates_its_own_environment():
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "compose-e2e-smoke:" in makefile
    assert "PHOTO_ORG_ENV_STORAGE_MODE=ephemeral" in makefile
    assert "compose-smoke PHOTO_ORG_ENVIRONMENT=" in makefile
    assert "test-e2e PHOTO_ORG_ENVIRONMENT=" in makefile
    assert "compose-down-volumes PHOTO_ORG_ENVIRONMENT=" in makefile
    assert "PHOTO_ORG_E2E_DATABASE_URL=" in makefile
    assert "PHOTO_ORG_E2E_API_BASE_URL=" in makefile


def test_makefile_compose_e2e_smoke_reanchors_nested_make_calls_to_repo_root():
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert 'cd "$(CURDIR)" && env -u PHOTO_ORG_ENVIRONMENT' in makefile
    assert '$(MAKE) --no-print-directory env-create' in makefile
    assert '$(MAKE) --no-print-directory compose-smoke' in makefile
    assert '$(MAKE) --no-print-directory -s print-compose-db-url' in makefile
    assert '$(MAKE) --no-print-directory test-e2e' in makefile
    assert '$(MAKE) --no-print-directory compose-down-volumes' in makefile


def test_makefile_uses_namespaced_environment_contract():
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "PHOTO_ORG_ENVIRONMENT" in makefile
    assert "PHOTO_ORG_ENV_FILE" in makefile
    assert "PHOTO_ORG_ENV_REGISTRY_DIR" in makefile
    assert "PHOTO_ORG_ENV_STORAGE_MODE" in makefile
    assert "PHOTO_ORG_POSTGRES_HOST_PORT" in makefile
    assert "PHOTO_ORG_API_HOST_PORT" in makefile
    assert "PHOTO_ORG_COMPOSE_DATABASE_URL" in makefile
    assert "\nCOMPOSE_DATABASE_URL ?=" not in makefile
