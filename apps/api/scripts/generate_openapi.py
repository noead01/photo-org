from pathlib import Path
import sys


API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.main import app  # noqa: E402
from app.openapi_docs import write_openapi_yaml  # noqa: E402


DEFAULT_OUTPUT_PATH = API_ROOT / ".generated" / "openapi.yaml"


def main() -> None:
    write_openapi_yaml(app.openapi(), DEFAULT_OUTPUT_PATH)


if __name__ == "__main__":
    main()
