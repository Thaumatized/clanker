import discord
from discord.ext import commands
from core.ai.client import OllamaClient
from bot.utils import chunk_text_with_smart_breaks, get_channel_history, discord_history_to_ollama
from core.db.manager import get_bot_to_bot, is_channel_enabled, get_model

# Use a Cog to encapsulate all bot functionality (events and commands)
class EventHandlers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Initialize the AI client instance here
        self.ollama_client = OllamaClient()

    @commands.Cog.listener()
    async def on_ready(self):
        """Event handler for when the bot is ready."""
        print("--- BOT STATUS ---")
        #print(f"Logged in as {discord.utils.get_executor().name}")
        print("------------------")

        # Register slash commands
        try:
            await self.bot.tree.sync()
            print("✅ Slash commands registered successfully!")
        except Exception as e:
            print(f"⚠️ Error registering slash commands: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        # Check for self-messages or empty content
        if message.author == self.bot.user or not message.content.strip():
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
        if not is_channel_enabled(message.channel.id):
            return
        
        print(f"Responding to message: {message.content}")

        channel = message.channel
        async with channel.typing():
            try:
                discord_message_history = await get_channel_history(channel, message.id)

                ollama_message_history = discord_history_to_ollama(discord_message_history, self.bot.user.id)

                response = await self.ollama_client.generate(message_history=ollama_message_history, model=get_model(message.channel.id))

                print(f"Response: {response}")

                chunks = chunk_text_with_smart_breaks(response, 2000)

                first = True
                for chunk in chunks:
                    if first:
                        await message.reply(chunk)
                        first = False
                    else:
                        await channel.send(chunk)
            except Exception as e:
                print(f"Error: {str(e)}")
                await channel.send(f"Error: {str(e)}")