from dotenv import load_dotenv
load_dotenv()

import discord
from discord.ext import commands
import requests
import os

BOT_TOKEN = os.getenv('BOT_TOKEN')
TRN_API_KEY = os.getenv('TRN_API_KEY')

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

linked_users = {}

class PlatformButtonView(discord.ui.View):
    def __init__(self, username):
        super().__init__(timeout=30)
        self.username = username

        for platform in ["steam", "epic", "psn", "xbl"]:
            self.add_item(discord.ui.Button(
                label=platform.upper(),
                style=discord.ButtonStyle.primary,
                custom_id=platform
            ))

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ Cancelled!", ephemeral=True)
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

    async def on_timeout(self):
        pass

@bot.command()
async def link(ctx, username: str):
    view = PlatformButtonView(username)
    await ctx.send(
        f"👋 Hi {ctx.author.mention}, pick your platform for **{username}**:",
        view=view
    )

@bot.command()
async def stats(ctx):
    user_id = str(ctx.author.id)
    if user_id not in linked_users:
        await ctx.send("❌ You haven't linked your Rocket League account yet. Use `!link yourname`.")
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
        color=0xff6600
    )
    embed.set_thumbnail(url="https://www.rocketleague.com/_next/static/media/rocket-league.6f2c3b84.svg")
    embed.add_field(name="🏆 Rank", value=stats['rating']['displayValue'], inline=True)
    embed.add_field(name="🎯 MMR", value=stats['rating']['value'], inline=True)
    embed.add_field(name="✅ Wins", value=stats['wins']['value'], inline=True)
    embed.add_field(name="🥅 Goals", value=stats['goals']['value'], inline=True)

    await ctx.send(embed=embed)

@bot.event
async def on_ready():
    print(f"✅ OctaneCore is online!")

bot.run(BOT_TOKEN)
