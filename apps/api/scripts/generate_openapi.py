from pathlib import Path
import sys

import yaml


API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.main import app  # noqa: E402


def main() -> None:
    spec_path = API_ROOT / "openapi" / "spec.yaml"
    spec_path.write_text(
        yaml.safe_dump(app.openapi(), sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
