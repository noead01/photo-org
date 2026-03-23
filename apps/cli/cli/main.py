from __future__ import annotations

from app import cli as api_cli


def build_parser():
    return api_cli.build_parser()


def main(argv: list[str] | None = None) -> int:
    return api_cli.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
