from discord import app_commands
import discord
from discord.ext import commands
from core.db.manager import set_history_length, get_history_length, set_channel_enabled, set_whack, set_bot_to_bot, get_bot_to_bot, set_model, get_model
from config import get_gif_url, CONFIG
from core.ai.client import OllamaClient # Import the client

# Global model state management remains here for now:
CURRENT_MODEL = None # This should be initialized by srcold/config.py, but kept for context

class GeneralCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Initialize the client instance when the cog is loaded
        self.ai_client = OllamaClient()
        
    @app_commands.command(name='history-length', description='Set Clankers chat history window')
    async def history_length(self, interaction, count: int = None):
        if count is not None:
            set_history_length(interaction.channel.id, count)

        await interaction.response.send_message(f"✅ Clanker target history window is now {get_history_length(interaction.channel.id)}!", ephemeral=False)

    @app_commands.command(name='enable', description='Enable Clanker in a channel')
    async def enable(self, interaction, channel: discord.TextChannel = None):
        if channel is None:
            channel = interaction.channel

        set_channel_enabled(channel.id, True)

        gif_link = get_gif_url("enable")
        await interaction.response.send_message(f"✅ Clanker is now **enabled** in <#{channel.id}>!\n{gif_link}", ephemeral=False)

    @app_commands.command(name='disable', description='Disable Clanker in a channel')
    async def disable(self, interaction, channel: discord.TextChannel = None):
        """Disable Clanker in a channel."""
        if channel is None:
            channel = interaction.channel

        set_channel_enabled(channel.id, False)

        gif_link = get_gif_url("disable")
        await interaction.response.send_message(f"🚫 Clanker is now **disabled** in <#{channel.id}>!\n{gif_link}", ephemeral=False)

    @app_commands.command(name='whack', description='Clear clankers memory by slowly increasing historylength from 1')
    async def whack(self, interaction: discord.Interaction):
        response_message = await interaction.response.send_message(f"History whacked.\n{get_gif_url('whack')}", ephemeral=False)

        set_whack(interaction.channel_id, response_message.id)

    @app_commands.command(name='dumb', description='Change Clanker\'s model to a lower intelligence model.')
    async def dumb(self, interaction):
        try:
            AVAILABLE_MODELS = CONFIG['base']['models']['censored']
            CURRENT_MODEL = get_model(interaction.channel.id)
            current_index = AVAILABLE_MODELS.index(CURRENT_MODEL)
            new_index = current_index - 1

            if new_index < 0:
                await interaction.response.send_message(f"⚠️ Clanker is already using the lowest intelligence model: **{CURRENT_MODEL['name']}**.", ephemeral=False)
                return

            new_model = AVAILABLE_MODELS[new_index]
            set_model(interaction.channel.id, new_model)
            gif_link = get_gif_url("dumb")
            await interaction.response.send_message(f"⚡️ Clanker's model has been switched to a lower intelligence tier: **{new_model['name']}**!\n{gif_link}", ephemeral=False)
        except ValueError:
            await interaction.response.send_message("❌ Error: Current model not found in available list.", ephemeral=True)

    @app_commands.command(name='smart', description='Change Clanker\'s model to a higher intelligence model.')
    async def smart(self, interaction):
        try:
            AVAILABLE_MODELS = CONFIG['base']['models']['censored']
            CURRENT_MODEL = get_model(interaction.channel.id)
            current_index = AVAILABLE_MODELS.index(CURRENT_MODEL)
            new_index = current_index + 1

            if new_index >= len(AVAILABLE_MODELS):
                await interaction.response.send_message(f"⚠️ Clanker is already using the highest intelligence model: **{CURRENT_MODEL['name']}**.", ephemeral=False)
                return

            new_model = AVAILABLE_MODELS[new_index]
            set_model(interaction.channel.id, new_model)
            gif_link = get_gif_url("smart")
            await interaction.response.send_message(f"📚 Clanker's model has been switched to a higher intelligence tier: **{new_model['name']}**!\n{gif_link}", ephemeral=False)
        except ValueError:
            await interaction.response.send_message("❌ Error: Current model not found in available list.", ephemeral=True)

    @app_commands.command(name='bot-to-bot', description='Set whether Clanker responds to messages from other bots.')
    async def toggle_bot_to_bot(self, interaction: discord.Interaction, enable: bool = None):
        channel = interaction.channel

        old_channel_state = get_bot_to_bot(channel.id)
        new_channel_state = enable if (enable != None) else old_channel_state
        set_bot_to_bot(channel.id, new_channel_state)

        # Determine status message based on the channel's state
        if new_channel_state:
            status_message = "✅ Clanker is now configured to respond to messages from other bots (Bot-to-Bot Mode)."
            gif_link = get_gif_url("botToBotEnable")
        else:
            status_message = "🚫 Clanker is now configured to only respond to human users (Human-Only Mode)."
            gif_link = get_gif_url("botToBotDisable")
            
        await interaction.response.send_message(f"{status_message}\n{gif_link}", ephemeral=False)