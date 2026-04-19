"""Entry point — run as: python -m vigil

Flags:
  --log    Append JSONL tick records to ~/.local/share/vigil/YYYY-MM-DD.jsonl
"""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="vigil",
        description="Elite TUI power monitor",
    )
    parser.add_argument(
        "--log",
        action="store_true",
        default=False,
        help="Log every tick to ~/.local/share/vigil/YYYY-MM-DD.jsonl",
    )
    args = parser.parse_args()

    from vigil.app import TerminalInfoApp
    TerminalInfoApp(log_enabled=args.log).run()


if __name__ == "__main__":
    main()
