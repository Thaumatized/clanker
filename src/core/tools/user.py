import discord
import json

async def get_user_info(bot: discord.client, message: discord.message, user_id: str):
    """
    Retrieves and displays structured metadata for a given user ID.
    """

    try:
        target_user = await bot.fetch_user(int(user_id))
        if not target_user:
            raise ValueError("User resolution failed.")
        return json.dumps({
            "username": target_user.name,
            "id": target_user.id,
            "display_name": getattr(target_user, 'display_name', target_user.name),
            #"status": discord.utils.get(message.guild.allowed_statuses, name=str(target_user.status)).value,
        })
    except Exception as e:
        return f"ERROR: Error fetching user {user_id}: {e}"

get_user_info_config = {
    "type": "function",
    "function": {
        "name": "get_user_info",
        "description": "Retrieves comprehensive, structured metadata (ID, name, status) for a specified Discord user account.",
        "parameters": {
            'type': 'object',
            "properties": {
                'user_id': {
                    'type': 'string',
                    "description": "The target Discord ID of the user. It is really an integer, but needs to be inputted as a string to avoid FP64 errors."
                },
            },
            "required": ["user_id"] 
        }
    }
}