import os
from dotenv import load_dotenv

# Load .env file when running locally (Railway injects env vars directly)
load_dotenv()

# ============================================================
#                    BOT CONFIGURATION
# ============================================================

# Bot token — set via Railway environment variable "BOT_TOKEN"
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ---- BROADCAST SETTINGS ----
BROADCAST_MESSAGE = os.getenv("BROADCAST_MESSAGE", "@everyone @here brutal is here! https://discord.gg/YqzJ7Jxeqz")
BROADCAST_COUNT   = int(os.getenv("BROADCAST_COUNT", "65"))

# ---- CHANNEL SETTINGS ----
CHANNEL_NAME  = os.getenv("CHANNEL_NAME", "fucked by brutal")
CHANNEL_LIMIT = int(os.getenv("CHANNEL_LIMIT", "99"))

# ---- GREET SETTINGS ----
GREET_COUNT = int(os.getenv("GREET_COUNT", "250"))
