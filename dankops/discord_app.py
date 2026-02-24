from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path

import aiohttp
import discord
from discord import app_commands, Webhook
from discord.ext import commands

from .config import AppConfig, load_config
from .engine import FarmEngine


class DankOpsBot(commands.Bot):
    def __init__(self, config_path: Path):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.messages = True
        super().__init__(command_prefix="!", intents=intents)
        self.config_path = config_path
        self.config: AppConfig = load_config(config_path)
        self.engine = FarmEngine(self.config, self._send_farm_message)
        self.log = logging.getLogger("dankops")

    async def setup_hook(self) -> None:
        self.tree.add_command(farm_start)
        self.tree.add_command(farm_stop)
        self.tree.add_command(farm_status)
        self.tree.add_command(farm_run_once)
        self.tree.add_command(farm_reload)
        self.tree.add_command(farm_create_webhook)
        # Try to register commands to the guild that contains the configured target channel
        guild_obj = None
        try:
            if self.config.target_channel_id:
                ch = await self.fetch_channel(self.config.target_channel_id)
                if getattr(ch, "guild", None) is not None:
                    guild_obj = discord.Object(id=ch.guild.id)
        except Exception:
            guild_obj = None

        if guild_obj is not None:
            try:
                await self.tree.sync(guild=guild_obj)
                self.log.info("Synced commands to guild %s", guild_obj.id)
            except Exception:
                await self.tree.sync()
                self.log.info("Falling back to global command sync")
        else:
            await self.tree.sync()

    async def on_ready(self) -> None:
        self.log.info("Connected as %s", self.user)
        await self.change_presence(status=self._presence_value())
        if self.config.auto_start:
            await self.engine.start()
            await self._post_status("Farm engine auto start enabled and running")

    async def close(self) -> None:
        await self.engine.stop()
        await super().close()

    async def _send_farm_message(self, content: str) -> None:
        # If a webhook URL is configured, post via webhook so the message is not from this bot account
        if getattr(self.config, "webhook_url", ""):
            url = self.config.webhook_url
            async with aiohttp.ClientSession() as session:
                webhook = Webhook.from_url(url, adapter=discord.AsyncWebhookAdapter(session))
                await webhook.send(content)
            return

        channel = self.get_channel(self.config.target_channel_id)
        if channel is None:
            channel = await self.fetch_channel(self.config.target_channel_id)
        if not isinstance(channel, discord.abc.Messageable):
            raise RuntimeError("Target channel is not messageable")
        await channel.send(content)

    async def _post_status(self, content: str) -> None:
        channel_id = self.config.status_channel_id or self.config.target_channel_id
        channel = self.get_channel(channel_id)
        if channel is None:
            channel = await self.fetch_channel(channel_id)
        if isinstance(channel, discord.abc.Messageable):
            await channel.send(content)

    def _presence_value(self) -> discord.Status:
        options = {
            "online": discord.Status.online,
            "idle": discord.Status.idle,
            "dnd": discord.Status.dnd,
            "invisible": discord.Status.invisible,
        }
        return options.get(self.config.presence.lower(), discord.Status.online)

    def is_owner(self, user_id: int) -> bool:
        return self.config.owner_user_id == 0 or self.config.owner_user_id == user_id


@app_commands.command(name="farm_create_webhook", description="Create a webhook in target channel and save to config")
async def farm_create_webhook(interaction: discord.Interaction) -> None:
    bot = interaction.client
    if not isinstance(bot, DankOpsBot):
        return
    if bot.config.target_channel_id == 0:
        await interaction.response.send_message("target_channel_id not set in config", ephemeral=True)
        return
    if not bot.is_owner(interaction.user.id):
        await interaction.response.send_message("Not authorized", ephemeral=True)
        return
    channel = bot.get_channel(bot.config.target_channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(bot.config.target_channel_id)
        except Exception:
            await interaction.response.send_message("Could not find target channel", ephemeral=True)
            return
    try:
        webhook = await channel.create_webhook(name="dankops-farm")
    except discord.Forbidden:
        await interaction.response.send_message("Bot lacks Manage Webhooks permission in target channel", ephemeral=True)
        return
    except Exception as exc:
        await interaction.response.send_message(f"Failed to create webhook: {exc}", ephemeral=True)
        return
    bot.config.webhook_url = webhook.url
    from .config import save_config

    save_config(bot.config_path, bot.config)
    await interaction.response.send_message("Webhook created and saved to config", ephemeral=True)




async def _check_owner(interaction: discord.Interaction) -> bool:
    bot = interaction.client
    if not isinstance(bot, DankOpsBot):
        return False
    return bot.is_owner(interaction.user.id)


@app_commands.command(name="farm_start", description="Start scheduler")
async def farm_start(interaction: discord.Interaction) -> None:
    bot = interaction.client
    if not isinstance(bot, DankOpsBot):
        return
    if not await _check_owner(interaction):
        await interaction.response.send_message("Not authorized", ephemeral=True)
        return
    started = await bot.engine.start()
    if started:
        await interaction.response.send_message("Scheduler started")
    else:
        await interaction.response.send_message("Scheduler is already running", ephemeral=True)


@app_commands.command(name="farm_stop", description="Stop scheduler")
async def farm_stop(interaction: discord.Interaction) -> None:
    bot = interaction.client
    if not isinstance(bot, DankOpsBot):
        return
    if not await _check_owner(interaction):
        await interaction.response.send_message("Not authorized", ephemeral=True)
        return
    stopped = await bot.engine.stop()
    if stopped:
        await interaction.response.send_message("Scheduler stopped")
    else:
        await interaction.response.send_message("Scheduler was not running", ephemeral=True)


@app_commands.command(name="farm_status", description="Show scheduler state")
async def farm_status(interaction: discord.Interaction) -> None:
    bot = interaction.client
    if not isinstance(bot, DankOpsBot):
        return
    if not await _check_owner(interaction):
        await interaction.response.send_message("Not authorized", ephemeral=True)
        return
    stats = bot.engine.get_stats()
    now = dt.datetime.utcnow().isoformat(timespec="seconds")
    lines = [
        f"UTC: {now}",
        f"running: {stats.running}",
        f"on_break: {stats.on_break}",
        f"sent_total: {stats.sent_total}",
    ]
    for name, count in sorted(stats.sent_by_command.items()):
        lines.append(f"{name}: {count}")
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


@app_commands.command(name="farm_run_once", description="Run one enabled command once")
@app_commands.describe(command_name="Configured command key")
async def farm_run_once(interaction: discord.Interaction, command_name: str) -> None:
    bot = interaction.client
    if not isinstance(bot, DankOpsBot):
        return
    if not await _check_owner(interaction):
        await interaction.response.send_message("Not authorized", ephemeral=True)
        return
    ok = await bot.engine.run_once(command_name)
    if ok:
        await interaction.response.send_message(f"Executed {command_name}")
    else:
        await interaction.response.send_message(f"Command {command_name} is missing or disabled", ephemeral=True)


@app_commands.command(name="farm_reload", description="Reload config from disk")
async def farm_reload(interaction: discord.Interaction) -> None:
    bot = interaction.client
    if not isinstance(bot, DankOpsBot):
        return
    if not await _check_owner(interaction):
        await interaction.response.send_message("Not authorized", ephemeral=True)
        return
    bot.config = load_config(bot.config_path)
    bot.engine.update_config(bot.config)
    await bot.change_presence(status=bot._presence_value())
    await interaction.response.send_message("Config reloaded")


@app_commands.command(name="farm_list_commands", description="List registered farm commands for the current guild")
async def farm_list_commands(interaction: discord.Interaction) -> None:
    bot = interaction.client
    if not isinstance(bot, DankOpsBot):
        return
    guild_obj = None
    try:
        ch = await bot.fetch_channel(bot.config.target_channel_id)
        if getattr(ch, "guild", None) is not None:
            guild_obj = discord.Object(id=ch.guild.id)
    except Exception:
        guild_obj = None

    try:
        if guild_obj is not None:
            cmds = await bot.tree.fetch_commands(guild=guild_obj)
        else:
            cmds = await bot.tree.fetch_commands()
    except Exception:
        cmds = []
    names = [c.name for c in cmds]
    await interaction.response.send_message("Registered commands: " + (", ".join(names) if names else "(none)"), ephemeral=True)


def run_bot(config_path: Path) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    cfg = load_config(config_path)
    if not cfg.bot_token.strip():
        raise RuntimeError("bot_token is empty in config")
    bot = DankOpsBot(config_path)
    bot.run(cfg.bot_token)


async def run_bot_async(config_path: Path) -> None:
    cfg = load_config(config_path)
    if not cfg.bot_token.strip():
        raise RuntimeError("bot_token is empty in config")
    bot = DankOpsBot(config_path)
    async with bot:
        await bot.start(cfg.bot_token)
