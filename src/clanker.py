import os
import discord
import ollama
import asyncio
import sqlite3
from dotenv import load_dotenv
from discord.ext import commands
import random # Added random import
import json5 # Using the pyjson5 library
from datetime import datetime
from zoneinfo import ZoneInfo

# Load environment variables from .env file
load_dotenv()

# --- Profile Loading ---
PROFILE_NAME = os.environ.get('PROFILE', 'clanker')
PROFILE_CONFIG_PATH = f'profiles/{PROFILE_NAME}.jsonc'

DEFAULTS = {
    "history_length": 25,
}


# Load configuration from JSON file
# NOTE: Using json5 to correctly handle JSONC format (with comments).
def load_jsonc(file_path):
    """Loads JSON content from a file, supporting JSONC format."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            # Use json5.loads to parse the content
            return json5.loads(content)
    except FileNotFoundError:
        print(f"⚠️ Warning: {file_path} not found. Using default/empty configuration.")
        return {}
    except Exception as e:
        print(f"⚠️ Warning: Error decoding {file_path} using json5. Ensure it is valid JSONC. Error: {e}")
        return {}

# Load the profile configuration
PROFILE_CONFIG = load_jsonc(PROFILE_CONFIG_PATH)

# Load the GIF configuration
CONFIG = load_jsonc('config.jsonc')
AVAILABLE_MODELS = CONFIG.get("models", [])
CURRENT_MODEL = AVAILABLE_MODELS[1]

# Load the secrets file to get the Discord token
SECRETS = load_jsonc('secrets.jsonc').get(PROFILE_NAME, {})

# Initialize the Discord Token and System Prompt based on the profile
# Retrieve the token from the secrets file
DISCORD_TOKEN = SECRETS.get("discordToken")
PERSONALITY_PROMPT = PROFILE_CONFIG.get("personalityPrompt", "You are complains-of-missing-personality-prompt. All you will do is complain about missing personality prompt.")

# Define the system prompt for the LLM, combining personality and context
SYSTEM_PROMPT = f"""
{PERSONALITY_PROMPT}
You see messages in the format:
<userid> username: message
You do not prepend your responses with userid or username. This is handled by external systems.
"""

if not DISCORD_TOKEN:
    raise ValueError(f"No Discord token found for profile '{PROFILE_NAME}'! Please check your secrets configuration.")

# Database setup
DB_PATH = f'databases/{PROFILE_NAME}.sqlite'
SHARED_DB_PATH = 'databases/shared.sqlite'

def get_db_connection():
    """Get a database connection for profile-specific data."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_shared_db_connection():
    """Get a database connection for shared settings."""
    os.makedirs(os.path.dirname(SHARED_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(SHARED_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database with required tables (Profile-specific)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create channels table to track enabled/disabled status
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS channels (
            channel_id INTEGER PRIMARY KEY,
            is_enabled INTEGER DEFAULT 0,
            history_length INTEGER DEFAULT {DEFAULTS["history_length"]},
            whack_message_id INTEGER DEFAULT 0
        )
    ''')

    conn.commit()
    conn.close()

def init_shared_db():
    """Initialize the shared database with global settings."""
    conn = get_shared_db_connection()
    cursor = conn.cursor()
    
    # Create channels table to track bot-to-bot mode
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            channel_id INTEGER PRIMARY KEY,
            bot_to_bot_enabled INTEGER DEFAULT 0
        )
    ''')

    conn.commit()
    conn.close()

init_db()
init_shared_db()

# --- Bot State Management ---

def get_whack(channel_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT whack_message_id FROM channels WHERE channel_id = ?', (channel_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return row['whack_message_id']
    # Default state if not found
    return 0

def set_whack(channel_id: int, whack_message_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO channels (channel_id, whack_message_id)
        VALUES (?, ?)
        ON CONFLICT(channel_id) DO UPDATE SET
            whack_message_id = excluded.whack_message_id
    ''', (channel_id, whack_message_id))
    conn.commit()
    conn.close()

def get_history_length(channel_id: int) -> bool:
    """Reads the bot-to-bot response state for a specific channel from the profile database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT history_length FROM channels WHERE channel_id = ?', (channel_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return row['history_length']
    # Default state if not found
    return DEFAULTS["history_length"]

def set_history_length(channel_id: int, history_length: bool):
    """Writes the bot-to-bot response state for a specific channel to the profile database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO channels (channel_id, history_length)
        VALUES (?, ?)
        ON CONFLICT(channel_id) DO UPDATE SET
            history_length = excluded.history_length
    ''', (channel_id, history_length))
    conn.commit()
    conn.close()

def get_bot_to_bot(channel_id: int) -> bool:
    """Reads the bot-to-bot response state for a specific channel from the profile database."""
    conn = get_shared_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT bot_to_bot_enabled FROM channels WHERE channel_id = ?', (channel_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return row['bot_to_bot_enabled'] == 1
    # Default state if not found
    return False

def set_bot_to_bot(channel_id: int, enabled: bool):
    """Writes the bot-to-bot response state for a specific channel to the profile database."""
    conn = get_shared_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO channels (channel_id, bot_to_bot_enabled)
        VALUES (?, ?)
        ON CONFLICT(channel_id) DO UPDATE SET
            bot_to_bot_enabled = excluded.bot_to_bot_enabled
    ''', (channel_id, 1 if enabled else 0))
    conn.commit()
    conn.close()

# Intents setup
intents = discord.Intents.default()
intents.message_content = True  # REQUIRED to read user messages
intents.guilds = False
intents.members = False

# Create bot WITHOUT prefix commands - only slash commands
# Note: command_prefix=None is required in newer Discord.py versions
client = commands.Bot(command_prefix=None, intents=intents)

# --- Tool Functions ---

def get_datetime(timezone_name: str) -> str:
    """
    Returns the current localized datetime for a given IANA time zone name,
    correctly accounting for DST transitions.

    :param timezone_name: The full IANA name of the time zone (e.g., "America/Vancouver").
    :return: Formatted string of the current date, time, and timezone name.
    """
    try:
        tz = ZoneInfo(timezone_name)
        now = datetime.now(tz)
        return now.strftime("%Y-%m-%d %H:%M:%S") + f" ({timezone_name})"
    
    except Exception as e:
        # Handle cases where the time zone name is invalid
        print(f"Error fetching time for {timezone_name}: {e}")
        return datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M:%S (UTC)")

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_datetime",
            "description": "Returns the current, localized date and time for a given time zone name, correctly accounting for Daylight Saving Time (DST) and all time zone rules.",
            "parameters": {
                'type': 'object',
                'properties': {
                    'timezone': {
                        'type': 'string',
                        "description": "The full IANA time zone name (e.g., 'America/Los_Angeles', 'Europe/London', 'Asia/Tokyo'). This name allows the function to correctly calculate DST shifts."
                    }
                },
                'required': ['timezone'] 
            }
        }
    }
]



# --- Helper Functions ---

def format_discord_message_to_ollama(msg):
    """
    Converts a Discord message object to Ollama message format.
    Determines role based on whether the author is the bot.
    """
    if msg.author == client.user:
        return {
            'role': 'assistant',
            'content': f"{msg.content}"
        }
    else:
        return {
            'role': 'user',
            'content': f"<{msg.author.id}> {msg.author.display_name}: {msg.content}"
        }


async def get_channel_history_from_discord(channel):
    """
    Fetches messages from the Discord channel starting from the newest,
    stopping once we reach the 'whack' message ID (inclusive/exclusive logic applied).
    """
    history_messages = []

    try:
        whack_id = get_whack(channel.id)

        # Fetch messages from newest to oldest
        async for msg in channel.history(
            limit=get_history_length(channel.id), 
            oldest_first=False
        ):            
            if whack_id is not None and msg.id <= whack_id:
                break

            # Skip system messages or empty messages
            if not msg.content.strip():
                continue
                
            # Format for Ollama
            formatted_msg = format_discord_message_to_ollama(msg)
            history_messages.append(formatted_msg)
        
        # Reverse to get chronological order (oldest -> newest)
        history_messages.reverse()
        
    except discord.Forbidden:
        print(f"Cannot read message history in channel {channel.id}. Check permissions.")
    except Exception as e:
        print(f"Error fetching history: {e}")
    
    return history_messages

def build_ollama_messages(system_prompt, history):
    """
    Constructs the full message list for Ollama:
    [System Prompt, ...History..., User Prompt]
    """
    messages = [
        {'role': 'system', 'content': system_prompt}
    ]
    
    # Append history
    messages.extend(history)
    
    # we dont "Append current user message" -- it is last in history

    return messages

def getGif(key):
    """
    Retrieves a random GIF link for a given action key from the configuration.
    Returns None if the configuration is missing or the list is empty.
    """
    gifs_config = CONFIG.get("gifs")
    
    if not isinstance(gifs_config, dict):
        print("Warning: 'gifs' configuration section missing or malformed.")
        return None
    
    gif_list = gifs_config.get(key)
    
    if not gif_list or not isinstance(gif_list, list) or not gif_list:
        print(f"Warning: No GIF links found for key '{key}'.")
        return None
        
    return random.choice(gif_list)

# --- Database Functions ---

async def is_channel_enabled(channel):
    """Check if a channel is enabled for Clanker."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_enabled FROM channels WHERE channel_id = ?', (channel.id,))
    row = cursor.fetchone()
    conn.close()
    return row is not None and row['is_enabled'] == 1

async def set_channel_enabled(channel, enabled):
    """Enable or disable a channel."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO channels (channel_id, is_enabled)
        VALUES (?, ?)
    ''', (channel.id, 1 if enabled else 0))
    conn.commit()
    conn.close()
    return enabled

# --- Ollama Helper Function ---
async def get_llama_response(channel):
    """
    Sends a prompt to Ollama with system instruction and conversation history fetched from Discord.
    Handles tool calls if necessary.
    """
    try:
        # Fetch recent history from Discord
        history = await get_channel_history_from_discord(channel)

        # Build initial message list
        messages = build_ollama_messages(SYSTEM_PROMPT, history)
        print(f"--- Ollama Call Start ---")
        print(f"Initial message count: {len(messages)}")
        
        while True:

            # Run the synchronous ollama call in a thread pool
            response = await asyncio.to_thread(
                ollama.chat, 
                model=CURRENT_MODEL['name'],
                messages=messages,
                tools= tools if CURRENT_MODEL['toolCalls'] else None
            )

            message = response['message']
            
            if message.get('tool_calls'):
                print("Tool calls detected!")
                
                tool_calls = message['tool_calls']
                
                for tool_call in tool_calls:
                    print(f"Tool call loop, {tool_call}")
                    function_name = tool_call['function']['name']
                    function_args = tool_call['function']['arguments']
                    
                    if function_name == 'get_datetime':
                        print(f"Getting time for zone {function_args.get('timezone', "UTC")}")
                        tool_output = get_datetime(function_args.get('timezone', "UTC"))
                        
                        # --- STEP 4: Record the tool call and its result in history ---
                        
                        # A. Record the model's request to call the tool
                        messages.append({
                            "role": "assistant",
                            "tool_calls": tool_calls
                        })
                        
                        # B. Record the result of the tool execution
                        messages.append({
                            "role": "tool",
                            "name": function_name,
                            "content": tool_output # The result string!
                        })
                        
                        print("\n🛠️ Tool Output Received!")
                        print(f"   Output Content: {tool_output}")
                        print("-" * 40)
                        
                        # IMPORTANT: Break the inner loop (since we handled one call) 
                        # and continue the while True loop to get the final answer.
                        # break 
            
            else:
                # Ollama generated a final answer (no tool calls needed)
                print("\n✅ Final Answer Generated by LLM!")
                print(f"   Response: {message['content']}")
                return message['content']
                break # Exit the while loop

    except Exception as e:
        print(f"Ollama Error: {e}")
        return "I'm having trouble connecting to my brain right now. Try again later."

# --- Slash Command Registration ---

@client.event
async def on_ready():
    print(f'Logged in as {client.user} (ID: {client.user.id})')
    print('------')
    print(f"Database initialized at {DB_PATH}")
    print(f"Shared Settings initialized at {SHARED_DB_PATH}")
    print(f"Loaded Profile: {PROFILE_NAME}")
    print(f"System Prompt initialized.")
    
    # Register slash commands
    try:
        await client.tree.sync()
        print("✅ Slash commands registered successfully!")
    except Exception as e:
        print(f"⚠️ Error registering slash commands: {e}")

# --- Slash Commands ---

@client.tree.command(name='history-length', description='Set Clankers chat history window')
async def history_length(interaction, count: int = None):

    if count is not None:
        set_history_length(interaction.channel.id, count)
    
    await interaction.response.send_message(f"✅ Clanker target history window is now {get_history_length(interaction.channel.id)}!", ephemeral=False)

@client.tree.command(name='enable', description='Enable Clanker in a channel')
async def enable(interaction, channel: discord.TextChannel = None):
    """Enable Clanker in a channel"""
    if channel is None:
        channel = interaction.channel
    
    enabled = await set_channel_enabled(channel, True)
    
    if enabled:
        gif_link = getGif("enable")
        if gif_link:
            await interaction.response.send_message(f"✅ Clanker is now **enabled** in <#{channel.id}>!\n{gif_link}", ephemeral=False)
        else:
            await interaction.response.send_message(f"✅ Clanker is now **enabled** in <#{channel.id}>! (No GIF available)", ephemeral=False)
    else:
        await interaction.response.send_message(f"⚠️ Channel <#{channel.id}> was already enabled.", ephemeral=False)

@client.tree.command(name='disable', description='Disable Clanker in a channel')
async def disable(interaction, channel: discord.TextChannel = None):
    """Disable Clanker in a channel."""
    if channel is None:
        channel = interaction.channel
    
    enabled = await set_channel_enabled(channel, False)
    
    if not enabled:
        gif_link = getGif("disable")
        if gif_link:
            await interaction.response.send_message(f"🚫 Clanker is now **disabled** in <#{channel.id}>!\n{gif_link}", ephemeral=False)
        else:
            await interaction.response.send_message(f"🚫 Clanker is now **disabled** in <#{channel.id}>! (No GIF available)", ephemeral=False)
    else:
        await interaction.response.send_message(f"⚠️ Channel <#{channel.id}> was already disabled.", ephemeral=False)

@client.tree.command(name='whack', description='Clear clankers memory by slowly increasing historylength from 1')
async def whack(interaction: discord.Interaction):
    response_message = await interaction.response.send_message(f"History whacked.\n{getGif('whack')}", ephemeral=False)
    
    set_whack(interaction.channel_id, response_message.id)


@client.tree.command(name='dumb', description='Change Clanker\'s model to a lower intelligence model.')
async def dumb(interaction):
    """Changes the global model used by the bot to a lower intelligence tier."""
    global CURRENT_MODEL
    
    try:
        current_index = AVAILABLE_MODELS.index(CURRENT_MODEL)
        new_index = current_index - 1
        
        if new_index < 0:
            await interaction.response.send_message(f"⚠️ Clanker is already using the lowest intelligence model: **{CURRENT_MODEL['name']}**.", ephemeral=False)
            return
        
        new_model = AVAILABLE_MODELS[new_index]
        CURRENT_MODEL = new_model
        gif_link = getGif("dumb")
        await interaction.response.send_message(f"⚡️ Clanker's model has been switched to a lower intelligence tier: **{CURRENT_MODEL['name']}**!\n{gif_link}", ephemeral=False)
    except ValueError:
        await interaction.response.send_message("❌ Error: Current model not found in available list.", ephemeral=True)


@client.tree.command(name='smart', description='Change Clanker\'s model to a higher intelligence model.')
async def smart(interaction):
    """Changes the global model used by the bot to a higher intelligence tier."""
    global CURRENT_MODEL
    
    try:
        current_index = AVAILABLE_MODELS.index(CURRENT_MODEL)
        new_index = current_index + 1
        
        if new_index >= len(AVAILABLE_MODELS):
            await interaction.response.send_message(f"⚠️ Clanker is already using the highest intelligence model: **{CURRENT_MODEL['name']}**.", ephemeral=False)
            return
        
        new_model = AVAILABLE_MODELS[new_index]
        CURRENT_MODEL = new_model
        gif_link = getGif("smart")
        await interaction.response.send_message(f"📚 Clanker's model has been switched to a higher intelligence tier: **{CURRENT_MODEL['name']}**!\n{gif_link}", ephemeral=False)
    except ValueError:
        await interaction.response.send_message("❌ Error: Current model not found in available list.", ephemeral=True)

@client.tree.command(name='bot-to-bot', description='Set whether Clanker responds to messages from other bots.')
async def toggle_bot_to_bot(interaction: discord.Interaction, enable: bool = None):
    """Toggles the bot's response behavior for other bots and saves state globally and per channel."""
    channel = interaction.channel

    old_channel_state = get_bot_to_bot(channel.id)
    new_channel_state = enable if (enable != None) else old_channel_state
    set_bot_to_bot(channel.id, new_channel_state)

    # Determine status message based on the channel's state
    if new_channel_state:
        status_message = "✅ Clanker is now configured to respond to messages from other bots (Bot-to-Bot Mode)."
        gif_link = getGif("botToBotEnable")
    else:
        status_message = "🚫 Clanker is now configured to only respond to human users (Human-Only Mode)."
        gif_link = getGif("botToBotDisable")
        
    await interaction.response.send_message(f"{status_message}\n{gif_link}", ephemeral=False)


# --- Message Event Handler ---

def chunk_text_with_smart_breaks(text: str, max_chars: int = 2000) -> list[str]:
    """
    Splits a large string into smaller chunks, prioritizing natural breaks
    (like newlines or spaces) over strict character limits.

    Args:
        text: The string to be split (e.g., a long article).
        max_chars: The maximum desired length of each chunk.

    Returns:
        A list of strings, where each string is a chunk.
    """
    if not text:
        return []
    
    chunks = []
    current_start_index = 0
    total_length = len(text)

    while current_start_index < total_length:
        cut_index = -1
        search_window = text[current_start_index : current_start_index + max_chars]

        if total_length < current_start_index + max_chars:
            cut_index = total_length

        if cut_index <= 0:
            best_break_in_window = search_window.rfind('\n')
            cut_index = current_start_index + best_break_in_window
            
        if cut_index <= 0:
            best_break_in_window = search_window.rfind(' ')
            cut_index = current_start_index + best_break_in_window

        if cut_index <= 0:
            cut_index = current_start_index + max_chars

        chunks.append(text[current_start_index:cut_index])  
        current_start_index = cut_index
        
    return chunks

@client.event
async def on_message(message):
    # Check for self-messages or empty content
    if message.author == client.user or not message.content.strip():
        return
    
    if get_bot_to_bot(message.channel.id):
        # Only respond to bots
        if not message.author.bot:
            return
    else:
        # Only respond to humans
        if message.author.bot:
            return

    # Check if channel is enabled
    if not await is_channel_enabled(message.channel):
        return

    channel = message.channel

    # Send a "thinking" indicator
    async with channel.typing():
        try:
            # Generate response with history fetched from Discord
            response = await get_llama_response(channel)
            
            # Discord has a 2000 character limit per message.
            # Split long responses into chunks.
            chunks = chunk_text_with_smart_breaks(response, 2000)
            
            first = True
            for chunk in chunks:
                if first:
                    await message.reply(chunk)
                    first = False
                else:
                    await channel.send(chunk)
                
        except Exception as e:
            await channel.send(f"Error: {str(e)}")
if __name__ == "__main__":
    print("Starting Discord Bot with Discord API History...")
    print(f"Profile: {PROFILE_NAME}")
    print(f"Model: {CURRENT_MODEL['name']}")
    print(f"Available Models: {', '.join([model['name'] for model in AVAILABLE_MODELS])}")
    print(f"Profile Database: {DB_PATH}")
    print(f"Shared Settings Database: {SHARED_DB_PATH}")
    print("⚠️ Clanker is DISABLED by default in all channels.")
    print("Use /enable to enable Clanker in specific channels.")
    print("Use /disable to disable Clanker in specific channels.")
    print("Use /history-length <int> to set history length.")
    print("Use /whack to clear memory.")
    print("Use /bot-to-bot <true|false> to toggle bot response.")
    print("Use /dumb or /smart to change the model tier.")
    client.run(DISCORD_TOKEN)
