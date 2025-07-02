import os
import json
import requests
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import traceback

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
TRN_API_KEY = os.getenv("TRN_API_KEY")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))  # Put your log channel ID here

DATA_FILE = "linked_users.json"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Load linked users from JSON file
def load_linked_users():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

# Save linked users to JSON file
def save_linked_users(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Send log message helper
async def send_log(message: str):
    if LOG_CHANNEL_ID == 0:
        return
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(message)

linked_users = load_linked_users()

class PlatformButtonView(discord.ui.View):
    def __init__(self, username, user_id):
        super().__init__(timeout=60)
        self.username = username
        self.user_id = user_id

        for platform in ["steam", "epic", "psn", "xbl"]:
            self.add_item(discord.ui.Button(
                label=platform.upper(),
                style=discord.ButtonStyle.primary,
                custom_id=platform
            ))

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ Cancelled.", ephemeral=True)
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == int(self.user_id)

    async def interaction_handler(self, interaction: discord.Interaction):
        platform = interaction.data['custom_id']
        if platform in ["steam", "epic", "psn", "xbl"]:
            linked_users[str(self.user_id)] = {"platform": platform, "username": self.username}
            save_linked_users(linked_users)
            await interaction.response.send_message(
                f"✅ Linked `{self.username}` on **{platform.upper()}**.", ephemeral=True)
            await send_log(f"🔗 User {interaction.user} linked Rocket League account: {self.username} on {platform.upper()}")
            self.stop()

    async def on_interaction(self, interaction: discord.Interaction):
        await self.interaction_handler(interaction)

@tree.command(name="link", description="Link your Rocket League username to your Discord account")
@app_commands.describe(username="Your Rocket League username")
async def link_command(interaction: discord.Interaction, username: str):
    view = PlatformButtonView(username, str(interaction.user.id))
    await interaction.response.send_message(
        f"👋 {interaction.user.mention}, choose your platform for **{username}**:", view=view, ephemeral=True
    )

@tree.command(name="stats", description="View your Rocket League stats")
async def stats_command(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id not in linked_users:
        await interaction.response.send_message(
            "❌ You haven't linked your Rocket League account yet. Use `/link yourname`.", ephemeral=True)
        return

    platform = linked_users[user_id]["platform"]
    username = linked_users[user_id]["username"]

    url = f"https://api.tracker.gg/api/v2/rocket-league/standard/profile/{platform}/{username}"
    headers = {"TRN-Api-Key": TRN_API_KEY}
    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        await interaction.response.send_message("⚠️ Couldn't fetch your stats. Try again.", ephemeral=True)
        return

    stats = r.json()["data"]["segments"][0]["stats"]
    embed = discord.Embed(
        title=f"{username}'s Rocket League Stats",
        description=f"📊 Platform: `{platform.upper()}`",
        color=0xff6600
    )
    embed.set_thumbnail(url="https://www.rocketleague.com/_next/static/media/rocket-league.6f2c3b84.svg")
    embed.add_field(name="🏆 Rank", value=stats['rating']['displayValue'], inline=True)
    embed.add_field(name="🎯 MMR", value=stats['rating']['value'], inline=True)
    embed.add_field(name="✅ Wins", value=stats['wins']['value'], inline=True)
    embed.add_field(name="🥅 Goals", value=stats['goals']['value'], inline=True)

    await interaction.response.send_message(embed=embed)

@tree.command(name="unlink", description="Unlink your Rocket League account")
async def unlink_command(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id in linked_users:
        linked_users.pop(user_id)
        save_linked_users(linked_users)
        await interaction.response.send_message("✅ Your Rocket League account has been unlinked.", ephemeral=True)
        await send_log(f"❌ User {interaction.user} unlinked their Rocket League account.")
    else:
        await interaction.response.send_message("❌ You don't have an account linked.", ephemeral=True)

@tree.command(name="platform", description="Change your linked platform")
@app_commands.describe(platform="New platform to link")
async def platform_command(interaction: discord.Interaction, platform: str):
    user_id = str(interaction.user.id)
    platform = platform.lower()
    if platform not in ["steam", "epic", "psn", "xbl"]:
        await interaction.response.send_message("❌ Invalid platform. Choose from steam, epic, psn, xbl.", ephemeral=True)
        return

    if user_id not in linked_users:
        await interaction.response.send_message("❌ You have no linked account. Use `/link yourname` first.", ephemeral=True)
        return

    linked_users[user_id]["platform"] = platform
    save_linked_users(linked_users)
    await interaction.response.send_message(f"✅ Platform changed to **{platform.upper()}**.", ephemeral=True)
    await send_log(f"🔄 User {interaction.user} changed platform to {platform.upper()}.")

@tree.command(name="leaderboard", description="Show top 5 linked users by MMR")
async def leaderboard_command(interaction: discord.Interaction):
    if not linked_users:
        await interaction.response.send_message("No linked users found.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🚀 OctaneCore Leaderboard - Top 5 by MMR",
        color=0xff6600
    )

    results = []

    for user_id, info in linked_users.items():
        platform = info["platform"]
        username = info["username"]
        url = f"https://api.tracker.gg/api/v2/rocket-league/standard/profile/{platform}/{username}"
        headers = {"TRN-Api-Key": TRN_API_KEY}
        try:
            r = requests.get(url, headers=headers)
            if r.status_code == 200:
                stats = r.json()["data"]["segments"][0]["stats"]
                mmr = stats["rating"]["value"]
                results.append((username, platform, mmr))
        except Exception:
            pass

    results.sort(key=lambda x: x[2], reverse=True)
    top_5 = results[:5]

    if not top_5:
        await interaction.response.send_message("Could not fetch leaderboard data.", ephemeral=True)
        return

    for i, (username, platform, mmr) in enumerate(top_5, start=1):
        embed.add_field(name=f"{i}. {username} ({platform.upper()})", value=f"MMR: {mmr}", inline=False)

    await interaction.response.send_message(embed=embed)

@tree.command(name="help", description="Show commands list and usage")
async def help_command(interaction: discord.Interaction):
    help_text = """
**OctaneCore Commands:**
`/link <username>` - Link your Rocket League account.
`/stats` - Show your linked Rocket League stats.
`/unlink` - Unlink your Rocket League account.
`/platform <platform>` - Change your linked platform (steam, epic, psn, xbl).
`/leaderboard` - Show top 5 users by MMR.
`/help` - Show this help message.
"""
    await interaction.response.send_message(help_text, ephemeral=True)

@bot.event
async def on_ready():
    await tree.sync()
    await bot.change_presence(activity=discord.Game(name="Rocket League Stats! 🚗💨"))
    print(f"✅ OctaneCore is online as {bot.user}!")
    await send_log(f"✅ OctaneCore is online as {bot.user}!")

# Global error handler for command errors
@bot.event
async def on_command_error(ctx, error):
    error_msg = f"⚠️ Error in command `{ctx.command}` by user {ctx.author}:\n```{error}```"
    print(error_msg)
    if LOG_CHANNEL_ID != 0:
        channel = bot.get_channel(LOG_CHANNEL_ID)
        if channel:
            await channel.send(error_msg)

# Global error handler for app commands (slash commands)
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    error_msg = f"⚠️ Error in slash command by user {interaction.user}:\n```{error}```"
    print(error_msg)
    if LOG_CHANNEL_ID != 0:
        channel = bot.get_channel(LOG_CHANNEL_ID)
        if channel:
            await channel.send(error_msg)

bot.run(BOT_TOKEN)
