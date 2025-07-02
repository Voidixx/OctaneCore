import discord
from discord.ext import commands, tasks
import requests
import os
import json
import asyncio
import datetime
from datetime import timezone

BOT_TOKEN = os.environ['BOT_TOKEN']
TRN_API_KEY = os.environ['TRN_API_KEY']
LOG_CHANNEL_ID = int(os.environ['LOG_CHANNEL_ID'])  # Add this to your Render secrets

intents = discord.Intents.default()
intents.message_content = True
intents.presences = True
intents.members = True
bot = commands.Bot(command_prefix="/", intents=intents)

start_time = datetime.datetime.now(timezone.utc)

# Load linked users
try:
    with open("linked_users.json", "r") as f:
        linked_users = json.load(f)
except FileNotFoundError:
    linked_users = {}

def save_users():
    with open("linked_users.json", "w") as f:
        json.dump(linked_users, f, indent=2)

# Modal for linking
class PlatformModal(discord.ui.Modal, title="Link Your Rocket League Account"):
    username = discord.ui.TextInput(label="Username", placeholder="Enter your Rocket League username")
    platform = discord.ui.TextInput(label="Platform (epic, steam, psn, xbl)", placeholder="e.g. epic")

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        linked_users[user_id] = [self.platform.value.lower(), self.username.value]
        save_users()
        await interaction.response.send_message(
            f"✅ Linked `{self.username.value}` on `{self.platform.value}`!",
            ephemeral=True
        )

# Button for public linking
class LinkButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔗 Link Your Rocket League Account", style=discord.ButtonStyle.success)
    async def link_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PlatformModal())

# Command to post the button
@bot.command()
async def post_link_button(ctx):
    view = LinkButtonView()
    await ctx.send("🔧 Press the button to link your Rocket League account:", view=view)

# Command to show stats
@bot.command()
async def stats(ctx):
    user_id = str(ctx.author.id)
    if user_id not in linked_users:
        await ctx.send("❌ You haven't linked your Rocket League account yet. Use `/post_link_button`.")
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

# Confirmable restart
class RestartConfirmView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=30)
        self.ctx = ctx

    @discord.ui.button(label="✅ Confirm Restart", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command author can confirm the restart.", ephemeral=True)
            return

        await interaction.response.send_message("🔁 Restarting bot now...", ephemeral=True)

        save_users()
        uptime = datetime.datetime.now(timezone.utc) - start_time
        uptime_str = f"{uptime.seconds//3600}h {uptime.seconds//60%60}m {uptime.seconds%60}s"

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(
                f"🔁 Bot restarting (by {interaction.user.mention})\n🕒 Uptime: `{uptime_str}`"
            )

        await bot.change_presence(activity=discord.Game(name="Restarting..."))
        await asyncio.sleep(2)
        os._exit(0)

@bot.command()
@commands.is_owner()
async def restart(ctx):
    await ctx.send("⚠️ Are you sure you want to restart the bot?", view=RestartConfirmView(ctx))

# Status timer
@tasks.loop(seconds=60)
async def update_status():
    uptime = datetime.datetime.now(timezone.utc) - start_time
    h, m, s = uptime.seconds // 3600, (uptime.seconds // 60) % 60, uptime.seconds % 60
    await bot.change_presence(activity=discord.Game(name=f"Online for {h}h {m}m {s}s"))

# Bot startup
@bot.event
async def on_ready():
    print(f"✅ {bot.user.name} is online!")
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send("✅ Bot is online and ready!")
    update_status.start()

bot.run(BOT_TOKEN)
