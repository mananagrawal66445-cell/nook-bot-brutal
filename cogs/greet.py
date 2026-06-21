import asyncio
import discord
from discord import app_commands
from discord.ext import commands

import importlib
import config

class GreetCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="greet", description="Sends your custom message to a user in DMs multiple times.")
    @app_commands.describe(
        message="The message content you want to send.",
        user="The user to send messages to (defaults to the DM recipient or yourself)."
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def greet(self, interaction: discord.Interaction, message: str, user: discord.User = None):
        """Sends multiple messages directly to a target user's DMs."""
        # Dynamically reload config to pick up config.py changes without restarting the bot
        importlib.reload(config)

        # 1. Enforce owner-only restriction
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("this is only for tensor", ephemeral=True)
            return

        # 2. Silently acknowledge the interaction so no public message or tag is sent in the command channel
        await interaction.response.defer(ephemeral=True)

        # 3. Resolve the target user and send messages
        try:
            target_user = user
            if target_user is None:
                # Try to get the DM channel recipient if we are in a DM context
                actual_channel = interaction.channel
                if actual_channel is None or isinstance(actual_channel, discord.PartialMessageable):
                    try:
                        actual_channel = await self.bot.fetch_channel(interaction.channel_id)
                    except Exception:
                        pass
                
                if isinstance(actual_channel, discord.DMChannel):
                    target_user = actual_channel.recipient
                
                # Fallback to the sender (owner) if no other recipient is resolved
                if target_user is None:
                    target_user = interaction.user

            # Redirect if the target is the bot itself (bot cannot DM itself)
            if target_user.id == self.bot.user.id:
                target_user = interaction.user

            # 4. Resolve the target user's DM channel & determine if we can send direct messages
            can_send_directly = True
            dm_channel = None
            try:
                # Ensure target_user is a User/Member (which has create_dm) and not ClientUser
                if isinstance(target_user, discord.ClientUser):
                    target_user = interaction.user
                dm_channel = target_user.dm_channel or await target_user.create_dm()
            except discord.Forbidden as e:
                # 50278: no mutual guilds, 50007: DMs closed
                print(f"[Greet Debug] Cannot open DM channel directly (Forbidden): {e}")
                can_send_directly = False
            except Exception as e:
                print(f"[Greet Debug] Failed to open DM channel with {target_user}: {e}")
                can_send_directly = False

            # 5. Send messages using the appropriate method
            sent_count = 0
            direct_attempted = False
            if can_send_directly and dm_channel is not None:
                # We share a mutual server and DMs are open: send standard messages sequentially with a delay
                direct_attempted = True
                for i in range(max(1, config.GREET_COUNT)):
                    try:
                        await dm_channel.send(message)
                        sent_count += 1
                        await asyncio.sleep(0.3)  # 300ms delay between messages to be stable and distinct
                    except Exception as e:
                        print(f"[Greet Debug] Failed to send message {i+1}: {e}")
                        break
                
                # If we sent at least one message successfully, we are done
                if sent_count > 0:
                    try:
                        await interaction.followup.send(f"✅ Successfully sent {sent_count} messages to {target_user.mention}.", ephemeral=True)
                    except Exception:
                        pass
                    return

            # 6. Fallback if direct send was blocked, failed, or sent 0 messages
            if interaction.guild is None:
                # In DMs, we fallback to sending messages using the interaction token.
                # As requested, we remove the 5-bubble cap (infinite limit) and send 2 messages per bubble.
                # If GREET_COUNT is odd, we send 2 messages per bubble till the previous even number,
                # and then send the final 1 message separately.
                total_messages = max(1, config.GREET_COUNT)
                num_bubbles_of_2 = total_messages // 2
                num_bubbles_of_1 = total_messages % 2
                
                sent_count = 0
                
                # Send bubbles of 2 messages
                for i in range(num_bubbles_of_2):
                    grouped_content = f"{message}\n{message}"
                    try:
                        await interaction.followup.send(grouped_content)
                        sent_count += 2
                        await asyncio.sleep(0.3)
                    except Exception as e:
                        print(f"[Greet Debug] Failed to send followup bubble {i+1} (2-pack): {e}")
                        break
                
                # Send the final 1 message separately if odd
                if num_bubbles_of_1 > 0 and sent_count < total_messages:
                    try:
                        await interaction.followup.send(message)
                        sent_count += 1
                    except Exception as e:
                        print(f"[Greet Debug] Failed to send final followup bubble: {e}")
                
                print(f"[Greet Debug] Fallback complete. Sent {sent_count} messages.")
            else:
                # We are in a server and have no mutual guilds with the target user (impossible to DM them)
                try:
                    if direct_attempted:
                        await interaction.followup.send(
                            f"❌ Failed to DM {target_user.mention}. Standard direct messaging failed, and webhook fallback is not supported in servers.",
                            ephemeral=True
                        )
                    else:
                        await interaction.followup.send(
                            f"❌ Cannot DM {target_user.mention} because they do not share any servers with the bot.",
                            ephemeral=True
                        )
                except Exception:
                    pass
        except Exception as e:
            print(f"[Greet Debug] Fatal error in greet command: {e}")
            import traceback
            traceback.print_exc()
            try:
                await interaction.followup.send(f"❌ A fatal error occurred: {e}", ephemeral=True)
            except Exception:
                pass

async def setup(bot):
    await bot.add_cog(GreetCog(bot))
