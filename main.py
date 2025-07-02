import discord
from discord.ext import commands, tasks
import os
import json
import datetime
import asyncio

# Environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
TRN_API_KEY = os.getenv('TRN_API_KEY')
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))

# Bot setup
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

# Time tracking for uptime status
start_time = datetime.datetime.utcnow()

# Uptime status update loop (every 60 seconds)
@tasks.loop(seconds=60)
async def update_status():
    uptime = datetime.datetime.utcnow() - start_time
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, _ = divmod(remainder, 60)
    status = f"Online for {hours}h {minutes}m"
    await bot.change_presence(activity=discord.Game(name=status))

# Event when the bot is ready
@bot.event
async def on_ready():
    print(f"✅ {bot.user.name} is online!")
    await bot.change_presence(activity=discord.Game(name="Starting up..."))
    update_status.start()

    # Log bot online status
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send("✅ Bot restarted and is online.")

# Class for the link account button
class LinkAccountButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="🔗 Link Rocket League Account", style=discord.ButtonStyle.success, custom_id="link_account"))

# Modal for username input
class UsernameModal(discord.ui.Modal, title="Enter Your Rocket League Username"):
    username = discord.ui.TextInput(label="Rocket League Username", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("Select your platform:", view=PlatformSelector(self.username.value), ephemeral=True)

# Platform selector buttons
class PlatformSelector(discord.ui.View):
    def __init__(self, username):
        super().__init__(timeout=60)
        self.username = username

        # Add platform buttons
        for platform in ["steam", "epic", "psn", "xbl"]:
            self.add_item(discord.ui.Button(label=platform.upper(), style=discord.ButtonStyle.primary, custom_id=f"platform_{platform}"))

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ Linking canceled.", ephemeral=True)

# Handle button interactions (link account)
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        if interaction.data["custom_id"] == "link_account":
            try:
                await interaction.response.send_modal(UsernameModal())
            except discord.Forbidden:
                await interaction.response.send_message("❌ I can't DM you. Please enable DMs!", ephemeral=True)

        elif interaction.data["custom_id"].startswith("platform_"):
            platform = interaction.data["custom_id"].split("_")[1]
            user_id = str(interaction.user.id)
            username = interaction.message.components[0].children[0].label  # Fallback to the username entered earlier

            # Load existing linked users
            try:
                with open("linked_users.json", "r") as f:
                    linked_users = json.load(f)
            except FileNotFoundError:
                linked_users = {}

            # Add new linked user
            linked_users[user_id] = {"platform": platform, "username": username}

            # Save to linked_users.json
            with open("linked_users.json", "w") as f:
                json.dump(linked_users, f, indent=2)

            # Send confirmation message
            await interaction.response.send_message(f"✅ Linked `{username}` on `{platform.upper()}`!", ephemeral=True)

            # Log the link action in the log channel
            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(f"🔗 {interaction.user.mention} linked `{username}` on `{platform.upper()}`.")

# Command to post the link button
@bot.command()
async def post_link_button(ctx):
    await ctx.send("🔗 Click below to link your Rocket League account:", view=LinkAccountButton())

# Command to show linked users' stats (example)
@bot.command()
async def stats(ctx):
    user_id = str(ctx.author.id)
    if user_id not in linked_users:
        await ctx.send("❌ You haven't linked your Rocket League account yet. Use `/post_link_button` to link.")
        return

    platform, username = linked_users[user_id]
    url = f"https://api.tracker.gg/api/v2/rocket-league/standard/profile/{platform}/{username}"
    headers = {"TRN-Api-Key": TRN_API_KEY}
    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        await ctx.send("⚠️ Couldn't fetch your stats. Try again.")
        return

    stats = r.json()["data"]["segments"][0]["stats"]
    embed = discord.Embed(
        title=f"{username}'s Rocket League Stats",
        description=f"📊 Platform: `{platform.upper()}`",
        color=0x00ffcc
    )
    embed.set_thumbnail(url="https://www.rocketleague.com/_next/static/media/rocket-league.6f2c3b84.svg")
    embed.add_field(name="🏆 Rank", value=stats['rating']['displayValue'], inline=True)
    embed.add_field(name="🎯 MMR", value=stats['rating']['value'], inline=True)
    embed.add_field(name="✅ Wins", value=stats['wins']['value'], inline=True)
    embed.add_field(name="🥅 Goals", value=stats['goals']['value'], inline=True)

    await ctx.send(embed=embed)

# Run the bot
bot.run(BOT_TOKEN)
