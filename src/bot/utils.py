import discord
from typing import Optional
from core.db.manager import get_whack, get_history_length

# Discord-specific utility functions.

def create_embed(title: str, description: str, color: int = discord.Color.blue()) -> discord.Embed:
    # Creates a basic Discord embed.
    return discord.Embed(title=title, description=description, color=color)

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

async def get_channel_history(channel: discord.channel, newest_message_id: int | None = None) -> list:
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
            # Skip messages newer than the one we are responding to
            if newest_message_id is not None and msg.id > newest_message_id:
                continue

            # Skip system messages or empty messages
            if not msg.content.strip():
                continue

            if whack_id is not None and msg.id <= whack_id:
                print(whack_id)
                break

            history_messages.append(msg)
        
        # Reverse to get chronological order (oldest first)
        history_messages.reverse()
        
    except discord.Forbidden:
        print(f"Cannot read message history in channel {channel.id}. Check permissions.")
    except Exception as e:
        print(f"Error fetching history: {e}")
    
    return history_messages

def format_discord_message_to_ollama(msg: discord.message, bot_id: int):
    """
    Converts a Discord message object to Ollama message format.
    Determines role based on whether the author is the bot.
    """
    if msg.author.id == bot_id:
        return {
            'role': 'assistant',
            'content': f"{msg.content}"
        }
    else:
        return {
            'role': 'user',
            'content': f"<{msg.author.id}> {msg.author.display_name}: {msg.content}"
        }
    
def discord_history_to_ollama(discord_history: list, bot_id: int):
    return list(map(lambda msg: format_discord_message_to_ollama(msg, bot_id), discord_history))
