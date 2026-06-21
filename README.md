# Modular Discord Rebuild & Broadcast Bot

This is a modular Discord bot built using python's `discord.py` v2.0+ library and structured using **Cogs** for clean, organized command management.

> [!CAUTION]
> **WARNING: DESTRUCTIVE ACTION**
> The `nexus4all.tensor` command will permanently delete all existing channels, categories, and voice channels in the server. This action is irreversible. Use this bot ONLY in temporary test servers.

## Project Structure

```
discord_bot/
├── config.py           # Configuration variables (Token, message, limits, channel name)
├── main.py             # Main entry point (Bot subclass, setup_hook, event loops)
├── cogs/
│   ├── __init__.py     # Package initialization
│   ├── broadcast.py    # Cog containing the rebuild and broadcast commands (.tensor and .stop)
│   └── owner.py        # Cog containing owner-only commands (.eval)
├── README.md           # This setup and usage guide
└── requirements.txt     # Python package dependencies
```

## Prerequisites

1. **Python 3.8+** must be installed.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Setup & Configuration

1. **Get a Bot Token**:
   - Go to the [Discord Developer Portal](https://discord.com/developers/applications).
   - Create an Application, then go to the **Bot** tab and add a bot.
   - Copy the bot **Token**.
   - Under the **Privileged Gateway Intents** section, enable **Message Content Intent** (required so the bot can read commands).
   - Save changes.

2. **Configure the Bot Settings**:
   Open **[config.py](file:///C:/Users/manan/.gemini/antigravity/scratch/discord_bot/config.py)** to customize the bot behavior:
   * `BROADCAST_MESSAGE`: The message to spam inside the new channels.
   * `BROADCAST_COUNT`: The number of times to send the message in each channel (e.g. `3`).
   * `CHANNEL_NAME`: The base name for the new channels (e.g. `"nexus"` will create `nexus-1`, `nexus-2`, etc.).
   * `CHANNEL_LIMIT`: The number of new channels to create (e.g. `5` or `10`).
   * `BOT_TOKEN`: Paste your bot's token here.

3. **Invite the Bot**:
   - Go to the **OAuth2** tab -> **URL Generator**.
   - Select the `bot` scope.
   - Under bot permissions, select **Administrator** (necessary since it deletes/creates channels and manages permissions).
   - Copy the generated URL and open it in a browser to invite the bot.

## Running the Bot

Start the bot by running:
```bash
python main.py
```

## Commands

### 1. Rebuild & Broadcast
* **Command**: `nexus4all.tensor`
* **Access**: Server Administrators only (`@commands.has_permissions(administrator=True)`).
* **Function**: 
  1. Creates the first new channel (e.g. `nexus-1`).
  2. Deletes all other old channels, voice channels, and categories in the guild.
  3. Creates the remaining channels up to your `CHANNEL_LIMIT`.
  4. Broadcasts `BROADCAST_MESSAGE` concurrently to all new channels `BROADCAST_COUNT` times.
* **Important Note**: Since the command channel is deleted during the process, the final status report will be sent to the first new channel (`#<channel_name>-1`).

### 2. Stop Process
* **Command**: `nexus4all.stop`
* **Access**: Server Administrators only (`@commands.has_permissions(administrator=True)`).
* **Function**: Instantly halts an active rebuild or broadcast. It checks for cancellation before deleting channels, before creating channels, and before sending messages.

### 3. Owner Evaluation (Code Executor)
* **Command**: `nexus4all.eval <code>`
* **Access**: Bot Owner only (`@commands.is_owner()`).
* **Function**: Runs arbitrary Python code inside an async context, captures console prints (`stdout`), and returns the output.
* **Usage Example**:
  ```text
  nexus4all.eval
  for i in range(5):
      print(f"Loop index: {i}")
  ```
