"""
Module for handling reminder-related tools.
"""
import discord

import asyncio
import datetime
from typing import Any

async def set_reminder(bot: discord.client, message: discord.message, time: str, content: str) -> str:
    """
    Sets a reminder to be sent in the same channel at a specified time.

    Args:
        bot: The discord bot instance.
        message: The discord message object where the request was made.
        time: A Unix timestamp (integer) for when the reminder should be sent.
        message_text: The content of the reminder to be sent.
    """
    # Note: In a production environment, this should use a persistent task queue/database.
    # For now, we use an in-memory asyncio task for simplicity.

    # Simple logic to handle "in X minutes" or similar.
    # A more robust parser like dateparser would be ideal here.
    try:
        # This is a placeholder for actual time parsing logic.
        # In a real scenario, we'd parse 'time' into a timedelta or a specific datetime.
        # For this implementation, we assume the LLM provides a valid duration if possible
        # or we use a basic heuristic.

        seconds = max(0, int(datetime.datetime.fromisoformat(time).timestamp())
 - int(datetime.datetime.now().timestamp()))

        # Create the task to send the message after the specified delay.
        async def delayed_reminder():
            await asyncio.sleep(seconds)
            # Ping the user by mentioning them in the same channel.
            await message.channel.send(f"🔔 {message.author.mention} **Reminder:** {content}")

        asyncio.create_task(delayed_reminder())
        return f"Success: Reminder set at timestamp {time}."
    except Exception as e:
        return f"ERROR: Failed to set reminder: {str(e)}"

set_reminder_config = {
    "type": "function",
    "function": {
        "name": "set_reminder",
        "description": "Sets a reminder for the user. The reminder will be sent in the same channel at the specified time.",
        "parameters": {
            'type': 'object',
            "properties": {
                "time": {
                    "type": "string",
                    "description": "ISO 8601 string of the time when the reminder should go off"
                },
                "content": {
                    "type": "string",
                    "description": "The content of the reminder to be displayed."
                }
            },
            "required": ["time", "content"]
        }
    }
}
