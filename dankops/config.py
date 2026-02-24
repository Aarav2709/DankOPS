from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CooldownWindow:
    min_seconds: float = 2.0
    max_seconds: float = 5.0


@dataclass
class CommandProfile:
    enabled: bool
    command: str
    min_delay: float
    max_delay: float


@dataclass
class AppConfig:
    bot_token: str = ""
    owner_user_id: int = 0
    target_channel_id: int = 0
    status_channel_id: int = 0
    presence: str = "online"
    webhook_url: str = ""
    auto_start: bool = False
    break_mode: bool = True
    break_after_min_minutes: float = 45.0
    break_after_max_minutes: float = 120.0
    break_duration_min_minutes: float = 10.0
    break_duration_max_minutes: float = 25.0
    command_interval: CooldownWindow = field(default_factory=CooldownWindow)
    commands: dict[str, CommandProfile] = field(default_factory=dict)
    ui_dark_mode: bool = False
    use_message_content_intent: bool = False
    # If enabled, after sending a command the bot will wait for a Dank Memer reply
    wait_for_reply_enabled: bool = False
    wait_for_reply_timeout_seconds: float = 12.0


def default_commands() -> dict[str, CommandProfile]:
    return {
        "beg": CommandProfile(True, "pls beg", 45, 60),
        "dig": CommandProfile(True, "pls dig", 35, 50),
        "fish": CommandProfile(True, "pls fish", 35, 50),
        "hunt": CommandProfile(True, "pls hunt", 35, 50),
        "daily": CommandProfile(True, "pls daily", 86400, 90000),
        "monthly": CommandProfile(False, "pls monthly", 2592000, 2629800),
        "search": CommandProfile(False, "pls search", 40, 60),
        "crime": CommandProfile(False, "pls crime", 45, 70),
        "postmemes": CommandProfile(False, "pls postmemes", 40, 60),
        "highlow": CommandProfile(False, "pls hl", 25, 35),
        "deposit": CommandProfile(False, "pls deposit all", 60, 90),
    }


def default_config() -> AppConfig:
    return AppConfig(commands=default_commands())


def _profile_from_any(name: str, raw: dict[str, Any]) -> CommandProfile:
    base = default_commands().get(name, CommandProfile(False, f"pls {name}", 30, 45))
    return CommandProfile(
        enabled=bool(raw.get("enabled", base.enabled)),
        command=str(raw.get("command", base.command)),
        min_delay=float(raw.get("min_delay", base.min_delay)),
        max_delay=float(raw.get("max_delay", base.max_delay)),
    )


def _window_from_any(raw: dict[str, Any]) -> CooldownWindow:
    base = CooldownWindow()
    return CooldownWindow(
        min_seconds=float(raw.get("min_seconds", base.min_seconds)),
        max_seconds=float(raw.get("max_seconds", base.max_seconds)),
    )


def _config_from_any(raw: dict[str, Any]) -> AppConfig:
    base = default_config()
    commands_raw = raw.get("commands", {}) if isinstance(raw.get("commands", {}), dict) else {}
    commands = default_commands()
    for name, value in commands_raw.items():
        if isinstance(value, dict):
            commands[name] = _profile_from_any(name, value)
    config = AppConfig(
        bot_token=str(raw.get("bot_token", base.bot_token)),
        owner_user_id=int(raw.get("owner_user_id", base.owner_user_id) or 0),
        target_channel_id=int(raw.get("target_channel_id", base.target_channel_id) or 0),
        status_channel_id=int(raw.get("status_channel_id", base.status_channel_id) or 0),
        presence=str(raw.get("presence", base.presence)),
        webhook_url=str(raw.get("webhook_url", base.webhook_url)),
        auto_start=bool(raw.get("auto_start", base.auto_start)),
        break_mode=bool(raw.get("break_mode", base.break_mode)),
        break_after_min_minutes=float(raw.get("break_after_min_minutes", base.break_after_min_minutes)),
        break_after_max_minutes=float(raw.get("break_after_max_minutes", base.break_after_max_minutes)),
        break_duration_min_minutes=float(raw.get("break_duration_min_minutes", base.break_duration_min_minutes)),
        break_duration_max_minutes=float(raw.get("break_duration_max_minutes", base.break_duration_max_minutes)),
        command_interval=_window_from_any(raw.get("command_interval", {})),
        commands=commands,
        ui_dark_mode=bool(raw.get("ui_dark_mode", base.ui_dark_mode)),
        use_message_content_intent=bool(raw.get("use_message_content_intent", base.use_message_content_intent)),
        wait_for_reply_enabled=bool(raw.get("wait_for_reply_enabled", base.wait_for_reply_enabled)),
        wait_for_reply_timeout_seconds=float(raw.get("wait_for_reply_timeout_seconds", base.wait_for_reply_timeout_seconds)),
    )
    return normalize_config(config)


def normalize_config(config: AppConfig) -> AppConfig:
    if config.command_interval.max_seconds < config.command_interval.min_seconds:
        config.command_interval.max_seconds = config.command_interval.min_seconds
    if config.break_after_max_minutes < config.break_after_min_minutes:
        config.break_after_max_minutes = config.break_after_min_minutes
    if config.break_duration_max_minutes < config.break_duration_min_minutes:
        config.break_duration_max_minutes = config.break_duration_min_minutes
    for profile in config.commands.values():
        if profile.max_delay < profile.min_delay:
            profile.max_delay = profile.min_delay
    return config


def config_to_dict(config: AppConfig) -> dict[str, Any]:
    return asdict(config)


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        cfg = default_config()
        save_config(path, cfg)
        return cfg
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        cfg = default_config()
        save_config(path, cfg)
        return cfg
    cfg = _config_from_any(raw)
    save_config(path, cfg)
    return cfg


def save_config(path: Path, config: AppConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = config_to_dict(normalize_config(config))
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
