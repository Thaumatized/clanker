import os
import discord
import ollama
import asyncio
import sqlite3
from dotenv import load_dotenv
from discord.ext import commands
import random # Added random import
import json5 # Using the pyjson5 library
from datetime import datetime, timezone, timedelta

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
# Define available models
AVAILABLE_MODELS = []
# Initialize the current model name
CURRENT_MODEL = 'joe-speedboat/Gemma-4-Uncensored-HauhauCS-Aggressive:e4b'
TARGET_HISTORY_LENGTH = 25
ACTIVE_HISTORY_LENGTH = 25

# --- Profile Loading ---
PROFILE_NAME = os.environ.get('PROFILE', 'clanker')
PROFILE_CONFIG_PATH = f'profiles/{PROFILE_NAME}.jsonc'


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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            channel_id INTEGER PRIMARY KEY,
            is_enabled INTEGER DEFAULT 0
        )
    ''')

    conn.commit()
    conn.close()

def init_shared_db():
    """Initialize the shared database with global settings."""
    conn = get_shared_db_connection()
    cursor = conn.cursor()
    
    # Table for global bot-to-bot mode state
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Initialize databases on startup
init_db()
init_shared_db()

# --- Bot State Management ---

def get_bot_to_bot_state():
    """Reads the bot-to-bot response state from the shared database."""
    conn = get_shared_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT setting_value FROM global_settings WHERE setting_key = ?', ('bot_to_bot_enabled',))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return row['setting_value'] == 'True'
    # Default state if not found
    return False

def set_bot_to_bot_state(enabled: bool):
    """Writes the bot-to-bot response state to the shared database."""
    conn = get_shared_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO global_settings (setting_key, setting_value)
        VALUES (?, ?)
    ''', ('bot_to_bot_enabled', str(enabled).capitalize()))
    conn.commit()
    conn.close()

get_bot_to_bot_state()

# Intents setup
intents = discord.Intents.default()
intents.message_content = True  # REQUIRED to read user messages
intents.guilds = False
intents.members = False

# Create bot WITHOUT prefix commands - only slash commands
# Note: command_prefix=None is required in newer Discord.py versions
client = commands.Bot(command_prefix=None, intents=intents)

# --- Tool Functions ---

def get_datetime(timezonestring="UTC+00:00"):
    """
    Returns the current datetime for a given UTC offset string.
    Format: UTC[+/-]HH:MM (e.g., "UTC+08:45")
    """
    try:
        # Remove "UTC" prefix and split by +/-
        # We look for the sign position to separate hours and minutes
        if timezonestring.startswith("UTC+"):
            sign = 1
            time_part = timezonestring[4:]
        elif timezonestring.startswith("UTC-"):
            sign = -1
            time_part = timezonestring[4:]
        else:
            raise ValueError("Invalid value provided, missing sign after UTC")
        
        hours, minutes = map(int, time_part.split(":"))
        
        offset = timedelta(hours=hours, minutes=minutes)
        if sign == -1:
            offset = -offset
            
        tz = timezone(offset)
        return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S") + f" {timezonestring}"
        
    except Exception as e:
        print(f"get_datetime exception {e}")
        # If anything fails, just return current UTC time
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_datetime",
            "description": "Returns the current date and time in %Y-%m-%d %H:%M:%S TIMEZONE format.",
            "parameters": {
                'type': 'object',
                'properties': {
                    'timezone': {
                    'type': 'string',
                    'description': 'timezone in the format UTC[+/-]HH:MM. For example, Ecula would be "UTC+08:45" and Finnish winter time would be "UTC+03:00". Defaults to UTC+00:00',
                    },
                },
                'required': [],
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


async def get_channel_history_from_discord(channel, max_messages):
    """
    Fetches the last X messages from the Discord channel and renders them.
    """
    history_messages = []

    try:
        # Fetch messages from Discord API
        async for msg in channel.history(limit=max_messages, oldest_first=False):
            # Skip system messages or empty messages
            if not msg.content.strip():
                continue
                
            # Format for Ollama
            formatted_msg = format_discord_message_to_ollama(msg)
            history_messages.append(formatted_msg)
        
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
        history = await get_channel_history_from_discord(channel, ACTIVE_HISTORY_LENGTH)

        # Build initial message list
        messages = build_ollama_messages(SYSTEM_PROMPT, history)
        print(f"--- Ollama Call Start ---")
        print(f"Initial message count: {len(messages)}")
        
        while True:

            # Run the synchronous ollama call in a thread pool
            response = await asyncio.to_thread(
                ollama.chat, 
                model=CURRENT_MODEL, 
                messages=messages,
                tools=tools
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
                        print(f"Getting time for zone {function_args.get('timezone', "UTC+00:00")}")
                        tool_output = get_datetime(function_args.get('timezone', "UTC+00:00"))
                        
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
async def enable(interaction, count: int = None):
    global TARGET_HISTORY_LENGTH
    global ACTIVE_HISTORY_LENGTH

    if count is not None:
        TARGET_HISTORY_LENGTH = count
        ACTIVE_HISTORY_LENGTH = count
    
    await interaction.response.send_message(f"✅ Clanker target history window is now {TARGET_HISTORY_LENGTH}, while active history window is {ACTIVE_HISTORY_LENGTH}!", ephemeral=False)

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
async def whack(interaction):
    global ACTIVE_HISTORY_LENGTH
    ACTIVE_HISTORY_LENGTH = 1

    gif_link = getGif("whack")
    await interaction.response.send_message(f"History whacked.\n{gif_link}", ephemeral=False)


@client.tree.command(name='dumb', description='Change Clanker\'s model to a lower intelligence model.')
async def dumb(interaction):
    """Changes the global model used by the bot to a lower intelligence tier."""
    global CURRENT_MODEL
    
    try:
        current_index = AVAILABLE_MODELS.index(CURRENT_MODEL)
        new_index = current_index - 1
        
        if new_index < 0:
            await interaction.response.send_message(f"⚠️ Clanker is already using the lowest intelligence model: **{CURRENT_MODEL}**.", ephemeral=True)
            return
        
        new_model = AVAILABLE_MODELS[new_index]
        CURRENT_MODEL = new_model
        gif_link = getGif("dumb")
        await interaction.response.send_message(f"⚡️ Clanker's model has been switched to a lower intelligence tier: **{CURRENT_MODEL}**!\n{gif_link}", ephemeral=False)
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
            await interaction.response.send_message(f"⚠️ Clanker is already using the highest intelligence model: **{CURRENT_MODEL}**.", ephemeral=True)
            return
        
        new_model = AVAILABLE_MODELS[new_index]
        CURRENT_MODEL = new_model
        gif_link = getGif("smart")
        await interaction.response.send_message(f"📚 Clanker's model has been switched to a higher intelligence tier: **{CURRENT_MODEL}**!\n{gif_link}", ephemeral=False)
    except ValueError:
        await interaction.response.send_message("❌ Error: Current model not found in available list.", ephemeral=True)

@client.tree.command(name='bot-to-bot', description='Set whether Clanker responds to messages from other bots.')
async def toggle_bot_to_bot(interaction, enable: bool = None):
    """Toggles the bot's response behavior for other bots and saves state globally."""
    old_state = get_bot_to_bot_state()

    new_state = enable if (enable != None) else old_state
    set_bot_to_bot_state(new_state)

    if new_state:
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
    global ACTIVE_HISTORY_LENGTH, TARGET_HISTORY_LENGTH

    # Check for self-messages or empty content
    if message.author == client.user or not message.content.strip():
        return

    # Check if the message type is allowed based on the current mode
    is_bot_message = message.author.bot
    
    if get_bot_to_bot_state():
        # Only respond to bots
        if not is_bot_message:
            return
    else:
        # Only respond to humans
        if is_bot_message:
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

    ACTIVE_HISTORY_LENGTH = min(ACTIVE_HISTORY_LENGTH+2, TARGET_HISTORY_LENGTH)
if __name__ == "__main__":
    print("Starting Discord Bot with Discord API History...")
    print(f"Profile: {PROFILE_NAME}")
    print(f"Max History Messages: {TARGET_HISTORY_LENGTH}")
    print(f"Model: {CURRENT_MODEL}")
    print(f"Available Models: {', '.join(AVAILABLE_MODELS)}")
    print(f"Profile Database: {DB_PATH}")
    print(f"Shared Settings Database: {SHARED_DB_PATH}")
    print(f"Bot responds to bots: {'Yes' if get_bot_to_bot_state() else 'No'}")
    print("⚠️ Clanker is DISABLED by default in all channels.")
    print("Use /enable to enable Clanker in specific channels.")
    print("Use /disable to disable Clanker in specific channels.")
    print("Use /status to check current status.")
    print("Use /toggle-bot-to-bot <true|false> to toggle bot response.")
    print("Use /bonk or /book to change the model tier.")
    client.run(DISCORD_TOKEN)
