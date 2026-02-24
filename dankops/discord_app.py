from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path

import aiohttp
import discord
from discord import app_commands, Webhook
from discord.ext import commands
from typing import Optional

from .config import AppConfig, load_config
from .engine import FarmEngine


@commands.command(name="farm_test")
async def farm_test_text(ctx: commands.Context, *, content: str) -> None:
    """Fallback text command to send a test command and wait for Dank Memer reply.

    Usage: `!farm_test pls fish`
    """
    bot = ctx.bot
    if not isinstance(bot, DankOpsBot):
        return
    if not bot.is_owner(getattr(ctx.author, "id", 0)):
        await ctx.send("Not authorized")
        return
    await ctx.send("Sending test command...")
    try:
        reply = await bot.send_and_wait_for_reply(content)
    except Exception as exc:
        await ctx.send(f"Error while sending: {exc}")
        return
    if reply is None:
        await ctx.send("No Dank Memer reply detected within timeout.")
    else:
        text = reply.content or "(embed/unknown content)"
        await ctx.send(f"Detected reply: {text}")


class DankOpsBot(commands.Bot):
    def __init__(self, config_path: Path, force_disable_message_content: bool = False):
        # Load configuration first so we can decide whether to request message_content intent
        self.config_path = config_path
        self.config: AppConfig = load_config(config_path)
        intents = discord.Intents.default()
        intents.guilds = True
        intents.messages = True
        # Only enable message_content intent when explicitly enabled in config
        use_msg_content = bool(getattr(self.config, "use_message_content_intent", False))
        if force_disable_message_content:
            use_msg_content = False
        intents.message_content = use_msg_content
        super().__init__(command_prefix="!", intents=intents)
        self.engine = FarmEngine(self.config, self._send_farm_message)
        self.log = logging.getLogger("dankops")

    async def setup_hook(self) -> None:
        self.tree.add_command(farm_start)
        self.tree.add_command(farm_stop)
        self.tree.add_command(farm_status)
        self.tree.add_command(farm_run_once)
        self.tree.add_command(farm_reload)
        self.tree.add_command(farm_create_webhook)
        # Register legacy prefix commands as a fallback when slash commands are unavailable
        try:
            self.add_command(farm_test_text)
        except Exception:
            self.log.exception("Failed to register text fallback commands")
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
        # Log registered commands for debugging
        try:
            guild_obj = None
            if self.config.target_channel_id:
                ch = await self.fetch_channel(self.config.target_channel_id)
                if getattr(ch, "guild", None) is not None:
                    guild_obj = discord.Object(id=ch.guild.id)
            if guild_obj is not None:
                cmds = await self.tree.fetch_commands(guild=guild_obj)
                self.log.info("Registered commands in guild %s: %s", guild_obj.id, [c.name for c in cmds])
            else:
                cmds = await self.tree.fetch_commands()
                self.log.info("Registered global commands: %s", [c.name for c in cmds])
        except Exception:
            self.log.exception("Failed to list registered commands")
        await self.change_presence(status=self._presence_value())
        if self.config.auto_start:
            await self.engine.start()
            self.log.info("Farm engine auto start enabled and running")

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
            self.log.info("Sent via webhook to %s: %s", url, content)
            return

        channel = self.get_channel(self.config.target_channel_id)
        if channel is None:
            channel = await self.fetch_channel(self.config.target_channel_id)
        if not isinstance(channel, discord.abc.Messageable):
            raise RuntimeError("Target channel is not messageable")
        await channel.send(content)
        self.log.info("Sent message to channel %s: %s", channel.id if getattr(channel,'id',None) else 'unknown', content)

    async def send_and_wait_for_reply(self, content: str, timeout: Optional[float] = None) -> Optional[discord.Message]:
        """Send a farm message (webhook or channel) and wait for Dank Memer reply.

        Returns the reply message if seen within timeout, otherwise None.
        """
        cfg = self.config
        timeout = timeout if timeout is not None else float(getattr(cfg, "wait_for_reply_timeout_seconds", 12.0))
        # Send
        await self._send_farm_message(content)

        # Wait for a message authored by Dank Memer in the same channel
        DANK_MEMER_ID = 270904126974590976

        def _check(m: discord.Message) -> bool:
            try:
                return (
                    m.author is not None
                    and getattr(m.author, "id", None) == DANK_MEMER_ID
                    and cfg.target_channel_id
                    and getattr(m.channel, "id", None) == cfg.target_channel_id
                )
            except Exception:
                return False

        try:
            msg = await self.wait_for("message", check=_check, timeout=timeout)
            self.log.info("Detected Dank Memer reply (id=%s): %s", getattr(msg, 'id', None), getattr(msg, 'content', None))
            return msg
        except Exception:
            self.log.info("No Dank Memer reply seen within %.1fs", timeout)
            return None

    async def on_message(self, message: discord.Message) -> None:
        # Log messages in target channel and detect Dank Memer replies
        try:
            # ignore our own messages
            if message.author and message.author.id == getattr(self.user, 'id', None):
                return

            if self.config.target_channel_id and message.channel.id == self.config.target_channel_id:
                author_id = getattr(message.author, 'id', None)
                content = getattr(message, 'content', '') or ''
                # also consider embeds text
                if not content and message.embeds:
                    try:
                        content = ' '.join(e.description or '' for e in message.embeds if getattr(e, 'description', None))
                    except Exception:
                        content = ''

                self.log.info("Incoming message in target channel from %s (%s): %s", getattr(message.author,'name',str(author_id)), author_id, content)
                # Dank Memer official ID
                if author_id == 270904126974590976:
                    self.log.info("Detected Dank Memer reply: %s", content)
        except Exception:
            self.log.exception("Error in on_message handler")
        finally:
            await super().on_message(message)

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


@app_commands.command(name="farm_test", description="Send a test command and wait for Dank Memer reply")
@app_commands.describe(content="Message content to send (e.g. 'pls fish')")
async def farm_test(interaction: discord.Interaction, content: str) -> None:
    bot = interaction.client
    if not isinstance(bot, DankOpsBot):
        return
    if not await _check_owner(interaction):
        await interaction.response.send_message("Not authorized", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    # Ensure target channel is set
    if bot.config.target_channel_id == 0:
        await interaction.followup.send("target_channel_id not set in config", ephemeral=True)
        return
    # Send and wait
    try:
        reply = await bot.send_and_wait_for_reply(content)
    except Exception as exc:
        await interaction.followup.send(f"Error while sending: {exc}", ephemeral=True)
        return
    if reply is None:
        await interaction.followup.send("No Dank Memer reply detected within timeout.", ephemeral=True)
    else:
        text = reply.content or "(embed/unknown content)"
        await interaction.followup.send(f"Detected reply: {text}", ephemeral=True)


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
    # Ensure logs directory exists and write logs to file for GUI tailing
    import os
    os.makedirs("logs", exist_ok=True)
    fh = logging.FileHandler("logs/dankops.log", encoding="utf-8")
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    fh.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    # avoid duplicate handlers if present
    if not any(isinstance(h, logging.FileHandler) and h.baseFilename.endswith("dankops.log") for h in root_logger.handlers if hasattr(h, 'baseFilename')):
        root_logger.addHandler(fh)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    cfg = load_config(config_path)
    if not cfg.bot_token.strip():
        raise RuntimeError("bot_token is empty in config")
    bot = DankOpsBot(config_path)
    try:
        bot.run(cfg.bot_token)
    except discord.errors.PrivilegedIntentsRequired:
        msg = (
            "Privileged Gateway Intents are required by the bot configuration. "
            "Attempting fallback by disabling message content intent and restarting. "
            "If you need message content access, enable 'Message Content Intent' in the Discord Developer Portal for your application."
        )
        logging.getLogger("dankops").exception(msg)
        print(msg)
        # Retry once without requesting message content intent
        bot = DankOpsBot(config_path, force_disable_message_content=True)
        try:
            bot.run(cfg.bot_token)
        except Exception:
            logging.getLogger("dankops").exception("Fallback run failed")
            raise


async def run_bot_async(config_path: Path) -> None:
    cfg = load_config(config_path)
    if not cfg.bot_token.strip():
        raise RuntimeError("bot_token is empty in config")
    bot = DankOpsBot(config_path)
    try:
        async with bot:
            await bot.start(cfg.bot_token)
    except discord.errors.PrivilegedIntentsRequired:
        msg = (
            "Privileged Gateway Intents are required by the bot configuration. "
            "Retrying without message content intent."
        )
        logging.getLogger("dankops").exception(msg)
        print(msg)
        bot = DankOpsBot(config_path, force_disable_message_content=True)
        async with bot:
            await bot.start(cfg.bot_token)
