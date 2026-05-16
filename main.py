# =========================
# Imports
# =========================
import os
import io
import discord
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv
import asyncio
import aiohttp

from flask import Flask
import threading

# Flask app
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# Start Flask server in background thread
threading.Thread(target=run_web).start()

# =========================
# Load environment
# =========================
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
APPLICATION_ID = int(os.getenv("APPLICATION_ID"))
CATEGORY_GENERAL_SUPPORT = int(os.getenv("CATEGORY_GENERAL_SUPPORT"))
CATEGORY_INTERNAL_AFFAIRS = int(os.getenv("CATEGORY_INTERNAL_AFFAIRS"))
CATEGORY_MANAGEMENT = int(os.getenv("CATEGORY_MANAGEMENT"))
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID"))
HIGH_RANK_ROLE_ID = int(os.getenv("HIGH_RANK_ROLE_ID"))
SENIOR_HIGH_RANK_ROLE_ID = int(os.getenv("SENIOR_HIGH_RANK_ROLE_ID"))
DIRECTOR_ROLE_ID = int(os.getenv("DIRECTOR_ROLE_ID"))
FOUNDERSHIP_ROLE_ID = int(os.getenv("FOUNDERSHIP_ROLE_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))

# =========================
# GLOBAL COUNTER
# =========================
ticket_counter = 0

# =========================
# Bot
# =========================
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=discord.Intents.all(),
            application_id=APPLICATION_ID
        )

    async def setup_hook(self):
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

bot = MyBot()

# =========================
# CLOSE MODAL
# =========================
class CloseReasonModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title="Close Ticket")
        self.view = view

        self.reason = discord.ui.TextInput(
            label="Reason for closing",
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        transcript = await self.view.save_transcript(interaction.channel)

        file = discord.File(
            fp=io.StringIO(transcript),
            filename=f"{interaction.channel.name}.txt"
    )

        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)

        embed = discord.Embed(
            title="Ticket Closed",
            description=f"{interaction.channel.name}\nClosed by {interaction.user.mention}\nReason: {self.reason.value}",
            color=discord.Color.from_rgb(255, 255, 255)  # white embed
    )

        await log_channel.send(embed=embed, file=file)

        try:
            if interaction.channel.topic:
                user_id = int(interaction.channel.topic.split('-')[0])
                user = interaction.guild.get_member(user_id)
                if user:
                    await user.send(
                        content=f"Here is the transcript for your ticket **{interaction.channel.name}**:",
                        file=file
                )
        except Exception as e:
            print(f"Could not DM user: {e}")

    # Use followup to send your ephemeral message safely
        await interaction.followup.send("Closing ticket...", ephemeral=True)

        await interaction.channel.delete()

# =========================
# BUTTONS (STAFF)
# =========================
class TicketButtons(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    async def save_transcript(self, channel):
        messages = []
        async for msg in channel.history(limit=None, oldest_first=True):
            messages.append(f"{msg.author}: {msg.content}")
        return "\n".join(messages)

    @discord.ui.button(
        label="Close",
        style=discord.ButtonStyle.secondary,
        emoji="<:lock:1500781900179046490>",
        custom_id="ticket_close_button"
    )
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Closing ticket...", ephemeral=True)
        self.bot.loop.create_task(self._process_close(interaction, reason=None))

    @discord.ui.button(
        label="Close with Reason",
        style=discord.ButtonStyle.secondary,
        emoji="<:lock:1500781900179046490>",
        custom_id="ticket_close_reason_button"
    )
    async def close_reason(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CloseReasonModal(self))

    async def _process_close(self, interaction: discord.Interaction, reason=None):
        transcript = await self.save_transcript(interaction.channel)
        file = discord.File(io.StringIO(transcript), filename=f"{interaction.channel.name}.txt")

        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
        embed = discord.Embed(
            title="Ticket Closed",
            description=f"{interaction.channel.name} closed by {interaction.user.mention}" +
                        (f"\nReason: {reason}" if reason else ""),
            color=discord.Color.from_rgb(255, 255, 255)
        )
        await log_channel.send(embed=embed, file=file)

        # DM ticket creator
        try:
            if interaction.channel.topic:
                user_id = int(interaction.channel.topic.split('-')[0])
                user = interaction.guild.get_member(user_id)
                if user:
                    await user.send(
                        content=f"Here is the transcript for your ticket **{interaction.channel.name}**:",
                        file=file
                    )
        except Exception as e:
            print(f"Could not DM user: {e}")

        await interaction.channel.delete()

    @discord.ui.button(
        label="Claim",
        style=discord.ButtonStyle.secondary,
        emoji="<:people:1500636270156841031>",
        custom_id="ticket_claim_button"
    )
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel

        if channel.topic and "claimed" in channel.topic:
            await interaction.response.send_message(
                "<:Xmark:1500777980694237274> This ticket is already claimed.",
                ephemeral=True
            )
            return

        try:
            user_id = int(channel.topic)
            user = interaction.guild.get_member(user_id)
        except:
            user = None

        base_name = channel.name.split("-")[0]
        display = user.display_name if user else "user"
        new_name = f"{base_name}-{display}".lower().replace(" ", "-")

        await channel.edit(
            name=new_name,
            topic=f"{channel.topic}-claimed" if channel.topic else "claimed"
        )

        await interaction.response.send_message(
            f"<:Cmark:1500778023799099403> {interaction.user.mention} claimed this ticket."
        )

# =========================
# USER BUTTONS (Persistent)
# =========================
class TicketUserButtons(discord.ui.View):
    def __init__(self, ticket_owner_id):
        super().__init__(timeout=None)
        self.ticket_owner_id = ticket_owner_id

    @discord.ui.button(
        label="Request Close",
        style=discord.ButtonStyle.danger,
        emoji="<:lock:1500781900179046490>",
        custom_id="request_close_button"
    )
    async def request_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ticket_owner_id:
            await interaction.response.send_message(
                "You cannot request closing this ticket because you didn't create it.",
                ephemeral=True
            )
            return

        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
        await log_channel.send(
            f"User {interaction.user.mention} has requested to close ticket {interaction.channel.mention}."
        )

        await interaction.response.send_message(
            "Your request to close this ticket has been sent to the staff.",
            ephemeral=True
        )

# =========================
# FULL COMBINED VIEW (Staff + User)
# =========================
class TicketFullView(discord.ui.View):
    def __init__(self, bot, ticket_owner_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.ticket_owner_id = ticket_owner_id

        # Add staff buttons
        staff_buttons = TicketButtons(bot)
        self.add_item(staff_buttons.children[0])  # Close
        self.add_item(staff_buttons.children[1])  # Close with Reason
        self.add_item(staff_buttons.children[2])  # Claim

        # Add user button
        user_buttons = TicketUserButtons(ticket_owner_id)
        self.add_item(user_buttons.children[0])  # Request Close

# =========================
# MODAL (CREATE TICKET)
# =========================
class TicketModal(discord.ui.Modal):
    def __init__(self, title, role_id, bot):
        super().__init__(title=title)
        self.role_id = role_id
        self.ticket_type = title
        self.bot = bot

        self.reason = discord.ui.TextInput(
            label="Reason",
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        # Defer inside the modal for long operations
        await interaction.response.defer(ephemeral=True)

        global ticket_counter
        guild = interaction.guild

        # Select category based on ticket type
        if self.ticket_type == "General Support":
            category = guild.get_channel(CATEGORY_GENERAL_SUPPORT)
        elif self.ticket_type == "Internal Affairs":
            category = guild.get_channel(CATEGORY_INTERNAL_AFFAIRS)
        elif self.ticket_type == "Management":
            category = guild.get_channel(CATEGORY_MANAGEMENT)
        else:
            category = guild.get_channel(CATEGORY_GENERAL_SUPPORT)

        # List of roles that can see General Support tickets
        GENERAL_SUPPORT_ROLES = [
            ADMIN_ROLE_ID,
            HIGH_RANK_ROLE_ID,
            SENIOR_HIGH_RANK_ROLE_ID,
            DIRECTOR_ROLE_ID,
            FOUNDERSHIP_ROLE_ID
        ]

        # Set permission overwrites
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        if self.ticket_type == "General Support":
            for role_id in GENERAL_SUPPORT_ROLES:
                role = guild.get_role(role_id)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        else:
            # For other ticket types, only give permission to the assigned role
            role = guild.get_role(self.role_id)
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        # Prevent duplicates
        for ch in category.channels:
            if ch.topic and str(interaction.user.id) == ch.topic.split('-')[0]:
                await interaction.followup.send(
                    "<:Xmark:1500777980694237274> You already have an open ticket.",
                    ephemeral=True
                )
                return

        # Ticket numbering
        ticket_counter += 1
        ticket_number = str(ticket_counter).zfill(3)

        # Create ticket channel
        channel = await guild.create_text_channel(
            name=f"ticket-{ticket_number}",
            category=category,
            topic=str(interaction.user.id),
            overwrites=overwrites
        )

        # Send final response as followup
        await interaction.followup.send(
            f"<:Cmark:1500778023799099403> Ticket created: {channel.mention}",
            ephemeral=True
        )

        # ================= EMBED MESSAGES (unchanged) =================
        embed1 = discord.Embed(
            title=self.ticket_type,
            description=(
                f"You have successfully created a **{self.ticket_type}** ticket. "
                "Please await a response from one of our support members, do not ping them.\n\n"
                "If no one responds within 10 hours, you are free to ping a support member once.\n\n"
                "*Do note that if the ticket opener (you) fails to respond within 8 hours, "
                "this ticket will be closed without your permission.*"
            ),
            color=discord.Color.from_rgb(255, 255, 255)
        )

        embed2 = discord.Embed(
            title=self.ticket_type,
            description=f"**Reason:**\n{self.reason.value}",
            color=discord.Color.from_rgb(255, 255, 255)
        )

        embed1.set_footer(
            text="Powered by Springfield",
            icon_url="https://media.discordapp.net/attachments/1500468168282345472/1500780381048279080/asp_logo_1.png"
        )

        embed2.set_footer(
            text="Powered by Springfield",
            icon_url="https://media.discordapp.net/attachments/1500468168282345472/1500780381048279080/asp_logo_1.png"
        )

        # Only one message with both role + ticket creator ping
        await channel.send(
            content=f"{interaction.user.mention}",  # Ping ticket creator only (roles already notified via view)
            embeds=[embed1, embed2],
            view=TicketFullView(self.bot, interaction.user.id)
        )

# =========================
# SELECT
# =========================
class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="General Support",
                value="general_support",
                emoji="<:people:1500636270156841031>"
            ),
            discord.SelectOption(
                label="Internal Affairs Support",
                value="internal_affairs",
                emoji="<:hammer:1500636179505352754>"
            ),
            discord.SelectOption(
                label="Management Support",
                value="management",
                emoji="<:shield:1500636322103038054>"
            )
        ]
        super().__init__(
            placeholder="Choose a ticket type...",
            options=options,
            custom_id="persistent_ticket_select"
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "general_support":
            await interaction.response.send_modal(TicketModal("General Support", ADMIN_ROLE_ID, interaction.client))
        elif self.values[0] == "internal_affairs":
            await interaction.response.send_modal(TicketModal("Internal Affairs", HIGH_RANK_ROLE_ID, interaction.client))
        elif self.values[0] == "management":
            await interaction.response.send_modal(TicketModal("Management", SENIOR_HIGH_RANK_ROLE_ID, interaction.client))

# =========================
# VIEW
# =========================
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

# =========================
# PANEL (UNCHANGED)
# =========================
async def send_ticket_panel(channel):

    view = TicketView()

    banner_embed = discord.Embed(color=discord.Color.from_rgb(255, 255, 255))
    banner_embed.set_image(url="https://media.discordapp.net/attachments/1500468168282345472/1500472482895757363/image.png")

    content_embed = discord.Embed(
        title="<:sf:1500771748839292938> Support Centre",
        description="> Our assistance dashboard is here for our members to easily contact our support team through our various ticket options. Pick the one that you think best supports your issue(s) and await a respond from a support member.",
        color=discord.Color.from_rgb(255, 255, 255)
    )

    content_embed.add_field(name="<:people:1500636270156841031> General Support", value="➜  Questions\n ➜  Staff Transfers\n ➜  General Problems", inline=True)
    content_embed.add_field(name="<:hammer:1500636179505352754> Internal Affairs", value="➜  Report Staff\n ➜  Express Concerns\n ➜  Staff Issues", inline=True)
    content_embed.add_field(name="<:shield:1500636322103038054> Management", value="➜  Questions requiring SHR\n ➜  Partnerships\n ➜  Paid Advertisements", inline=True)

    content_embed.set_image(url="https://media.discordapp.net/attachments/1500468168282345472/1500472229668847748/image.png")
    content_embed.set_footer(
        text="Powered by Springfield",
        icon_url="https://media.discordapp.net/attachments/1500468168282345472/1500780381048279080/asp_logo_1.png?ex=69f9ae25&is=69f85ca5&hm=47b1a7896d11b2f7a7ba22fc009cf87a89c4f5565a4768cd5ed6ee09d3e5b0a2&animated=true"
    )

    await channel.send(embeds=[banner_embed, content_embed], view=view)

# =========================
# Moderation Role System
# =========================

MOD_ROLE_IDS = [
    int(os.getenv("MODPERM_ROLE_ID"))
]

async def send_embed(ctx, title, description, color=discord.Color.from_rgb(255, 255, 255)):
    embed = discord.Embed(title=title, description=description, color=color)
    if ctx.response.is_done():
        await ctx.followup.send(embed=embed)
    else:
        await ctx.response.send_message(embed=embed)

async def is_allowed_user(interaction: discord.Interaction):
    if not interaction.guild:
        return False

    user_role_ids = [role.id for role in interaction.user.roles]

    if not any(role_id in MOD_ROLE_IDS for role_id in user_role_ids):
        await send_embed(
            interaction,
            "<:Xmark:1500777980694237274> Permission Denied",
            "You don't have permission to use this command.",
            discord.Color.red()
        )
        return False

    return True

# =========================
# BAN
# =========================
@bot.tree.command(name="ban", description="Ban a member from the server")
@app_commands.describe(user="User to ban", reason="Reason for banning")
async def ban_member(interaction: discord.Interaction, user: discord.Member, reason: str):

    if not await is_allowed_user(interaction):
        return

    try:
        await interaction.guild.ban(user, reason=reason)
        await send_embed(interaction, "<:Cmark:1500778023799099403> Member Banned", f"{user.mention} has been banned for: {reason}")
    except discord.Forbidden:
        await send_embed(interaction, "Error", "I do not have permission to ban members.")


# =========================
# UNBAN
# =========================
@bot.tree.command(name="unban", description="Unban a member")
@app_commands.describe(user_id="User ID", reason="Reason")
async def unban_member(interaction: discord.Interaction, user_id: int, reason: str):

    if not await is_allowed_user(interaction):
        return

    try:
        ban_entry = await interaction.guild.fetch_ban(discord.Object(id=user_id))
        await interaction.guild.unban(ban_entry.user, reason=reason)
        await send_embed(interaction, "<:Cmark:1500778023799099403> Member Unbanned", f"{ban_entry.user} has been unbanned for: {reason}")
    except discord.NotFound:
        await send_embed(interaction, "Error", "User is not banned or invalid ID.")


# =========================
# KICK
# =========================
@bot.tree.command(name="kick", description="Kick a member")
@app_commands.describe(user="User to kick", reason="Reason")
async def kick_member(interaction: discord.Interaction, user: discord.Member, reason: str):

    if not await is_allowed_user(interaction):
        return

    try:
        await user.kick(reason=reason)
        await send_embed(interaction, "<:Cmark:1500778023799099403> Member Kicked", f"{user.mention} has been kicked for: {reason}")
    except discord.Forbidden:
        await send_embed(interaction, "Error", "I do not have permission to kick members.")


# =========================
# TIMEOUT
# =========================
@bot.tree.command(name="timeout", description="Timeout a member")
@app_commands.describe(user="User", time="1m 1h 1d", reason="Reason")
async def timeout_member(interaction: discord.Interaction, user: discord.Member, time: str, reason: str):

    if not await is_allowed_user(interaction):
        return

    try:
        time_mapping = {
            "m": 60,
            "h": 3600,
            "d": 86400
        }

        duration = int(time[:-1]) * time_mapping[time[-1]]

        await user.timeout(
            discord.utils.utcnow() + discord.timedelta(seconds=duration),
            reason=reason
        )

        await send_embed(interaction, "<:Cmark:1500778023799099403> Member Timed Out", f"{user.mention} has been timed out for: {reason}")

    except Exception:
        await send_embed(interaction, "Error", "Invalid format (use 1m, 1h, 1d).")


# =========================
# UNTIMEOUT
# =========================
@bot.tree.command(name="untimeout", description="Remove timeout")
@app_commands.describe(user="User", reason="Reason")
async def untimeout_member(interaction: discord.Interaction, user: discord.Member, reason: str):

    if not await is_allowed_user(interaction):
        return

    try:
        await user.timeout(None, reason=reason)
        await send_embed(interaction, "<:Cmark:1500778023799099403> Timeout Removed", f"{user.mention} is no longer timed out.")
    except discord.Forbidden:
        await send_embed(interaction, "Error", "I do not have permission.")


# =========================
# MUTE
# =========================
@bot.tree.command(name="mute", description="Mute a member")
@app_commands.describe(user="User", reason="Reason")
async def mute_member(interaction: discord.Interaction, user: discord.Member, reason: str):

    if not await is_allowed_user(interaction):
        return

    mute_role = discord.utils.get(interaction.guild.roles, name="Muted")

    if not mute_role:
        await send_embed(interaction, "Error", "Muted role not found.")
        return

    try:
        await user.add_roles(mute_role, reason=reason)
        await send_embed(interaction, "<:Cmark:1500778023799099403> Member Muted", f"{user.mention} has been muted.")
    except discord.Forbidden:
        await send_embed(interaction, "Error", "Missing permissions.")


# =========================
# UNMUTE
# =========================
@bot.tree.command(name="unmute", description="Unmute a member")
@app_commands.describe(user="User", reason="Reason")
async def unmute_member(interaction: discord.Interaction, user: discord.Member, reason: str):

    if not await is_allowed_user(interaction):
        return

    mute_role = discord.utils.get(interaction.guild.roles, name="Muted")

    if mute_role not in user.roles:
        await send_embed(interaction, "Error", "User is not muted.")
        return

    try:
        await user.remove_roles(mute_role, reason=reason)
        await send_embed(interaction, "<:Cmark:1500778023799099403> Member Unmuted", f"{user.mention} has been unmuted.")
    except discord.Forbidden:
        await send_embed(interaction, "Error", "Missing permissions.")


# =========================
# ROLE ADD
# =========================
@bot.tree.command(name="role", description="Add role")
@app_commands.describe(user="User", role="Role", reason="Reason")
async def role_member(interaction: discord.Interaction, user: discord.Member, role: discord.Role, reason: str):

    if not await is_allowed_user(interaction):
        return

    try:
        await user.add_roles(role, reason=reason)
        await send_embed(interaction, "<:Cmark:1500778023799099403> Role Added", f"{role.name} given to {user.mention}")
    except discord.Forbidden:
        await send_embed(interaction, "Error", "Missing permissions.")


# =========================
# ROLE REMOVE
# =========================
@bot.tree.command(name="unrole", description="Remove role")
@app_commands.describe(user="User", role="Role", reason="Reason")
async def unrole_member(interaction: discord.Interaction, user: discord.Member, role: discord.Role, reason: str):

    if not await is_allowed_user(interaction):
        return

    try:
        await user.remove_roles(role, reason=reason)
        await send_embed(interaction, "<:Cmark:1500778023799099403> Role Removed", f"{role.name} removed from {user.mention}")
    except discord.Forbidden:
        await send_embed(interaction, "Error", "Missing permissions.")
        
# =========================
# COMMANDS
# =========================
@bot.command()
async def panel(ctx):
    await send_ticket_panel(ctx.channel)
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass  # Bot lacks permission to delete the message

#---------------------------------------------------------------------------------------
import json
import discord
from discord.ext import commands

SESSION_VOTE_FILE = "session_votes.json"

def load_votes():
    try:
        with open(SESSION_VOTE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_votes(data):
    with open(SESSION_VOTE_FILE, "w") as f:
        json.dump(data, f, indent=4)


class SessionVoteView(discord.ui.View):
    def __init__(self, author: discord.Member = None, message_id: int = None):
        super().__init__(timeout=None)

        self.author = author
        self.message_id = str(message_id) if message_id else None
        self.max_votes = 7

        data = load_votes()
        saved = data.get(self.message_id, {}) if self.message_id else {}

        self.voters = saved.get("voters", [])
        self.author_id = saved.get("author_id", author.id if author else None)

    def save(self):
        data = load_votes()

        data[self.message_id] = {
            "voters": self.voters,
            "author_id": self.author_id
        }

        save_votes(data)

    def get_vote_label(self):
        return f"Vote ({len(self.voters)}/{self.max_votes})"

    async def update_buttons(self, interaction):
        for item in self.children:
            if item.custom_id == "session_vote_button":
                item.label = self.get_vote_label()

            if len(self.voters) >= self.max_votes:
                item.disabled = True

        await interaction.message.edit(view=self)

    # =========================
    # VOTE BUTTON (TOGGLE)
    # =========================
    @discord.ui.button(
        label="Vote (0/7)",
        style=discord.ButtonStyle.secondary,
        emoji="<:Cmark:1500778023799099403>",
        custom_id="session_vote_button"
    )
    async def vote_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id in self.voters:
            self.voters.remove(interaction.user.id)
            self.save()

            await self.update_buttons(interaction)

            await interaction.response.send_message(
                "<:Cmark:1500778023799099403> Your vote has been removed.",
                ephemeral=True
            )
            return

        self.voters.append(interaction.user.id)
        self.save()

        await self.update_buttons(interaction)

        await interaction.response.send_message(
            "<:Cmark:1500778023799099403> You have voted for a Session.",
            ephemeral=True
        )

        if len(self.voters) == self.max_votes:
            await interaction.followup.send("<:Cmark:1500778023799099403> Session vote passed!")

    # =========================
    # VIEW VOTERS BUTTON
    # =========================
    @discord.ui.button(
        label="Voters",
        style=discord.ButtonStyle.secondary,
        emoji="<:people:1500636270156841031>",
        custom_id="session_voters_button"
    )
    async def voters_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not self.voters:
            desc = "No voters yet."
        else:
            desc = "\n".join(
                f"{i+1}. <@{uid}>"
                for i, uid in enumerate(self.voters)
            )

        embed = discord.Embed(
            title="<:control:1501145463343157249> Session Voters",
            description=desc,
            color=discord.Color.from_rgb(255, 255, 255)
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

# =========================
# SLASH COMMAND (MUST BE OUTSIDE CLASS)
# =========================
async def create_session_vote(ctx_or_interaction, user, channel, is_slash: bool):
    embed = discord.Embed(
        title="<:control:1501145463343157249> Session Vote",
        description="> Press the Vote button below to vote for the session. If this vote receives at least 7 votes, a session will be started! If you vote, you are **required** to join. Failure to do so may result in moderation.",
        color=discord.Color.from_rgb(255, 255, 255)
    )

    embed.set_author(
        name="Springfield Roleplay",
        icon_url="https://cdn.discordapp.com/attachments/1500468168282345472/1500780381048279080/asp_logo_1.png"
    )

    embed.set_footer(
        text=f"Session vote initiated by {user.display_name}",
        icon_url=user.display_avatar.url
    )

    ping_line = "-# <:bell:1501146811929202728> | <@&1493630980471259172> @here"

    if is_slash:
        await ctx_or_interaction.response.send_message(
            content=ping_line,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(everyone=True, roles=True)
        )
        try:
            msg = await ctx_or_interaction.original_response()
        except discord.NotFound:
            # Original response not found, send new
            msg = await ctx_or_interaction.followup.send(
                content=ping_line,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(everyone=True, roles=True),
                wait=True
            )
    else:
        msg = await channel.send(
            content=ping_line,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(everyone=True, roles=True)
        )

    # Create the vote view
    view = SessionVoteView(user, msg.id)

    # Safely edit the view
    try:
        await msg.edit(view=view)
    except discord.NotFound:
        # If message was deleted meanwhile, resend it
        msg = await channel.send(
            content=ping_line,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(everyone=True, roles=True),
            view=view
        )

    # Save vote state
    view.save()


@bot.tree.command(name="sessionvote", description="Start a session vote")
async def session_vote(interaction: discord.Interaction):
    await create_session_vote(interaction, interaction.user, interaction.channel, True)

@bot.command(name="sessionvote")
async def sessionvote_prefix(ctx):
    await create_session_vote(ctx, ctx.author, ctx.channel, False)
    
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass  # Bot lacks permission to delete
    except discord.NotFound:
        pass  # Message was already deleted
#--------------------------------------------------------------------------------
# =========================
# SHARED FUNCTION
# =========================
async def create_session_end(ctx_or_interaction, user, channel, is_slash: bool):

    embed = discord.Embed(
        title="<:control:1501145463343157249> Session Shutdown",
        description="> The in-game server has now shutdown. A new session will be initiated by server management at a later time. Thank you for joining! <:warn:1501164879871217806> Please do not join the in-game server at this time. You may be moderated if you do so.",
        color=discord.Color.red()
    )

    embed.set_author(
        name="Springfield Roleplay",
        icon_url="https://cdn.discordapp.com/attachments/1500468168282345472/1500780381048279080/asp_logo_1.png"
    )

    embed.set_footer(
        text=f"Session shutdown by {user.display_name}",
        icon_url=user.display_avatar.url
    )

    # =========================
    # SEND MESSAGE
    # =========================
    if is_slash:
        await ctx_or_interaction.response.send_message(embed=embed)
    else:
        await channel.send(embed=embed)


# =========================
# SLASH COMMAND
# =========================
@bot.tree.command(name="sessionend", description="End the current session")
async def session_end(interaction: discord.Interaction):

    await create_session_end(
        interaction,
        interaction.user,
        interaction.channel,
        True
    )


# =========================
# PREFIX COMMAND
# =========================
@bot.command(name="sessionend")
async def sessionend_prefix(ctx):
    await create_session_end(ctx, ctx.author, ctx.channel, False)
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass
    
# =========================
# SHARED FUNCTION
# =========================
server_code = "SPFRPX"

# =========================
# MULTI-SESSION GLOBALS
# =========================
session_messages = {
    "full": None,
    "low": None,
    "start": None
}

SESSION_FILE = "sessions.json"

# =========================
# PERSISTENCE FUNCTIONS
# =========================
def load_session():
    if not os.path.exists(SESSION_FILE):
        return {"full": None, "low": None, "start": None}

    with open(SESSION_FILE, "r") as f:
        return json.load(f)


def save_session(data):
    with open(SESSION_FILE, "w") as f:
        json.dump(data, f, indent=4)

# =========================
# ER:LC API (Fixed)
# =========================
async def get_player_count():
    url = "https://api.policeroleplay.community/v2/server?Players=true"
    headers = {
        "server-key": os.getenv("ERLC_API_KEY")
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as r:
            data = await r.json()
            players = data.get("Players", [])
            current = len(players)
            max_players = data.get("MaxPlayers", 40)
            return current, max_players

# =========================
# CREATE SESSION EMBED FUNCTION
# =========================
async def create_session(ctx_or_interaction, user, channel, session_type: str, is_slash: bool):
    """
    session_type: "full", "low", or "start"
    """
    current, max_players = await get_player_count()

    if session_type == "full":
        title = "<:control:1501145463343157249> Session Full!"
        description = "> The in-game session is now **FULL!** Keep trying to join for some amazing roleplays!"
        color = discord.Color.yellow()
        content = "-# <:bell:1501146811929202728> | <@&1493630980471259172> @here"
    elif session_type == "low":
        title = "<:control:1501145463343157249> Session Low!"
        description = "> The in-game session is running **LOW!** Join quickly before it fills up!"
        color = discord.Color.yellow()
        content = "-# <:bell:1501146811929202728> | <@&1493630980471259172> @here"
    elif session_type == "start":
        title = "<:control:1501145463343157249> Session Start-up!"
        description = "> The in-game session is now **FULL!** Keep trying to join for some amazing roleplays!"
        color = discord.Color.green()
        content = "-# <:bell:1501146811929202728> | <@&1493630980471259172> @here"
    else:
        raise ValueError("Invalid session type")

    embed = discord.Embed(
        title=title,
        description=description,
        color=color
    )

    embed.add_field(
        name="<:control:1501145463343157249> Server Information:",
        value=(
            f"<:RA:1502630515826491454> **Server Name:** Springfield Roleplay | New | Realistic\n"
            f"<:RA:1502630515826491454> **Server Players:** {current}/{max_players}\n"
            f"<:RA:1502630515826491454> **Server Code:** [SPFRPX](https://www.roblox.com/games/start?placeId=2534724415&privateServerLinkCode={server_code})\n"
            f"<:RA:1502630515826491454> **Server Owner:** [RETINKOW9](https://www.roblox.com/users/1626792051/profile)"
        ),
        inline=True
    )
    embed.set_author(
        name="Springfield Roleplay",
        icon_url="https://cdn.discordapp.com/attachments/1500468168282345472/1500780381048279080/asp_logo_1.png"
    )

    embed.set_footer(
        text=f"Session {session_type} initiated by {user.display_name}",
        icon_url=user.display_avatar.url
    )

    if is_slash:
        await ctx_or_interaction.response.send_message(
            content=content,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(everyone=True, roles=True)
        )
        msg = await ctx_or_interaction.original_response()
    else:
        msg = await channel.send(
            content=content,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(everyone=True, roles=True)
        )

    session_messages[session_type] = msg

    data = load_session()
    data[session_type] = {"channel_id": msg.channel.id, "message_id": msg.id}
    save_session(data)

    if not update_players_embed.is_running():
        update_players_embed.start()

# =========================
# AUTO UPDATE LOOP
# =========================
@tasks.loop(minutes=1)
async def update_players_embed():
    current, max_players = await get_player_count()

    for key in ["full", "low", "start"]:
        msg = session_messages.get(key)
        if not msg:
            continue

        try:
            embed = msg.embeds[0]
            embed.set_field_at(
                0,
                name="<:control:1501145463343157249> Server Information:",
                value=(
                    f"<:RA:1502630515826491454> **Server Name:** Springfield Roleplay | New | Realistic\n"
                    f"<:RA:1502630515826491454> **Server Players:** {current}/{max_players}\n"
                    f"<:RA:1502630515826491454> **Server Code:** [SPFRPX](https://www.roblox.com/games/start?placeId=2534724415&privateServerLinkCode={server_code})\n"
                    f"<:RA:1502630515826491454> **Server Owner:** [RETINKOW9](https://www.roblox.com/users/1626792051/profile)"
                ),
                inline=True
            )
            await msg.edit(embed=embed)
        except discord.NotFound:
            session_messages[key] = None

# =========================
# SLASH COMMANDS
# =========================
@bot.tree.command(name="sessionfull", description="Session Full")
async def session_full(interaction: discord.Interaction):
    await create_session(interaction, interaction.user, interaction.channel, "full", True)

@bot.tree.command(name="sessionlow", description="Session Low")
async def session_low(interaction: discord.Interaction):
    await create_session(interaction, interaction.user, interaction.channel, "low", True)

@bot.tree.command(name="sessionstart", description="Session Start")
async def session_start(interaction: discord.Interaction):
    await create_session(interaction, interaction.user, interaction.channel, "start", True)

# =========================
# PREFIX COMMANDS
# =========================
# =========================
# PREFIX COMMANDS
# =========================
@bot.command(name="sessionfull")
async def session_full_prefix(ctx):
    await create_session(ctx, ctx.author, ctx.channel, "full", False)
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass  # Bot doesn't have permission to delete messages

@bot.command(name="sessionlow")
async def session_low_prefix(ctx):
    await create_session(ctx, ctx.author, ctx.channel, "low", False)
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass

@bot.command(name="sessionstart")
async def session_start_prefix(ctx):
    await create_session(ctx, ctx.author, ctx.channel, "start", False)
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass
#----------------------------------------------------------------------------------------------------------
# =========================
# ER:LC API (Safe)
# =========================
async def get_server_info():
    url = "https://api.policeroleplay.community/v2/server?Players=true&Queue=true&Staff=true"
    headers = {"server-key": os.getenv("ERLC_API_KEY")}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as r:
            text = await r.text()
            try:
                data = json.loads(text)
            except Exception:
                print(f"[ER:LC API] Invalid JSON response:\n{text}")
                return {
                    "current_players": 0,
                    "max_players": 0,
                    "queue_count": 0,
                    "staff_count": 0,
                    "join_code": "SPFRPx"
                }

            if not isinstance(data, dict):
                print(f"[ER:LC API] Response is not a dict:\n{data}")
                return {
                    "current_players": 0,
                    "max_players": 0,
                    "queue_count": 0,
                    "staff_count": 0,
                    "join_code": "SPFRPx"
                }

            # Players & Queue
            current_players = data.get("CurrentPlayers", 0) or 0
            max_players = data.get("MaxPlayers", 0) or 0
            queue_count = len(data.get("Queue", []) or [])

            # Staff currently in-game
            staff_roles = ["Server Administrator", "Server Owner", "Server Moderator"]
            staff_in_game = 0
            players = data.get("Players", [])
            for p in players:
                perm = p.get("Permission", "")
                if any(role in perm for role in staff_roles):
                    staff_in_game += 1

            join_code = data.get("JoinKey", "SPFRPx") or "SPFRPx"

            return {
                "current_players": current_players,
                "max_players": max_players,
                "queue_count": queue_count,
                "staff_count": staff_in_game,
                "join_code": join_code
            }

# =========================
# Persistent View
# =========================
class ERLCView(discord.ui.View):
    def __init__(self, join_code: str = "SPFRPx"):
        super().__init__(timeout=None)

        join_button = discord.ui.Button(
            label="Join Server",
            style=discord.ButtonStyle.link,
            url=f"https://policeroleplay.community/join/{join_code}"
        )
        self.add_item(join_button)

        refresh_button = discord.ui.Button(
            label="Refresh",
            style=discord.ButtonStyle.secondary,
            custom_id="refresh_button"
        )
        refresh_button.callback = self.refresh_callback
        self.add_item(refresh_button)

    async def refresh_callback(self, interaction: discord.Interaction):
        # ✅ Defer interaction immediately to prevent Unknown Interaction errors
        await interaction.response.defer()

        info = await get_server_info()
        embed = discord.Embed(title="", color=discord.Color.green())

        embed.add_field(
            name="General:",
            value=(
                f"> **Server Name:** `Springfield Roleplay | New | Realistic`\n"
                f"> **Join Code:** `SPFRPx`"
            ),
            inline=False
        )

        embed.add_field(
            name="Players:",
            value=(
                f"> **Current Players:** `{info['current_players']}/{info['max_players']}`\n"
                f"> **Queue:** `{info['queue_count']} players`\n"
                f"> **Staff Online:** `{info['staff_count']} total`"
            ),
            inline=False
        )

        embed.set_author(
            name="Springfield Roleplay",
            icon_url="https://cdn.discordapp.com/attachments/1500468168282345472/1500780381048279080/asp_logo_1.png"
        )
        embed.set_footer(
            text="Powered by Springfield",
            icon_url="https://media.discordapp.net/attachments/1500468168282345472/1500780381048279080/asp_logo_1.png"
        )
        embed.set_thumbnail(
            url="https://media.discordapp.net/attachments/1500468168282345472/1500780381048279080/asp_logo_1.png"
        )

        # Update join button dynamically
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.style == discord.ButtonStyle.link:
                child.url = f"https://policeroleplay.community/join/{info['join_code']}"

        # Safely edit the original message
        try:
            await interaction.followup.edit_message(
                message_id=interaction.message.id,
                embed=embed,
                view=self
            )
        except discord.NotFound:
            print("Cannot edit: interaction expired or message deleted")

# =========================
# Slash Command
# =========================
@bot.tree.command(name="erlcinfo", description="Shows ER:LC server information")
async def erlcinfo(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        info = await get_server_info()
        embed = discord.Embed(title="", color=discord.Color.green())

        embed.add_field(
            name="General:",
            value=(
                f"> **Server Name:** `Springfield Roleplay | New | Realistic`\n"
                f"> **Join Code:** `SPFRPx`"
            ),
            inline=False
        )

        embed.add_field(
            name="Players:",
            value=(
                f"> **Current Players:** `{info['current_players']}/{info['max_players']}`\n"
                f"> **Queue:** `{info['queue_count']} players`\n"
                f"> **Staff Online:** `{info['staff_count']} total`"
            ),
            inline=False
        )

        embed.set_author(
            name="Springfield Roleplay",
            icon_url="https://cdn.discordapp.com/attachments/1500468168282345472/1500780381048279080/asp_logo_1.png"
        )
        embed.set_footer(
            text="Powered by Springfield",
            icon_url="https://media.discordapp.net/attachments/1500468168282345472/1500780381048279080/asp_logo_1.png"
        )
        embed.set_thumbnail(
            url="https://media.discordapp.net/attachments/1500468168282345472/1500780381048279080/asp_logo_1.png"
        )

        view = ERLCView(join_code=info["join_code"])
        await interaction.followup.send(embed=embed, view=view)
    except Exception as e:
        await interaction.followup.send(
            f"<:Xmark:1500777980694237274> Failed to fetch ER:LC server info.\n```{e}```",
            ephemeral=True
        )
        
@bot.tree.command(name="membercount", description="Shows the number of members in this server")
async def membercount(interaction: discord.Interaction):
    member_count = interaction.guild.member_count

    embed = discord.Embed(
        title="<:people:1500636270156841031> Server Member Count",
        description=f"This server has **{member_count} Members!**",
        color=discord.Color.from_rgb(255, 255, 255)  # White color
    )

    embed.set_author(
        name="Springfield Roleplay",
        icon_url="https://cdn.discordapp.com/attachments/1500468168282345472/1500780381048279080/asp_logo_1.png"
    )
    embed.set_footer(
        text="Powered by Springfield",
        icon_url="https://media.discordapp.net/attachments/1500468168282345472/1500780381048279080/asp_logo_1.png"
    )
    embed.set_thumbnail(
        url="https://media.discordapp.net/attachments/1500468168282345472/1500780381048279080/asp_logo_1.png"
    )

    await interaction.response.send_message(embed=embed)
#------------------------------------------------------
# =========================
# ON READY (FIXED + SAFE)
# =========================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    # -------------------------
    # Register persistent views
    # -------------------------
    bot.add_view(TicketView())
    bot.add_view(TicketButtons(bot))
    bot.add_view(TicketUserButtons(ticket_owner_id=0))
    bot.add_view(ERLCView())  # Persistent view example

    # -------------------------
    # Register /ticket commands
    # -------------------------
    class TicketManagement(app_commands.Group):
        def __init__(self, bot):
            super().__init__(name="ticket", description="Ticket commands")
            self.bot = bot

        @app_commands.command(name="adduser", description="Add a member to an active ticket")
        @app_commands.describe(member="Member to add to the ticket")
        async def adduser(self, interaction: discord.Interaction, member: discord.Member):
            # Only staff roles can use
            allowed_roles = [ADMIN_ROLE_ID, HIGH_RANK_ROLE_ID, SENIOR_HIGH_RANK_ROLE_ID]
            if not any(role.id in allowed_roles for role in interaction.user.roles):
                await interaction.response.send_message(
                    "<:Xmark:1500777980694237274> You don't have permission to add users.",
                    ephemeral=True
                )
                return

            # Get all active tickets (channels with topic set)
            guild = interaction.guild
            tickets = [ch for ch in guild.text_channels if ch.topic and "ticket" in ch.name.lower()]
            if not tickets:
                await interaction.response.send_message(
                    "<:Xmark:1500777980694237274> No active tickets found.",
                    ephemeral=True
                )
                return

            # Create a dropdown of tickets
            options = [
                discord.SelectOption(label=ch.name, value=str(ch.id))
                for ch in tickets
            ]

            class TicketSelect(discord.ui.Select):
                def __init__(self):
                    super().__init__(
                        placeholder="Select a ticket to add the user to...",
                        options=options,
                        min_values=1,
                        max_values=1
                    )

                async def callback(self, select_interaction: discord.Interaction):
                    channel_id = int(self.values[0])
                    channel = guild.get_channel(channel_id)
                    if not channel:
                        await select_interaction.response.send_message(
                            "<:Xmark:1500777980694237274> Could not find the ticket.",
                            ephemeral=True
                        )
                        return
                    await channel.set_permissions(member, view_channel=True, send_messages=True)
                    await select_interaction.response.send_message(
                        f"<:Cmark:1500778023799099403> {member.mention} has been added to **{channel.name}**.",
                        ephemeral=True
                    )

            view = discord.ui.View()
            view.add_item(TicketSelect())
            await interaction.response.send_message(
                f"Select a ticket to add {member.mention} to:",
                view=view,
                ephemeral=True
            )

        @app_commands.command(name="removeuser", description="Remove a member from an active ticket")
        @app_commands.describe(member="Member to remove from the ticket")
        async def removeuser(self, interaction: discord.Interaction, member: discord.Member):
            # Only staff roles can use
            allowed_roles = [ADMIN_ROLE_ID, HIGH_RANK_ROLE_ID, SENIOR_HIGH_RANK_ROLE_ID]
            if not any(role.id in allowed_roles for role in interaction.user.roles):
                await interaction.response.send_message(
                    "<:Xmark:1500777980694237274> You don't have permission to remove users.",
                    ephemeral=True
                )
                return

            # Get all active tickets (channels with topic set)
            guild = interaction.guild
            tickets = [ch for ch in guild.text_channels if ch.topic and "ticket" in ch.name.lower()]
            if not tickets:
                await interaction.response.send_message(
                    "<:Xmark:1500777980694237274> No active tickets found.",
                    ephemeral=True
                )
                return

            # Create dropdown of tickets
            options = [
                discord.SelectOption(label=ch.name, value=str(ch.id))
                for ch in tickets
            ]

            class TicketSelectRemove(discord.ui.Select):
                def __init__(self):
                    super().__init__(
                        placeholder="Select a ticket to remove the user from...",
                        options=options,
                        min_values=1,
                        max_values=1
                    )

                async def callback(self, select_interaction: discord.Interaction):
                    channel_id = int(self.values[0])
                    channel = guild.get_channel(channel_id)
                    if not channel:
                        await select_interaction.response.send_message(
                            "<:Xmark:1500777980694237274> Could not find the ticket.",
                            ephemeral=True
                        )
                        return
                    await channel.set_permissions(member, overwrite=None)  # Remove their perms
                    await select_interaction.response.send_message(
                        f"<:Cmark:1500778023799099403> {member.mention} has been removed from **{channel.name}**.",
                        ephemeral=True
                    )

            view = discord.ui.View()
            view.add_item(TicketSelectRemove())
            await interaction.response.send_message(
                f"Select a ticket to remove {member.mention} from:",
                view=view,
                ephemeral=True
            )

    # Instantiate and add group to bot tree (guild-only)
    ticket_management = TicketManagement(bot)
    bot.tree.add_command(ticket_management, guild=discord.Object(id=GUILD_ID))

    # -------------------------
    # Sync slash commands to guild
    # -------------------------
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print("Ticket commands synced!")

    # -------------------------
    # Restore persistent views and session data
    # -------------------------
    bot.add_view(TicketView())
    bot.add_view(TicketButtons(bot))
    bot.add_view(TicketUserButtons(ticket_owner_id=0))
    bot.add_view(ERLCView())

    data = load_votes()
    for message_id, vote_data in data.items():
        try:
            bot.add_view(SessionVoteView(author=None, message_id=message_id))
        except Exception as e:
            print(f"Failed to restore vote message {message_id}: {e}")

    data = load_session()
    for key in ["full", "low", "start"]:
        sess = data.get(key)
        if sess:
            try:
                channel = bot.get_channel(sess["channel_id"])
                if channel:
                    msg = await channel.fetch_message(sess["message_id"])
                    session_messages[key] = msg
                    print(f"Session {key} restored!")
            except discord.NotFound:
                session_messages[key] = None
            except Exception as e:
                print(f"Error restoring session {key}: {e}")

    # -------------------------
    # Start background tasks
    # -------------------------
    if not update_players_embed.is_running():
        update_players_embed.start()

# =========================
# RUN BOT
# =========================
bot.run(os.getenv("DISCORD_TOKEN"))
