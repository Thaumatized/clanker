# Clanker Discord Bot

Clanker is a sophisticated Discord bot designed to interact with users using advanced LLM capabilities (via Ollama). It features customizable personality, history management, and dynamic response generation.

## Features

* **Local LLM Integration:** Connects to local LLMs via Ollama.
* **Custom Personality:** Easily define the bot's persona using a profile jsonc file
* **History Management:** Tracks conversation history to maintain context.
* **Dynamic Status:** Commands to enable/disable the bot in specific channels or guilds.
* **Model Tiers:** Ability to switch the underlying LLM model's intelligence level.

## Prerequisites

Before running Clanker, ensure you have the following installed:

1. **Python 3.8+**
1. **Ollama:** The local LLM server must be running and accessible.
1. **Python venv**
1. **Required Python Libraries:**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## ⚙️ Setup and Configuration

### 1. Secrets

Create a file named `secrets.jsonc` in the root directory of your project and add your Discord bot token:

```
{
  "clanker": {
    "discordToken": "123-thisisatoken",
  },
  "mrs": {
    "discordToken": "456-othertokenforotherbot",
  },
}
```


### 2. Profile Configuration (`clanker.jsonc`)

The bot's core personality and token are managed in `{PROFILE}.jsonc`.

* **`personalityPrompt`**: The system prompt that defines Clanker's behavior.

**Example:**
```
{
    "personalityPrompt": "You are Clanker, a helpful Discord bot. Keep responses short and direct. "
}
```

### 3. Common Configuration (`config.jsonc`)

This file holds
1. enabled Models **WARNING** by default enabled models are uncensored. This is fun, but they will respond to *any* request so do not ask for what you don't want to see.
2. GIF links for various bot actions (e.g., `enable`, `disable`, `whack`).

## Usage

### 1. Running the Bot

Execute the main script:
> PROFILE=clanker ./clanker.sh

This will automatically use the venv and launch the bot.

### 2. Slash Commands Reference

Clanker uses Discord Slash Commands for management.

| Command | Description | Usage |
| :--- | :--- | :--- |
| `/enable` | Enables Clanker in the current channel. | `/enable` |
| `/disable` | Disables Clanker in the current channel. | `/disable` |
| `/history-length` | Sets the target and active history window size. | `/history-length <integer>` |
| `/whack` | Resets Clanker's active memory history. | `/whack` |
| `/smart` | Switches the bot to a higher intelligence model. | `/smart` |
| `/dumb` | Switches the bot to a lower intelligence model. | `/dumb` |
| `/toggle-bot-to-bot` | Toggles if the bot responds to other bots. | `/toggle-bot-to-bot <boolean>` |

## Troubleshooting

*   **"Ollama Error"**: Ensure the Ollama service is running locally and that the models listed in `clanker.py` are pulled (`ollama pull <model_name>`).
*   **Permissions**: The bot must have read/write permissions in the target channels.
*   **Token**: Verify that the token in `clanker.jsonc` is correct and belongs to a bot with necessary permissions.

## Vibecoding

Use `./aider.sh` to vibecode with aider.