"""Entry point for the banking agent REPL demo."""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cli.repl import run_repl  # noqa: E402


def main() -> None:
    """Start the interactive REPL."""
    run_repl()


if __name__ == "__main__":
    main()
