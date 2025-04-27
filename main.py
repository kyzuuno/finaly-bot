import discord
from discord.ext import commands
from discord.ui import View, Select, Button
from flask import Flask
from threading import Thread
import re
import asyncio
import os

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
bot.persistent_views_added = False

custom_emojis = {
    "Tier Max ": "<:tiers_max:1358214837519257701>",
    "Ranked Ranks ": "<:master:1358336524902596698>",
    "Prestige": "<:prestige:1358336319155339414>",
    "Carry": "💪",
    "Buy Account": "🛒"
}

services = {
    "Tier Max ": "tier_max",
    "Ranked Ranks ": "ranked_ranks",
    "Prestige": "prestige",
    "Carry": "carry",
    "Buy Account": "buy_account"
}

staff_role_names = ["🎃・ Booster", "🦇・ Staff"]
ticket_category_name = "🎫・Tickets"
target_channel_id = 1357412702494003226


class TicketCloseButton(Button):
    def __init__(self, ticket_channel: discord.TextChannel):
        super().__init__(label="Close ticket", style=discord.ButtonStyle.danger, emoji="🔒")
        self.ticket_channel = ticket_channel

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("🔒 Closing the ticket in 5 seconds...", ephemeral=True)
        await self.ticket_channel.send("🔒 The ticket will be closed...")
        await asyncio.sleep(5)
        await self.ticket_channel.delete(reason="Ticket closed")


class AcceptBoostButton(Button):
    def __init__(self, ticket_channel: discord.TextChannel, client: discord.Member):
        super().__init__(label="Accept order", style=discord.ButtonStyle.success, emoji="🟢")
        self.ticket_channel = ticket_channel
        self.client = client
        self.accepted = False

    async def callback(self, interaction: discord.Interaction):
        booster = interaction.user
        booster_role = discord.utils.get(interaction.guild.roles, name="🎃・ Booster")

        if booster_role not in booster.roles:
            await interaction.response.send_message("❌ Only boosters can accept this order.", ephemeral=True)
            return

        if self.accepted:
            await interaction.response.send_message("⚠️ This ticket has already been accepted.", ephemeral=True)
            return

        self.accepted = True

        overwrites = self.ticket_channel.overwrites
        if booster_role:
            overwrites[booster_role] = discord.PermissionOverwrite(read_messages=False)

        overwrites[booster] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        overwrites[self.client] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        for role_name in staff_role_names:
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if role and role != booster_role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        await self.ticket_channel.edit(overwrites=overwrites)

        await interaction.response.send_message(f"✅ {booster.mention} has accepted the order!", ephemeral=False)
        await self.ticket_channel.send(f"👤 {booster.mention} is now handling the order for {self.client.mention}!")

        self.disabled = True
        await interaction.message.edit(view=self.view)


class ServiceSelect(Select):
    def __init__(self, bot, ctx_channel):
        self.bot = bot
        self.ctx_channel = ctx_channel
        options = [
            discord.SelectOption(label=label, value=value, emoji="✅")
            for label, value in services.items()
        ]
        super().__init__(placeholder="Choose your order", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        selected_value = self.values[0]
        service = next((label for label, value in services.items() if value == selected_value), selected_value)
        guild = interaction.guild

        ticket_category = discord.utils.get(guild.categories, name=ticket_category_name)

        await interaction.response.send_message(
            f"🛒 You chose : **{service}**. Creating a ticket...",
            ephemeral=True
        )

        if not ticket_category:
            ticket_category = await guild.create_category(ticket_category_name)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }

        staff_roles = [discord.utils.get(guild.roles, name=role_name) for role_name in staff_role_names]
        for role in staff_roles:
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        booster_role = discord.utils.get(guild.roles, name="🎃・ Booster")
        if booster_role:
            overwrites[booster_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        safe_name = re.sub(r"[^a-zA-Z0-9\-]", "", interaction.user.name.lower().replace(" ", "-"))
        channel_name = f"commande-{safe_name}-{interaction.user.discriminator}"

        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            category=ticket_category,
            reason="Commande de boost"
        )

        all_roles_to_mention = [r for r in staff_roles if r]
        if booster_role and booster_role not in all_roles_to_mention:
            all_roles_to_mention.append(booster_role)

        mentions = " ".join(role.mention for role in all_roles_to_mention)

        view = View(timeout=None)
        view.add_item(AcceptBoostButton(ticket_channel, interaction.user))
        view.add_item(TicketCloseButton(ticket_channel))

        await ticket_channel.send(
            f"{mentions} 🚀 {interaction.user.mention} a commandé **{service}**.",
            view=view
        )


async def send_boost_menu(channel):
    embed = discord.Embed(
        title="What Do We Boost/Carry/Offer :",
        color=discord.Color.purple()
    )

    embed.add_field(name=f"Tier Max {custom_emojis['Tier Max ']}", value="‎", inline=False)
    embed.add_field(name=f"Ranked Ranks {custom_emojis['Ranked Ranks ']}", value="‎", inline=False)
    embed.add_field(name=f"Prestige {custom_emojis['Prestige']}", value="‎", inline=False)
    embed.add_field(name=f"Carry {custom_emojis['Carry']}", value="‎", inline=False)
    embed.add_field(name=f"Buy Account {custom_emojis['Buy Account']}", value="‎", inline=False)

    embed.set_footer(text="Select a service to open a ticket")

    view = View(timeout=None)
    view.add_item(ServiceSelect(bot, channel))
    await channel.send(embed=embed, view=view)


@bot.event
async def on_ready():
    print(f"✅ Connecté en tant que {bot.user}")

    if not bot.persistent_views_added:
        try:
            view = View(timeout=None)
            view.add_item(ServiceSelect(bot, None))
            bot.add_view(view)
            print("🔧 Views persistantes ajoutées")
            bot.persistent_views_added = True
        except Exception as e:
            print(f"❌ Erreur en ajoutant la view persistante : {e}")

    channel = bot.get_channel(target_channel_id)
    if not channel:
        print("❌ Salon introuvable. Vérifie target_channel_id.")
        return

    async for message in channel.history(limit=20):
        if message.author == bot.user and message.embeds:
            if message.embeds[0].title.startswith("What Do We Boost/Carry"):
                print("⏭️ Menu déjà présent, on ne le renvoie pas.")
                return

    await send_boost_menu(channel)
    print("📨 Menu envoyé dans le salon.")


# Flask server to keep the bot alive
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()

# Lance le bot
bot.run(os.getenv('TOKEN_DC'))
