import asyncio
import datetime
import json
import os
import discord
from discord import app_commands
from discord.ext import commands

class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.is_banning = False
        self.cancel_ban = False
        self.ban_task = None
        self.ban_active_tasks = set()

    def start_tracked_task(self, coro):
        """Starts a background ban task and tracks it for instant cancellation."""
        task = asyncio.create_task(coro)
        self.ban_active_tasks.add(task)
        task.add_done_callback(self.ban_active_tasks.discard)
        return task

    async def ban_member_safe(self, member: discord.Member):
        """Bans a single member safely, catching all exceptions."""
        try:
            await member.ban(
                delete_message_days=0,
                reason="Mass ban command executed."
            )
            print(f"Banned: {member.name} ({member.id})")
            return True
        except asyncio.CancelledError:
            raise
        except discord.Forbidden:
            print(f"Cannot ban {member.name}: Missing permissions or higher role.")
            return False
        except discord.HTTPException as e:
            if e.status == 429:
                # Rate limited - wait and retry
                await asyncio.sleep(1.0)
                try:
                    await member.ban(delete_message_days=0, reason="Mass ban command executed.")
                    return True
                except Exception:
                    return False
            print(f"HTTP error banning {member.name}: {e}")
            return False
        except Exception as e:
            print(f"Failed to ban {member.name}: {e}")
            return False

    def is_bannable(self, member: discord.Member, guild: discord.Guild, me: discord.Member) -> bool:
        """Check if the bot is allowed to ban this member."""
        # Cannot ban the bot itself
        if member.id == me.id:
            return False
        # Cannot ban the server owner
        if member.id == guild.owner_id:
            return False
        # Cannot ban members whose top role is equal or higher than the bot's top role
        if me.top_role <= member.top_role:
            return False
        return True

    @commands.command(name=".massb")
    @commands.has_permissions(administrator=True)
    async def massb(self, ctx):
        """Bans ALL members the bot can ban in the server simultaneously."""
        if self.is_banning:
            await ctx.send("⚠️ A mass ban is already in progress! Use `nexus4all.stopban` to abort.")
            return

        self.is_banning = True
        self.cancel_ban = False
        self.ban_task = asyncio.current_task()
        self.ban_active_tasks.clear()

        guild = ctx.guild
        me = guild.me

        try:
            # Filter members that the bot is actually allowed to ban
            # guild.members is populated automatically since intents.members is enabled in main.py
            bannable_members = [
                m for m in guild.members
                if self.is_bannable(m, guild, me)
            ]

            if not bannable_members:
                await ctx.send("❌ No members found that the bot can ban.")
                return

            await ctx.send(
                f"🔨 Starting mass ban on **{len(bannable_members)}** members..."
            )

            # Fire all ban requests simultaneously in the background
            ban_tasks = [
                self.start_tracked_task(self.ban_member_safe(m))
                for m in bannable_members
            ]

            results = await asyncio.gather(*ban_tasks, return_exceptions=True)

            successful = sum(1 for r in results if r is True)
            failed = len(results) - successful

            # Try to send completion message somewhere
            # ctx.channel may still exist if bot didn't have manage channels permission
            try:
                await ctx.send(
                    f"⚡ **Mass Ban Complete!**\n"
                    f"✅ Successfully banned: **{successful}** members.\n"
                    f"❌ Failed/Skipped: **{failed}** members."
                )
            except Exception:
                pass

        except asyncio.CancelledError:
            for task in list(self.ban_active_tasks):
                task.cancel()
            try:
                await ctx.send("🛑 **Mass ban aborted!**")
            except Exception:
                pass
        finally:
            self.is_banning = False
            self.ban_task = None
            self.ban_active_tasks.clear()

    @commands.command(name=".stopban")
    @commands.has_permissions(administrator=True)
    async def stopban(self, ctx):
        """Instantly stops an active mass ban operation."""
        if not self.is_banning:
            await ctx.send("❌ No active mass ban is running.")
            return

        self.cancel_ban = True

        if self.ban_task and not self.ban_task.done():
            self.ban_task.cancel()

        for task in list(self.ban_active_tasks):
            if not task.done():
                task.cancel()

        await ctx.send("🛑 **Mass ban terminated instantly.**")

    @app_commands.command(name="kick", description="Kicks a member from the server.")
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = None):
        guild = interaction.guild
        author = interaction.user
        me = guild.me

        # Check permissions
        if not author.guild_permissions.kick_members:
            await interaction.response.send_message("❌ You do not have permission to kick members.", ephemeral=True)
            return
        if not me.guild_permissions.kick_members:
            await interaction.response.send_message("❌ I do not have permission to kick members.", ephemeral=True)
            return

        # Check role hierarchy
        if member.id == author.id:
            await interaction.response.send_message("❌ You cannot kick yourself.", ephemeral=True)
            return
        if member.id == guild.owner_id:
            await interaction.response.send_message("❌ You cannot kick the server owner.", ephemeral=True)
            return
        if author.id != guild.owner_id and author.top_role <= member.top_role:
            await interaction.response.send_message("❌ You cannot kick a member with a higher or equal top role.", ephemeral=True)
            return
        if me.top_role <= member.top_role:
            await interaction.response.send_message("❌ I cannot kick this member because their top role is higher than or equal to mine.", ephemeral=True)
            return

        try:
            await member.kick(reason=reason)
            await interaction.response.send_message(f"✅ **{member.name}** has been kicked.\nReason: {reason or 'No reason provided.'}")
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to kick member: {e}", ephemeral=True)

    @app_commands.command(name="ban", description="Bans a member from the server.")
    @app_commands.choices(delete_messages=[
        app_commands.Choice(name="Don't Delete", value=0),
        app_commands.Choice(name="Previous 24 Hours", value=1),
        app_commands.Choice(name="Previous 7 Days", value=7)
    ])
    async def ban(self, interaction: discord.Interaction, member: discord.Member, delete_messages: int = 0, reason: str = None):
        guild = interaction.guild
        author = interaction.user
        me = guild.me

        # Check permissions
        if not author.guild_permissions.ban_members:
            await interaction.response.send_message("❌ You do not have permission to ban members.", ephemeral=True)
            return
        if not me.guild_permissions.ban_members:
            await interaction.response.send_message("❌ I do not have permission to ban members.", ephemeral=True)
            return

        # Check role hierarchy
        if member.id == author.id:
            await interaction.response.send_message("❌ You cannot ban yourself.", ephemeral=True)
            return
        if member.id == guild.owner_id:
            await interaction.response.send_message("❌ You cannot ban the server owner.", ephemeral=True)
            return
        if author.id != guild.owner_id and author.top_role <= member.top_role:
            await interaction.response.send_message("❌ You cannot ban a member with a higher or equal top role.", ephemeral=True)
            return
        if me.top_role <= member.top_role:
            await interaction.response.send_message("❌ I cannot ban this member because their top role is higher than or equal to mine.", ephemeral=True)
            return

        try:
            await member.ban(delete_message_days=delete_messages, reason=reason)
            await interaction.response.send_message(f"✅ **{member.name}** has been banned.\nReason: {reason or 'No reason provided.'}")
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to ban member: {e}", ephemeral=True)

    @app_commands.command(name="timeout", description="Mutes/times out a member.")
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = None):
        guild = interaction.guild
        author = interaction.user
        me = guild.me

        # Check permissions (moderate_members is required for timeouts)
        if not author.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You do not have permission to timeout members.", ephemeral=True)
            return
        if not me.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ I do not have permission to timeout members.", ephemeral=True)
            return

        # Check role hierarchy
        if member.id == author.id:
            await interaction.response.send_message("❌ You cannot timeout yourself.", ephemeral=True)
            return
        if member.id == guild.owner_id:
            await interaction.response.send_message("❌ You cannot timeout the server owner.", ephemeral=True)
            return
        if author.id != guild.owner_id and author.top_role <= member.top_role:
            await interaction.response.send_message("❌ You cannot timeout a member with a higher or equal top role.", ephemeral=True)
            return
        if me.top_role <= member.top_role:
            await interaction.response.send_message("❌ I cannot timeout this member because their top role is higher than or equal to mine.", ephemeral=True)
            return

        if minutes <= 0:
            await interaction.response.send_message("❌ Timeout duration must be greater than 0 minutes.", ephemeral=True)
            return

        try:
            duration = datetime.timedelta(minutes=minutes)
            await member.timeout(duration, reason=reason)
            await interaction.response.send_message(f"✅ **{member.name}** has been timed out for {minutes} minutes.\nReason: {reason or 'No reason provided.'}")
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to timeout member: {e}", ephemeral=True)

    @app_commands.command(name="unban", description="Unbans a user by their User ID.")
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = None):
        guild = interaction.guild
        author = interaction.user
        me = guild.me

        # Check permissions
        if not author.guild_permissions.ban_members:
            await interaction.response.send_message("❌ You do not have permission to unban members.", ephemeral=True)
            return
        if not me.guild_permissions.ban_members:
            await interaction.response.send_message("❌ I do not have permission to unban members.", ephemeral=True)
            return

        try:
            user = await self.bot.fetch_user(int(user_id))
            await guild.unban(user, reason=reason)
            await interaction.response.send_message(f"✅ **{user.name}** has been unbanned.\nReason: {reason or 'No reason provided.'}")
        except ValueError:
            await interaction.response.send_message("❌ Invalid User ID format. Please make sure to enter a numeric ID.", ephemeral=True)
        except discord.NotFound:
            await interaction.response.send_message("❌ User not found or not currently banned.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to unban user: {e}", ephemeral=True)

    @app_commands.command(name="purge", description="Deletes a specified number of messages from this channel.")
    async def purge(self, interaction: discord.Interaction, amount: int, member: discord.Member = None):
        guild = interaction.guild
        author = interaction.user
        me = guild.me
        channel = interaction.channel

        # Check permissions
        if not author.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You do not have permission to manage messages.", ephemeral=True)
            return
        if not me.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ I do not have permission to manage messages.", ephemeral=True)
            return

        if amount <= 0:
            await interaction.response.send_message("❌ Please specify an amount greater than 0.", ephemeral=True)
            return
        if amount > 100:
            amount = 100  # Cap it at 100 for safety

        # Defer response as it can take more than 3 seconds
        await interaction.response.defer(ephemeral=True)

        try:
            def check(m):
                return member is None or m.author.id == member.id

            deleted = await channel.purge(limit=amount, check=check)
            await interaction.followup.send(f"✅ Successfully deleted **{len(deleted)}** messages.")
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to purge messages: {e}")

    def load_warnings(self):
        if not os.path.exists("warnings.json"):
            return {}
        try:
            with open("warnings.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_warnings(self, data):
        try:
            with open("warnings.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Failed to save warnings: {e}")

    @app_commands.command(name="warn", description="Warns a member and logs it.")
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        guild = interaction.guild
        author = interaction.user

        if not author.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You do not have permission to warn members.", ephemeral=True)
            return

        if member.id == author.id:
            await interaction.response.send_message("❌ You cannot warn yourself.", ephemeral=True)
            return
        if member.bot:
            await interaction.response.send_message("❌ You cannot warn bots.", ephemeral=True)
            return

        # Load warnings
        warnings = self.load_warnings()
        guild_id_str = str(guild.id)
        member_id_str = str(member.id)

        if guild_id_str not in warnings:
            warnings[guild_id_str] = {}
        if member_id_str not in warnings[guild_id_str]:
            warnings[guild_id_str][member_id_str] = []

        warning_entry = {
            "reason": reason,
            "warned_by": author.name,
            "warned_by_id": author.id,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        warnings[guild_id_str][member_id_str].append(warning_entry)
        self.save_warnings(warnings)

        # Try to DM the user
        try:
            await member.send(f"⚠️ You have been warned in **{guild.name}**.\nReason: {reason}")
            dm_status = "DM sent successfully."
        except Exception:
            dm_status = "Could not DM user (DMs closed)."

        warn_count = len(warnings[guild_id_str][member_id_str])
        await interaction.response.send_message(
            f"✅ **{member.name}** has been warned (Warning #{warn_count}).\nReason: {reason}\n*{dm_status}*"
        )

    @app_commands.command(name="warnings", description="Shows the warnings of a member.")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        guild = interaction.guild
        author = interaction.user

        if not author.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You do not have permission to view warnings.", ephemeral=True)
            return

        warnings = self.load_warnings()
        guild_id_str = str(guild.id)
        member_id_str = str(member.id)

        user_warns = warnings.get(guild_id_str, {}).get(member_id_str, [])

        if not user_warns:
            await interaction.response.send_message(f"ℹ️ **{member.name}** has 0 warnings.")
            return

        embed = discord.Embed(
            title=f"Warnings for {member.name}",
            color=discord.Color.orange()
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        for idx, warn in enumerate(user_warns, start=1):
            timestamp_str = warn.get("timestamp", "")
            try:
                dt = datetime.datetime.fromisoformat(timestamp_str)
                time_display = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                time_display = timestamp_str

            embed.add_field(
                name=f"Warning #{idx}",
                value=f"**Reason:** {warn['reason']}\n**By:** {warn['warned_by']} (ID: {warn['warned_by_id']})\n**Date:** {time_display}",
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="clearwarns", description="Clears all warnings for a member.")
    async def clearwarns(self, interaction: discord.Interaction, member: discord.Member):
        guild = interaction.guild
        author = interaction.user

        if not author.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You do not have permission to clear warnings.", ephemeral=True)
            return

        warnings = self.load_warnings()
        guild_id_str = str(guild.id)
        member_id_str = str(member.id)

        if guild_id_str in warnings and member_id_str in warnings[guild_id_str]:
            del warnings[guild_id_str][member_id_str]
            self.save_warnings(warnings)
            await interaction.response.send_message(f"✅ Cleared all warnings for **{member.name}**.")
        else:
            await interaction.response.send_message(f"ℹ️ **{member.name}** had no warnings to clear.")

    @app_commands.command(name="slowmode", description="Changes the slowmode duration of the channel.")
    async def slowmode(self, interaction: discord.Interaction, seconds: int):
        guild = interaction.guild
        author = interaction.user
        me = guild.me
        channel = interaction.channel

        if not author.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ You do not have permission to manage channels.", ephemeral=True)
            return
        if not me.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ I do not have permission to manage channels.", ephemeral=True)
            return

        if seconds < 0 or seconds > 21600:
            await interaction.response.send_message("❌ Slowmode must be between 0 and 21600 seconds (6 hours).", ephemeral=True)
            return

        try:
            await channel.edit(slowmode_delay=seconds)
            if seconds == 0:
                await interaction.response.send_message("✅ Slowmode has been disabled for this channel.")
            else:
                await interaction.response.send_message(f"✅ Slowmode set to **{seconds}** seconds.")
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to set slowmode: {e}", ephemeral=True)

    @app_commands.command(name="lock", description="Locks the current channel (prevents members from sending messages).")
    async def lock(self, interaction: discord.Interaction, reason: str = None):
        guild = interaction.guild
        author = interaction.user
        me = guild.me
        channel = interaction.channel

        if not author.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ You do not have permission to manage channel permissions.", ephemeral=True)
            return
        if not me.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ I do not have permission to manage channel permissions.", ephemeral=True)
            return

        try:
            everyone_role = guild.default_role
            await channel.set_permissions(everyone_role, send_messages=False, reason=reason)
            await interaction.response.send_message(f"🔒 **Channel Locked.**\nReason: {reason or 'No reason provided.'}")
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to lock channel: {e}", ephemeral=True)

    @app_commands.command(name="unlock", description="Unlocks the current channel.")
    async def unlock(self, interaction: discord.Interaction):
        guild = interaction.guild
        author = interaction.user
        me = guild.me
        channel = interaction.channel

        if not author.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ You do not have permission to manage channel permissions.", ephemeral=True)
            return
        if not me.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ I do not have permission to manage channel permissions.", ephemeral=True)
            return

        try:
            everyone_role = guild.default_role
            await channel.set_permissions(everyone_role, send_messages=None)
            await interaction.response.send_message("🔓 **Channel Unlocked.**")
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to unlock channel: {e}", ephemeral=True)

    @app_commands.command(name="userinfo", description="Displays detailed information about a member.")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        if member is None:
            member = interaction.user

        guild = interaction.guild
        roles = [role.mention for role in member.roles if role != guild.default_role]
        roles_str = ", ".join(roles) if roles else "None"

        embed = discord.Embed(
            title=f"User Info - {member.name}",
            color=member.color
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Username", value=member.name, inline=True)
        embed.add_field(name="ID", value=member.id, inline=True)
        embed.add_field(name="Nickname", value=member.nick or "None", inline=True)

        created_time = member.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        joined_time = member.joined_at.strftime("%Y-%m-%d %H:%M:%S UTC") if member.joined_at else "Unknown"

        embed.add_field(name="Account Created", value=created_time, inline=False)
        embed.add_field(name="Joined Server", value=joined_time, inline=False)
        embed.add_field(name=f"Roles ({len(roles)})", value=roles_str, inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="Displays detailed information about the server.")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild

        embed = discord.Embed(
            title=f"Server Info - {guild.name}",
            color=discord.Color.blue()
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        owner = await guild.fetch_member(guild.owner_id) if guild.owner_id else None
        owner_name = f"{owner.name} (ID: {guild.owner_id})" if owner else f"ID: {guild.owner_id}"

        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)

        embed.add_field(name="Owner", value=owner_name, inline=False)
        embed.add_field(name="Server ID", value=guild.id, inline=True)
        embed.add_field(name="Created At", value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"), inline=True)
        embed.add_field(name="Member Count", value=guild.member_count, inline=True)
        embed.add_field(name="Text Channels", value=text_channels, inline=True)
        embed.add_field(name="Voice Channels", value=voice_channels, inline=True)
        embed.add_field(name="Categories", value=categories, inline=True)
        embed.add_field(name="Roles Count", value=len(guild.roles), inline=True)
        embed.add_field(name="Boost Tier / Count", value=f"Tier {guild.premium_tier} ({guild.premium_subscription_count} boosts)", inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ping", description="Checks the bot's latency/ping.")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"🏓 **Pong!** Latency: **{latency}ms**")

async def setup(bot):
    await bot.add_cog(ModerationCog(bot))
