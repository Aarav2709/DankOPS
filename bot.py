from __future__ import annotations

import argparse
from pathlib import Path

from dankops.config import load_config
from dankops.gui import run_setup_gui


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="dankops", description="DankOPS unified setup and runtime")
    parser.add_argument("mode", choices=["gui", "run", "init"], help="gui opens setup UI, run starts bot, init writes default config")
    parser.add_argument("--config", default="config.json", help="Path to config file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = Path(args.config).resolve()
    if args.mode == "init":
        load_config(config_path)
        return
    if args.mode == "gui":
        run_setup_gui(config_path)
        return
    if args.mode == "run":
        from dankops.discord_app import run_bot

        run_bot(config_path)
        return


if __name__ == "__main__":
    main()
