# DankOPS

DankOPS is a lightweight Python Discord bot with a local setup GUI and a unified scheduler.

## Important ToS and safety policy

This project is designed for Discord bot accounts created in the Developer Portal.

- Do not use user tokens
- Do not run self bots
- Do not bypass captcha systems
- Do not evade Discord limits or platform enforcement
- Use only in servers and channels where you have permission

If your usage violates Discord rules, this software is not appropriate for that use case.

## What this version includes

- Local setup GUI for token, owner id, channel ids, timing windows, and command profiles
- Unified command scheduler with randomized delays and optional break mode
- Slash command controls for start, stop, status, run once, and reload config
- JSON config persistence with sane defaults and normalization
- Single process Python runtime with low dependency footprint

## Project layout

- `bot.py`: launcher with `init`, `gui`, and `run` modes
- `dankops/config.py`: config dataclasses and persistence
- `dankops/engine.py`: scheduling and cooldown engine
- `dankops/discord_app.py`: Discord bot app and slash commands
- `dankops/gui.py`: Tkinter setup UI

## Requirements

- Python 3.11 or newer
- A Discord application bot token
- Bot invited to your server with message send permissions in target channel

## Setup

1. Create and activate a virtual environment
2. Install dependencies
3. Generate default config
4. Open setup GUI
5. Save config and run bot

Commands:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python bot.py init
python bot.py gui
python bot.py run
```

## Configuration notes

- `bot_token`: bot account token from Discord Developer Portal
- `owner_user_id`: only this user can control slash commands, `0` means no owner lock
- `target_channel_id`: channel where scheduled messages are sent
- `status_channel_id`: channel for status messages, falls back to target channel when empty
- `command_interval`: jitter between scheduled sends
- `commands`: profile map with `enabled`, `command`, `min_delay`, `max_delay`

The GUI writes to `config.json` by default.

## Slash commands

- `/farm_start`
- `/farm_stop`
- `/farm_status`
- `/farm_run_once command_name:<key>`
- `/farm_reload`

Command names for `farm_run_once` are the keys in the `commands` section of the config.

## Operational guidance

- Keep reasonable delays and avoid spam patterns
- Validate permissions in the target channel before enabling auto start
- Review logs in terminal output while testing
- Start with one or two enabled command profiles and scale gradually

## Disclaimer

You are responsible for compliance with Discord Terms of Service, server rules, and all applicable policies.
