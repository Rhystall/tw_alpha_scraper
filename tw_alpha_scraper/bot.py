from __future__ import annotations

from typing import Any

from .models import AdminActor
from .permissions import AccessPolicy
from .service import AlphaMonitorService


class DiscordAdminBot:
    def __init__(self, service: AlphaMonitorService) -> None:
        try:
            import discord
            from discord import app_commands
            from discord.ext import commands
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "discord.py is not installed. Install dependencies before enabling the Discord bot."
            ) from exc

        self.discord = discord
        self.app_commands = app_commands
        self.commands = commands
        self.service = service
        self.policy = AccessPolicy(
            admin_channel_id=service.config.discord.admin_channel_id,
            admin_role_ids=service.config.discord.admin_role_ids,
        )

        intents = discord.Intents.none()
        intents.guilds = True
        self.bot = commands.Bot(command_prefix="!", intents=intents)
        self.tree = self.bot.tree
        self._register_commands()
        self.bot.setup_hook = self._setup_hook  # type: ignore[method-assign]

    async def _setup_hook(self) -> None:
        guild_id = self.service.config.discord.guild_id
        if guild_id:
            print(f"SYNCING COMMANDS TO GUILD: {guild_id}"); guild = self.discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    def _register_commands(self) -> None:
        app_commands = self.app_commands

        @self.tree.command(name="status", description="Show monitor and worker health.")
        async def status(interaction: Any) -> None:
            if not await self._authorize(interaction):
                return
            await interaction.response.defer(ephemeral=True)
            message = await self.service.status_text()
            await interaction.followup.send(f"```text\n{message}\n```", ephemeral=True)

        @self.tree.command(name="pause", description="Pause the monitor loop.")
        async def pause(interaction: Any) -> None:
            if not await self._authorize(interaction):
                return
            result = await self.service.pause(actor=self._actor_from_interaction(interaction))
            await interaction.response.send_message(result.message, ephemeral=True)

        @self.tree.command(name="resume", description="Resume the monitor loop.")
        async def resume(interaction: Any) -> None:
            if not await self._authorize(interaction):
                return
            result = await self.service.resume(actor=self._actor_from_interaction(interaction))
            await interaction.response.send_message(result.message, ephemeral=True)

        targets = app_commands.Group(name="targets", description="Manage monitored targets.")

        @targets.command(name="list", description="List all monitored targets.")
        async def target_list(interaction: Any) -> None:
            if not await self._authorize(interaction):
                return
            rows = self.service.storage.list_targets()
            if not rows:
                message = "No targets configured."
            else:
                lines = []
                for target in rows:
                    status = "active" if target.active else "inactive"
                    lines.append(
                        f"- {target.display_label()} (`{target.user_id}`) [{status}] "
                        f"last_success={target.last_success_at}"
                    )
                message = "\n".join(lines)
            await interaction.response.send_message(message, ephemeral=True)

        @targets.command(name="add", description="Add a target by user ID or username.")
        @app_commands.describe(identifier="Twitter user ID or @username", label="Optional label")
        async def target_add(
            interaction: Any,
            identifier: str,
            label: str | None = None,
        ) -> None:
            if not await self._authorize(interaction):
                return
            await interaction.response.defer(ephemeral=True)
            result = await self.service.add_target(
                identifier=identifier,
                label=label,
                actor=self._actor_from_interaction(interaction),
            )
            await interaction.followup.send(result.message, ephemeral=True)

        @targets.command(name="remove", description="Remove a target by user ID, username, or label.")
        async def target_remove(interaction: Any, identifier: str) -> None:
            if not await self._authorize(interaction):
                return
            result = await self.service.remove_target(
                identifier=identifier,
                actor=self._actor_from_interaction(interaction),
            )
            await interaction.response.send_message(result.message, ephemeral=True)

        self.tree.add_command(targets)

    async def _authorize(self, interaction: Any) -> bool:
        user = interaction.user
        channel_id = getattr(interaction.channel, "id", None)
        role_ids = [role.id for role in getattr(user, "roles", [])]
        manage_guild = bool(getattr(getattr(user, "guild_permissions", None), "manage_guild", False))
        if self.policy.is_allowed(channel_id, role_ids, manage_guild):
            return True
        await interaction.response.send_message("Not authorized for this command.", ephemeral=True)
        return False

    def _actor_from_interaction(self, interaction: Any) -> AdminActor:
        user = interaction.user
        return AdminActor(actor_id=str(user.id), actor_name=getattr(user, "display_name", str(user.id)))

    async def start(self) -> None:
        token = self.service.config.discord.bot_token
        if not token:
            raise RuntimeError("DISCORD_BOT_TOKEN is required to run the Discord bot.")
        await self.bot.start(token)

    async def close(self) -> None:
        await self.bot.close()
