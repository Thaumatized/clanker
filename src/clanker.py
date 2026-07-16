import asyncio
import discord
from discord.ext import commands
from config import get_secret
from bot.events import EventHandlers
from bot.commands.general import GeneralCommands
from core.db.manager import initialize_all_db

# Discord configuration
TOKEN = get_secret("discordToken")

# Define intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True # Required for guild-specific events and context

# Initialize the bot
bot = commands.Bot(command_prefix=None, intents=intents)

async def main():
    initialize_all_db()

    await bot.add_cog(EventHandlers(bot))
    await bot.add_cog(GeneralCommands(bot))


    # Start the bot
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
