import discord
import sqlite3
import random
import datetime
import time
import asyncio
from discord.ext import commands, tasks
from discord import app_commands, ui, Interaction
from discord.app_commands import MissingPermissions
from datetime import timedelta
from zoneinfo import ZoneInfo

# ========== VARIABLES ==========

# ---------- DISCORD STUFF ----------
TOKEN = "DISCORD_TOKEN"
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.presences = True
intents.bans=True

start_time = time.time()
global check_voice
# BROWSER variable removed

# ---------- ID LIST ----------

# --- Server id ---
server_id = 1234567890

# --- Channel id ---
cmd_channel_id = 1234567890
welcome_channel_id = 1234567890
boost_channel_id = 1234567890
online_channel_id = 1234567890
total_channel_id = 1234567890
vocal_channel_id = 1234567890

# --- Role id ---
muted_role_id = 1234567890
top_lvl_role_id = 1234567890
join_role_id = 1234567890

LEVEL_ROLES = {
    5: 1234567890,
    10: 1234567890,
    15: 1234567890,
    20: 1234567890,
    30: 1234567890,
    40: 1234567890,
    50: 1234567890,
    75: 1234567890,
    100: 1234567890,

}

# ========== DATA BASE ==========

# ---------- XP SYSTEM ----------
connxp = sqlite3.connect("database\\xp_system.db")
cursorxp = connxp.cursor()
cursorxp.execute("""CREATE TABLE IF NOT EXISTS xp (
    user_id INTEGER PRIMARY KEY,
    xp INTEGER DEFAULT 0,
    total_xp INTEGER DEFAULT 1,
    level INTEGER DEFAULT 1
)""")
connxp.commit()
cursorxp.execute("PRAGMA table_info(xp)")
columns = cursorxp.fetchall()

# ---------- CASINO ----------
conncas = sqlite3.connect("database\\casino.db")
cursorcas = conncas.cursor()
cursorcas.execute("""CREATE TABLE IF NOT EXISTS economy (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0,
    last_daily TEXT
)""")
conncas.commit()

# ---------- MOD ----------
connmod = sqlite3.connect("database\\mod.db")
cursormod = connmod.cursor()
cursormod.execute("""CREATE TABLE IF NOT EXISTS mutes (
    user_id INTEGER PRIMARY KEY,
    end_time INTEGER
)""")

cursormod.execute("""CREATE TABLE IF NOT EXISTS warnings (
    user_id INTEGER,
    reason TEXT,
    timestamp INTEGER
)""")

cursormod.execute("""CREATE TABLE IF NOT EXISTS punishments (
    user_id INTEGER,
    action_type TEXT,
    reason TEXT,
    timestamp INTEGER
)""")
connmod.commit()

# ---------- STATS ----------
connstat = sqlite3.connect("database\\stats.db")
cursorstat = connstat.cursor()
cursorstat.execute("""CREATE TABLE IF NOT EXISTS stats (
    user_id INTEGER PRIMARY KEY,
    messages INTEGER DEFAULT 0,
    voice_seconds INTEGER DEFAULT 0,
    voice_start INTEGER DEFAULT NULL
)""")
connstat.commit()

# ========== CLASS & FUNCTION ==========

# ---------- XP SYSTEM ----------
class XPSystem:
    @staticmethod
    async def add_xp(user_id, amount, guild):
        if guild is None:
            return

        cursorxp.execute("SELECT xp, total_xp, level FROM xp WHERE user_id = ?", (user_id,))
        result = cursorxp.fetchone()

        if result is None:
            cursorxp.execute(
                "INSERT INTO xp (user_id, xp, total_xp, level) VALUES (?, ?, ?, ?)",
                (user_id, amount, amount, 1)
            )
        else:
            current_xp, total_xp, level = result
            new_xp = current_xp + amount
            total_xp += amount
            last_level = level

            while new_xp >= get_xp_needed(level):
                new_xp -= get_xp_needed(level)
                level += 1

            if level > last_level:
                channel = client.get_channel(cmd_channel_id)
                if channel:
                    user = await client.fetch_user(user_id)
                    await channel.send(f"🎉 {user.mention} reached the **level {level}** !")


                member = guild.get_member(user_id)
                if member:
                    new_role = None
                    for lvl, role_id in sorted(LEVEL_ROLES.items(), reverse=True):
                        if level >= lvl:
                            new_role = guild.get_role(role_id)
                            break

                    roles_to_remove = [
                        guild.get_role(rid)
                        for rid in LEVEL_ROLES.values()
                        if guild.get_role(rid) in member.roles
                    ]
                    for role in roles_to_remove:
                        await member.remove_roles(role)

                    if new_role and new_role not in member.roles:
                        await member.add_roles(new_role)

            cursorxp.execute(
                "UPDATE xp SET xp = ?, total_xp = ?, level = ? WHERE user_id = ?",
                (new_xp, total_xp, level, user_id)
            )

        connxp.commit()


# --- Functions ---
def get_xp_needed(level):
    return int(50 * (level ** 1.2))

# ---------- CASINO SYSTEM ----------
class Casino:
    def get_balance(user_id):
        cursorcas.execute("SELECT balance FROM economy WHERE user_id = ?", (user_id,))
        result = cursorcas.fetchone()
        return result[0] if result else 0

    def update_balance(user_id, amount):
        cursorcas.execute("SELECT balance FROM economy WHERE user_id = ?", (user_id,))
        result = cursorcas.fetchone()
        if result:
            new_balance = result[0] + amount
            cursorcas.execute("UPDATE economy SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        else:
            cursorcas.execute("INSERT INTO economy (user_id, balance) VALUES (?, ?)", (user_id, amount))
        conncas.commit()

class BetSelect(ui.View):
    def __init__(self, user, callback):
        super().__init__(timeout=60)
        self.user = user
        self.callback = callback
        self.message = None

        options = []
        balance = Casino.get_balance(user.id)
        steps = [10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000]
        valid_steps = [str(s) for s in steps if s <= balance]

        if not valid_steps:
            options.append(discord.SelectOption(label="Insufficient balance", value="0", default=True))
            bet_dropdown = BetDropdown(options)
            bet_dropdown.disabled = True
        else:
            for s in valid_steps:
                options.append(discord.SelectOption(label=f"{s} 💵", value=s))
            bet_dropdown = BetDropdown(options)

        self.add_item(bet_dropdown)

class BetDropdown(ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Choose your bet", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        mise = int(self.values[0])
        view: BetSelect = self.view
        await view.callback(interaction, mise)
        if view.message:
            await view.message.edit(content="Selected bet, game processing...", view=None)
        self.view.stop()

# --- Main Menu ---
class CasinoMenu(ui.View):
    def __init__(self, user):
        super().__init__(timeout=120)
        self.user = user
        self.message = None
        options = [
            discord.SelectOption(label="Slot Machine", description="Play slot machines", value="slot"),
            discord.SelectOption(label="Roulette", description="Play roulette", value="roulette"),
            discord.SelectOption(label="Blackjack", description="Play blackjack", value="blackjack"),
        ]
        self.add_item(GameSelect(options))

    async def interaction_check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.user.id

class GameSelect(ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Choose your game", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        game = self.values[0]
        bet_view = BetSelect(interaction.user, lambda i, mise: start_game(i, game, mise))

        sent_message = await interaction.response.send_message("Choose your bet :", view=bet_view, ephemeral=True)

        bet_view.message = await interaction.original_response()

# --- Slot Machine ---
class SlotView(ui.View):
    def __init__(self, bet: int, user_id):
        super().__init__(timeout=60)
        self.bet = bet
        if hasattr(user_id, "id"):
            self.user_id = user_id.id
        else:
            self.user_id = user_id

    @ui.button(label="Start Slot Machine", style=discord.ButtonStyle.green)
    async def launch_slot(self, interaction: Interaction, button: ui.Button):
        emojis = ["🍒", "🍋", "🍉", "🍇", "⭐"]
        result = [random.choice(emojis) for _ in range(3)]

        win = result.count(result[0]) == 3
        gain = self.bet * 5 if win else 0

        if gain > 0:
            Casino.update_balance(self.user_id, gain)
        else:
            Casino.update_balance(self.user_id, -self.bet)

        balance_after = Casino.get_balance(self.user_id)

        if not interaction.response.is_done():
            await interaction.response.defer()

        await interaction.followup.send(
            content=f"{interaction.user.mention}\n🎰 Result: {' | '.join(result)}\n"
                    f"Bet : {self.bet} 💵\n"
                    f"{'🎉 You won' if win else '💀 You lost'} {gain if win else self.bet} 💵\n"
                    f"Current balance : {balance_after} 💵",
            ephemeral=False
        )


        self.stop()

# --- Roulette ---
class RouletteColorView(ui.View):
    def __init__(self, user, bet):
        super().__init__(timeout=60)
        self.user = user
        self.bet = bet

    @ui.select(placeholder="Choose a color", options=[
        discord.SelectOption(label="RED", value="red"),
        discord.SelectOption(label="BLACK", value="black"),
        discord.SelectOption(label="GREEN", value="green")
    ])
    async def select_color(self, interaction: Interaction, select: ui.Select):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("It's not your game.", ephemeral=True)
        choix = select.values[0]
        result = random.choices(["red"]*18 + ["black"]*18 + ["green"], k=1)[0]
        gagne = (choix == result)
        gain = self.bet if gagne else -self.bet
        Casino.update_balance(self.user.id, gain)
        balance_after = Casino.get_balance(self.user.id)
        if not interaction.response.is_done():
            await interaction.response.defer()

        await interaction.followup.send(
            content=f"{interaction.user.mention}\n🎯 The roulette wheel has spun : **{result}**.\n"
                    f"You have {'🎉 You won' if gagne else '💀 You lost'} {abs(gain)} 💵.\n"
                    f"Bet : {self.bet} 💵\n"
                    f"Current balance : {balance_after} 💵",
            ephemeral=False
        )


# --- Blackjack ---
class BlackjackView(ui.View):
    def __init__(self, user, bet):
        super().__init__(timeout=180)
        self.user = user
        self.bet = bet

        self.deck = self.create_deck()
        self.player_cards = []
        self.dealer_cards = []

        self.player_score = 0
        self.dealer_score = 0

        self.game_over = False

        self.deal_initial()

    def create_deck(self):
        ranks = list(range(2,11)) + ["J","Q","K","A"]
        deck = ranks * 4
        random.shuffle(deck)
        return deck

    def card_value(self, card):
        if card in ["J","Q","K"]:
            return 10
        elif card == "A":
            return 11
        else:
            return card

    def adjust_for_aces(self, cards, score):
        aces = cards.count("A")
        while score > 21 and aces > 0:
            score -= 10
            aces -= 1
        return score

    def deal_initial(self):
        self.player_cards = [self.deck.pop(), self.deck.pop()]
        self.dealer_cards = [self.deck.pop(), self.deck.pop()]

        self.player_score = self.calculate_score(self.player_cards)
        self.dealer_score = self.calculate_score(self.dealer_cards)

    def calculate_score(self, cards):
        score = sum(self.card_value(c) for c in cards)
        score = self.adjust_for_aces(cards, score)
        return score

    def hand_description(self, reveal_dealer=False):
        dealer_hand = ", ".join(str(c) for c in self.dealer_cards) if reveal_dealer else f"{self.dealer_cards[0]}, ?"
        player_hand = ", ".join(str(c) for c in self.player_cards)
        desc = (f"Dealer: {dealer_hand} (Score: {'?' if not reveal_dealer else self.dealer_score})\n"
                f"You: {player_hand} (Score: {self.player_score})\n"
                f"Bet: {self.bet} 💵")
        return desc

    async def send_initial(self, interaction: Interaction):
        await interaction.response.send_message(f"Start of Blackjack :\n{self.hand_description()}", view=self)

    @ui.button(label="Draw a card", style=discord.ButtonStyle.green)
    async def hit(self, interaction: Interaction, button: ui.Button):
        if interaction.user.id != self.user.id or self.game_over:
            return await interaction.response.send_message("It's not your game, or the game is over.", ephemeral=True)
        card = self.deck.pop()
        self.player_cards.append(card)
        self.player_score = self.calculate_score(self.player_cards)

        if self.player_score > 21:
            self.game_over = True
            Casino.update_balance(self.user.id, -self.bet)
            balance_after = Casino.get_balance(self.user.id)
            await interaction.response.edit_message(content=f"{interaction.user.mention} \n{self.hand_description(reveal_dealer=True)}\nYou've gone over 21, you lose. {self.bet} 💵.\nRemaining balance : {balance_after} 💵", view=None)
            self.stop()
        else:
            await interaction.response.edit_message(content=self.hand_description(), view=self)

    @ui.button(label="Stay", style=discord.ButtonStyle.grey)
    async def stand(self, interaction: Interaction, button: ui.Button):
        if interaction.user.id != self.user.id or self.game_over:
            return await interaction.response.send_message("It's not your game, or the game is over.", ephemeral=True)

        self.game_over = True
        while self.dealer_score < 17:
            card = self.deck.pop()
            self.dealer_cards.append(card)
            self.dealer_score = self.calculate_score(self.dealer_cards)

        player = self.player_score
        dealer = self.dealer_score

        if dealer > 21 or player > dealer:
            gain = self.bet
            msg = f"You win ! {player} against {dealer}."
        elif player == dealer:
            gain = 0
            msg = f"Equality. {player} against {dealer}."
        else:
            gain = -self.bet
            msg = f"You lost. {player} against {dealer}."

        Casino.update_balance(self.user.id, gain)
        balance_after = Casino.get_balance(self.user.id)

        await interaction.response.edit_message(content=f"{interaction.user.mention} \n{self.hand_description(reveal_dealer=True)}\n{msg}\nRemaining balance : {balance_after} 💵", view=None)
        self.stop()

# --- Functions ---
async def start_game(interaction: Interaction, game: str, bet: int):
    balance = Casino.get_balance(interaction.user.id)
    if bet > balance or bet <= 0:
        return await interaction.followup.send("Invalid bet or insufficient balance.", ephemeral=True)

    if game == "slot":
        view = SlotView(bet, interaction.user)
        await interaction.response.send_message(f"Selected slot machine with a bet of {bet} 💵.", view=view, ephemeral=True)

    elif game == "roulette":
        view = RouletteColorView(interaction.user, bet)
        await interaction.response.send_message(f"Selected roulette with a bet of {bet} 💵.\nChoose your color.", view=view, ephemeral=True)

    elif game == "blackjack":
        view = BlackjackView(interaction.user, bet)
        await view.send_initial(interaction)

async def start_slot_game(interaction: Interaction, bet: int):
    user_id = interaction.user.id

    if Casino.get_balance(user_id) < bet:
        return await interaction.response.send_message("Insufficient funds.", ephemeral=True)

    view = SlotView(bet, user_id)
    await interaction.response.send_message(f"You bet {bet} 💵. Click on 'Start the slot'.", view=view, ephemeral=True)

# ---------- STATS SYSTEM ----------

class StatSystem:
    @staticmethod
    def add_message(user_id):
        cursorstat.execute("SELECT messages FROM stats WHERE user_id = ?", (user_id,))
        result = cursorstat.fetchone()
        if result is None:
            cursorstat.execute("INSERT INTO stats (user_id, messages) VALUES (?, 1)", (user_id,))
        else:
            cursorstat.execute("UPDATE stats SET messages = messages + 1 WHERE user_id = ?", (user_id,))
        connstat.commit()

    @staticmethod
    def start_voice(user_id):
        now = int(time.time())
        cursorstat.execute("SELECT voice_start FROM stats WHERE user_id = ?", (user_id,))
        result = cursorstat.fetchone()
        if result is None:
            cursorstat.execute("INSERT INTO stats (user_id, voice_start) VALUES (?, ?)", (user_id, now))
        else:
            cursorstat.execute("UPDATE stats SET voice_start = ? WHERE user_id = ?", (now, user_id))
        connstat.commit()

    @staticmethod
    def stop_voice(user_id):
        cursorstat.execute("SELECT voice_start FROM stats WHERE user_id = ?", (user_id,))
        result = cursorstat.fetchone()
        if result and result[0]:
            delta = int(time.time()) - result[0]
            cursorstat.execute("UPDATE stats SET voice_seconds = voice_seconds + ?, voice_start = NULL WHERE user_id = ?", (delta, user_id))
            connstat.commit()

class LeaderboardSelector(ui.View):
    def __init__(self, interaction: Interaction):
        super().__init__(timeout=60)
        self.interaction = interaction

        self.add_item(LeaderboardDropdown(interaction))

class LeaderboardDropdown(ui.Select):
    def __init__(self, interaction: Interaction):
        self.interaction = interaction
        options = [
            discord.SelectOption(label="XP", value="xp"),
            discord.SelectOption(label="Money", value="balance"),
            discord.SelectOption(label="Overall stats", value="stats"),
            discord.SelectOption(label="📝 Top Messages", value="topmessages"),
            discord.SelectOption(label="🎧 Top Voice Time", value="topvocal"),
        ]
        super().__init__(placeholder="Choose a ranking", options=options)

    async def callback(self, interaction: Interaction):
        value = self.values[0]

        if value == "xp":
            cursorxp.execute("SELECT user_id, total_xp FROM xp ORDER BY total_xp DESC LIMIT 10")
            results = cursorxp.fetchall()
            title = "🏆 XP Ranking"
            lines = [f"#{i+1} {interaction.guild.get_member(uid).name if interaction.guild.get_member(uid) else f'ID {uid}'}: {xp} XP"
                     for i, (uid, xp) in enumerate(results)]

        elif value == "balance":
            cursorcas.execute("SELECT user_id, balance FROM economy ORDER BY balance DESC LIMIT 10")
            results = cursorcas.fetchall()
            title = "💰 Money Ranking"
            lines = [f"#{i+1} {interaction.guild.get_member(uid).name if interaction.guild.get_member(uid) else f'ID {uid}'}: {bal} 💵"
                     for i, (uid, bal) in enumerate(results)]

        elif value == "stats":
            cursorstat.execute("SELECT user_id, messages, voice_seconds FROM stats ORDER BY messages + voice_seconds DESC LIMIT 10")
            results = cursorstat.fetchall()
            title = "📊 Overall Statistics Ranking"
            lines = [f"#{i+1} {interaction.guild.get_member(uid).name if interaction.guild.get_member(uid) else f'ID {uid}'}: 💬 {msg} | 🎧 {format_duration(voc)}"
                     for i, (uid, msg, voc) in enumerate(results)]

        elif value == "topmessages":
            cursorstat.execute("SELECT user_id, messages FROM stats ORDER BY messages DESC LIMIT 10")
            results = cursorstat.fetchall()
            title = "📝 Top Messages"
            lines = [f"#{i+1} {interaction.guild.get_member(uid).name if interaction.guild.get_member(uid) else f'ID {uid}'}: {msg} messages"
                     for i, (uid, msg) in enumerate(results)]

        elif value == "topvocal":
            cursorstat.execute("SELECT user_id, voice_seconds FROM stats ORDER BY voice_seconds DESC LIMIT 10")
            results = cursorstat.fetchall()
            title = "🎧 Top Voice Time"
            lines = [f"#{i+1} {interaction.guild.get_member(uid).name if interaction.guild.get_member(uid) else f'ID {uid}'}: {format_duration(voc)}"
                     for i, (uid, voc) in enumerate(results)]

        embed = discord.Embed(title=title, description="\n".join(lines), color=discord.Color.gold())
        await interaction.response.edit_message(embed=embed, view=self.view)

# --- Functions ---
def format_duration(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}h {m}m {s}s"

# ---------- MOD SYSTEM ----------

# --- Functions ---
def log_punishment(user_id: int, action_type: str, reason: str):
    timestamp = int(datetime.datetime.now(ZoneInfo("Europe/Paris")).timestamp())
    cursormod.execute("INSERT INTO punishments (user_id, action_type, reason, timestamp) VALUES (?, ?, ?, ?)",
              (user_id, action_type, reason, timestamp))
    connmod.commit()

def add_warning(user_id, reason):
    timestamp = int(datetime.datetime.now(ZoneInfo("Europe/Paris")).timestamp())
    cursormod.execute("INSERT INTO warnings (user_id, reason, timestamp) VALUES (?, ?, ?)", (user_id, reason, timestamp))
    connmod.commit()

# ---------- ANIMATION ----------

# --- Giveaway ---
class GiveawayButton(discord.ui.View):
    def __init__(self, timeout, reward, winners, end_timestamp, message):
        super().__init__(timeout=timeout)
        self.participants = set()
        self.reward = reward
        self.winners = winners
        self.end_timestamp = end_timestamp
        self.message = message

    @discord.ui.button(style=discord.ButtonStyle.green, emoji="🎁")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if user.id in self.participants:
            await interaction.response.send_message("You are already registered for the giveaway !", ephemeral=True)
        else:
            self.participants.add(user.id)
            await interaction.response.send_message("You are successfully registered ! 🎉", ephemeral=True)
            await self.update_embed()

    async def update_embed(self):
        embed = discord.Embed(
            title=f"🎉 Giveaway: {self.reward}",
            description=(
                f"Click on the :gift: button to participate.\n\n"
                f"**Number of winners :** {self.winners}\n"
                f"**Participants :** {len(self.participants)}\n"
                f"**End of giveaway :** <t:{self.end_timestamp}:R>"
                f"{'🔊 Only voice members will be eligible.' if check_voice else ''}"
            ),
            color=discord.Color.purple()
        )
        embed.set_footer(text="Good luck, everyone!")
        await self.message.edit(embed=embed, view=self)

# ========== BOT SYSTEM ==========

class Client(commands.Bot):
    async def on_ready(self):
        try:
            await self.tree.sync(guild=guild)
        except Exception as e:
            print("error syncing commands")

        activity = discord.CustomActivity(name="👋 Привет 👋")
        await self.change_presence(status=discord.Status.idle, activity=activity)

        self.update_voice_channel.start()
        self.update_vc_xp.start()
        self.update_top_xp_role.start()


    async def on_message(self, message):
        if message.author == self.user:
            return
        await XPSystem.add_xp(message.author.id, 10, message.guild)  # 10 XP message
        await self.process_commands(message)
        StatSystem.add_message(message.author.id)
        await self.process_commands(message)

    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        if before.channel is None and after.channel is not None:
            StatSystem.start_voice(member.id)
        elif before.channel is not None and after.channel is None:
            StatSystem.stop_voice(member.id)

    async def on_member_join(self, member):
        cursorxp.execute("INSERT OR IGNORE INTO xp (user_id, xp, level) VALUES (?, ?, ?)", (member.id, 0, 1))
        connxp.commit()


        channel = member.guild.get_channel(welcome_channel_id)
        if channel:
            await channel.send(f'Welcome {member.mention} to {member.guild.name} ! 🎉')

        
        role = member.guild.get_role(join_role_id)
        if role:
            await member.add_roles(role)

    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.premium_since != after.premium_since:
            if after.premium_since is not None:
                if boost_channel_id:
                    embed = discord.Embed(
                        title="🚀 New Boost!",
                        description=f"Thanks {after.mention} for the boost ! 💜\nThe server now has **{after.guild.premium_subscription_count}** boosts !",
                        color=discord.Color.purple()
                    )
                    embed.set_thumbnail(url=after.display_avatar.url)
                    await boost_channel_id.send(embed=embed)

    @tasks.loop(minutes=1)
    async def update_vc_xp(self):
        for guild in self.guilds:
            for vc in guild.voice_channels:
                for member in vc.members:
                    if not member.bot:
                        await XPSystem.add_xp(member.id, 10, guild)  # 10 XP minute voc

    @tasks.loop(minutes=1)
    async def unmute_task(self):
        now = int(datetime.datetime.now(ZoneInfo("Europe/Paris")).timestamp()) 
        cursormod.execute("SELECT user_id FROM mutes WHERE end_time <= ?", (now,))
        to_unmute = cursormod.fetchall()
        guild_obj = self.get_guild(guild.id)
        muted_role = guild_obj.get_role(muted_role_id)
        for (user_id,) in to_unmute:
            member = guild_obj.get_member(user_id)
            if member and muted_role and muted_role in member.roles:
                try:
                    await member.remove_roles(muted_role, reason="Mute automatically expired")
                    try:
                        await member.send(f"🔊 Your mute on {guild_obj.name} is finished.")
                    except:
                        pass
                except:
                    pass
            cursormod.execute("DELETE FROM mutes WHERE user_id = ?", (user_id,))
        connmod.commit()

    @tasks.loop(minutes=5)
    async def update_voice_channel(self):
        guild = client.get_guild(server_id)

        online_count = len([member for member in guild.members if member.status in (discord.Status.online, discord.Status.dnd, discord.Status.idle)])
        total_count = len([member for member in guild.members])
        total_in_vocal = sum(len(voice_channel.members) for voice_channel in guild.voice_channels)

        voice_online = guild.get_channel(online_channel_id)
        if voice_online and isinstance(voice_online, discord.VoiceChannel):
            await voice_online.edit(name=f"💎・Online : {online_count}")

        voice_total = guild.get_channel(total_channel_id)
        if voice_total and isinstance(voice_total, discord.VoiceChannel):
            await voice_total.edit(name=f"🌍・Members : {total_count}")

        voice_vocal = guild.get_channel(vocal_channel_id)
        if voice_vocal and isinstance(voice_vocal, discord.VoiceChannel):
            await voice_vocal.edit(name=f"🎧・In Voice : {total_in_vocal}")



    @tasks.loop(minutes=1)
    async def update_top_xp_role(self):
        cursorxp.execute("SELECT user_id, total_xp FROM xp ORDER BY total_xp DESC LIMIT 1")
        guild = self.get_guild(server_id)
        result = cursorxp.fetchone()
        if result is None:
            return 

        top_user_id = result[0]
        if guild is None:
            return

        top_role = guild.get_role(top_lvl_role_id)
        if top_role is None:
            return

        current_holders = [member for member in top_role.members]

        top_member = guild.get_member(top_user_id)
        if top_member is None:
            return

        if top_member in current_holders and len(current_holders) == 1:
            return 

        for member in current_holders:
            await member.remove_roles(top_role)

        await top_member.add_roles(top_role)

client = Client(command_prefix="!", intents=intents)
guild = client.get_guild(server_id)

# ========== COMMANDES / ==========

# ---------- XP SYSTEM ----------

# --- Set XP --- ADMIN
@client.tree.command(name="setxp", description="Assigns specific XP to a user.", guild=guild)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(user="Recipient user", xp_amount="Amount to set")
async def set_xp(interaction: discord.Interaction, user: discord.Member, xp_amount: int):
    cursorxp.execute("SELECT xp, total_xp, level FROM xp WHERE user_id = ?", (user.id,))
    result = cursorxp.fetchone()

    total_xp = xp_amount
    level = 1
    xp_to_allocate = total_xp

    while xp_to_allocate >= get_xp_needed(level):
        xp_to_allocate -= get_xp_needed(level)
        level += 1

    current_xp = xp_to_allocate

    if result is None:
        cursorxp.execute(
            "INSERT INTO xp (user_id, xp, total_xp, level) VALUES (?, ?, ?, ?)",
            (user.id, current_xp, total_xp, level)
        )
    else:
        cursorxp.execute(
            "UPDATE xp SET xp = ?, total_xp = ?, level = ? WHERE user_id = ?",
            (current_xp, total_xp, level, user.id)
        )

    connxp.commit()

    guild = interaction.guild

    new_role = None
    for lvl, role_id in sorted(LEVEL_ROLES.items(), reverse=True):
        if level >= lvl:
            new_role = guild.get_role(role_id)
            break

    roles_to_remove = [guild.get_role(rid) for rid in LEVEL_ROLES.values() if guild.get_role(rid) in user.roles]
    for role in roles_to_remove:
        await user.remove_roles(role)

    if new_role and new_role not in user.roles:
        await user.add_roles(new_role)

    channel = client.get_channel(cmd_channel_id)
    if channel:
        await channel.send(f"🎉 {user.mention} now has {total_xp} XP ! Their new level is {level} with {current_xp} XP in that level.")

    await interaction.response.send_message(f"XP updated : {user.mention} has {total_xp} total XP, level {level}.", ephemeral=True)


# ---------- CASINO SYSTEM ----------

# --- PAY ---
@client.tree.command(name="pay", description="Transfer money to another user", guild=guild)
@app_commands.describe(user="Recipient user", amount="Amount to be transferred")
async def pay(interaction: Interaction, user: discord.Member, amount: int):
    if user.id == interaction.user.id:
        return await interaction.response.send_message("You can't afford it yourself.", ephemeral=True)
    if amount <= 0:
        return await interaction.response.send_message("The amount must be greater than 0.", ephemeral=True)

    payer_id = interaction.user.id
    if Casino.get_balance(payer_id) < amount:
        return await interaction.response.send_message("You don't have enough money.", ephemeral=True)

    Casino.update_balance(payer_id, -amount)
    Casino.update_balance(user.id, amount)
    await interaction.response.send_message(f"{interaction.user.mention} transferred {amount} 💵 to {user.mention}.")

# --- Daily ---
@client.tree.command(name="daily", description="Claim your daily reward", guild=guild)
async def daily(interaction: discord.Interaction):
    user_id = interaction.user.id
    now = datetime.datetime.now(ZoneInfo("Europe/Paris"))
    today_str = now.date().isoformat()

    cursorcas.execute("SELECT last_daily FROM economy WHERE user_id = ?", (user_id,))
    row = cursorcas.fetchone()

    if row and row[0]:
        last_date = datetime.datetime.strptime(row[0], "%Y-%m-%d")
        if last_date.date() == now.date():
            next_claim = datetime.datetime.combine(last_date + timedelta(days=1), datetime.time.min).replace(tzinfo=ZoneInfo("Europe/Paris"))
            delta = next_claim - now
            hours, seconds = divmod(int(delta.total_seconds()), 3600)
            minutes = seconds // 60
            return await interaction.response.send_message(
                f"🕒 You can claim your reward in {hours}h {minutes}min."
            )

    Casino.update_balance(user_id, 100)
    cursorcas.execute("UPDATE economy SET last_daily = ? WHERE user_id = ?", (today_str, user_id))
    conncas.commit()
    await interaction.response.send_message("🎁 Tu as reçu 100 💵 ! Reviens demain.")

# --- Casino ---
@client.tree.command(name="casino", description="Open the casino menu", guild=guild)
async def casino(interaction: Interaction):
    view = CasinoMenu(interaction.user)
    await interaction.response.send_message("Choose your game:", view=view, ephemeral=True)
    view.message = await interaction.original_response()

# --- Set Balance --- ADMIN
@client.tree.command(name="setbalance", description="Define a user's balance", guild=guild)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(user="Targeted user", amount="Balance amount to be defined")
async def setbalance(interaction: discord.Interaction, user: discord.Member, amount: int):
    cursorcas.execute("SELECT balance FROM economy WHERE user_id = ?", (user.id,))
    if cursorcas.fetchone():
        cursorcas.execute("UPDATE economy SET balance = ? WHERE user_id = ?", (amount, user.id))
    else:
        cursorcas.execute("INSERT INTO economy (user_id, balance) VALUES (?, ?)", (user.id, amount))
    conncas.commit()
    await interaction.response.send_message(f"The balance of {user.mention} has been set to {amount} 💵.", ephemeral=True)

# ---------- MOD SYSTEM ----------

# --- WARNINGS ---
@client.tree.command(name="warnings", description="View punishment history", guild=guild)
@app_commands.describe(user="Targeted user")
async def warnings_cmd(interaction: discord.Interaction, user: discord.Member):
    cursormod.execute("SELECT action_type, reason, timestamp FROM punishments WHERE user_id = ? ORDER BY timestamp DESC", (user.id,))
    entries = cursormod.fetchall()

    if not entries:
        await interaction.response.send_message("No penalties recorded for this user.")
        return

    lines = []
    for i, (atype, reason, ts) in enumerate(entries):
        date = datetime.datetime.fromtimestamp(ts, ZoneInfo("Europe/Paris")).strftime("%Y-%m-%d %H:%M")
        lines.append(f"**{i+1}.** [{atype.upper()}] - {reason} *(le {date})*")

    embed = discord.Embed(title=f"Moderation history of {user.name}", description="\n".join(lines), color=discord.Color.red())
    await interaction.response.send_message(embed=embed)

# --- Ban --- ADMIN
@client.tree.command(name="ban", description="Ban a member", guild=guild)
@app_commands.checks.has_permissions(ban_members=True)
@app_commands.describe(user="Targeted user", reason="Reason for banishment")
async def ban(interaction: discord.Interaction, user: discord.Member, reason: str):
    try:
        await user.send(f"You have been banned from the server {interaction.guild.name}. Reason: {reason}")
    except:
        pass
    await user.ban(reason=reason)
    log_punishment(user.id, "ban", reason)
    await interaction.response.send_message(f"{user.mention} has been banned. Reason: {reason}")

# --- Unban --- ADMIN
@client.tree.command(name="unban", description="Unban a user", guild=guild)
@app_commands.checks.has_permissions(ban_members=True)
@app_commands.describe(user_id="ID of the user to be unbanned")
async def unban(interaction: discord.Interaction, user_id: str):
    try:
        banned_users = []
        async for ban_entry in interaction.guild.bans():
            banned_users.append(ban_entry)

        user = discord.utils.get(banned_users, user__id=int(user_id))
        if user is None:
            await interaction.response.send_message("User not found in the list of banned users.", ephemeral=True)
            return

        await interaction.guild.unban(user.user)
        try:
            await user.user.send(f"You have been unbanned from the server {interaction.guild.name}.")
        except:
            pass
        await interaction.response.send_message(f"The user {user.user.mention} has been unbanned.")
    except discord.Forbidden:
        await interaction.response.send_message("I do not have permission to unban this user.", ephemeral=True)
    except ValueError:
        await interaction.response.send_message("Invalid ID. Please enter a valid numeric ID.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Unexpected error: {e}", ephemeral=True)

# --- Kick --- ADMIN
@client.tree.command(name="kick", description="Kick a member", guild=guild)
@app_commands.checks.has_permissions(kick_members=True)
@app_commands.describe(user="User to kick", reason="Reason")
async def kick(interaction: discord.Interaction, user: discord.Member, reason: str):
    try:
        await user.send(f"You have been kicked from the server {interaction.guild.name}. Reason : {reason}")
    except:
        pass
    await user.kick(reason=reason)
    log_punishment(user.id, "kick", reason)
    await interaction.response.send_message(f"{user.mention} has been kicked. Reason: {reason}")

# --- Mute --- ADMIN
@client.tree.command(name="mute", description="Mute a member", guild=guild)
@app_commands.checks.has_permissions(moderate_members=True)
@app_commands.describe(user="User to mute", duration="Duration in seconds (0 = permanent)", reason="Reason")
async def mute(interaction: discord.Interaction, user: discord.Member, reason: str, duration: int = 0):
    muted_role = interaction.guild.get_role(muted_role_id)
    if not muted_role:
        await interaction.response.send_message("❌ The Muted role cannot be found.", ephemeral=True)
        return

    await user.add_roles(muted_role, reason=reason)
    log_punishment(user.id, "mute", reason)

    await interaction.response.send_message(
        f"🔇 {user.mention} has been muted{" for " + str(duration) + " secondes" if duration > 0 else ""}. Reason : {reason}"
    )

    try:
        await user.send(f"🔇 You have been muted on {interaction.guild.name} for {duration} seconds. Reason: {reason}")
    except:
        pass

    if duration > 0:
        unmute_time = int((datetime.datetime.now(ZoneInfo("Europe/Paris")) + datetime.timedelta(seconds=duration)).timestamp())
        cursormod.execute("REPLACE INTO mutes (user_id, end_time) VALUES (?, ?)", (user.id, unmute_time))
        connmod.commit()
    else:
        cursormod.execute("REPLACE INTO mutes (user_id, end_time) VALUES (?, ?)", (user.id, 9999999999))
        connmod.commit()

# --- Unmute --- ADMIN
@client.tree.command(name="unmute", description="Unmute a user", guild=guild)
@app_commands.checks.has_permissions(moderate_members=True)
@app_commands.describe(user="User to unmute")
async def unmute(interaction: discord.Interaction, user: discord.Member):
    muted_role = interaction.guild.get_role(muted_role_id)
    if not muted_role:
        await interaction.response.send_message("❌ The Muted role cannot be found.", ephemeral=True)
        return

    if muted_role in user.roles:
        await user.remove_roles(muted_role)
        cursormod.execute("DELETE FROM mutes WHERE user_id = ?", (user.id,))
        connmod.commit()
        await interaction.response.send_message(f"🔊 {user.mention} can speak again.")
        try:
            await user.send(f"🔊 You have been unmuted on {interaction.guild.name}.")
        except:
            pass
    else:
        await interaction.response.send_message(f"ℹ️ {user.mention} was not mute.")

# --- Warn--- ADMIN
@client.tree.command(name="warn", description="Warn a user", guild=guild)
@app_commands.checks.has_permissions(moderate_members=True)
@app_commands.describe(user="User to warn", reason="Reason")
async def warn(interaction: discord.Interaction, user: discord.Member, reason: str):
    add_warning(user.id, reason)
    try:
        await user.send(f"You have received a warning about {interaction.guild.name} for : {reason}")
    except:
        pass
    log_punishment(user.id, "warn", reason)
    await interaction.response.send_message(f"⚠️ {user.mention} was warned for: {reason}")

# --- Clear --- ADMIN
@client.tree.command(name="clear", description="Deletes messages.", guild=guild)
@app_commands.checks.has_permissions(manage_messages=True)
@app_commands.describe(amount="Number of messages to delete")
async def clear(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)

    deleted = await interaction.channel.purge(limit=amount)
    
    await interaction.followup.send(f"🧹 {len(deleted)} deleted messages", ephemeral=True)

# --- Slowmode --- ADMIN
@client.tree.command(name="slowmode", description="Enable slow mode", guild=guild)
@app_commands.checks.has_permissions(manage_messages=True)
@app_commands.describe(duration="Duration in seconds")
async def slowmode(interaction: discord.Interaction, duration: int):
    await interaction.channel.edit(slowmode_delay=duration)
    await interaction.response.send_message(f"⏱️ Slow mode set to {duration} seconds")

# --- Lock --- ADMIN
@client.tree.command(name="lock", description="Lock a channel", guild=guild)
@app_commands.checks.has_permissions(manage_messages=True)
@app_commands.describe(channel="Channel to lock")
async def lock(interaction: discord.Interaction, channel: discord.TextChannel = None):
    target_channel = channel or interaction.channel
    await target_channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message(f"🔒 {target_channel.mention} is locked")

# --- Unlock --- ADMIN
@client.tree.command(name="unlock", description="Unlock a channel", guild=guild)
@app_commands.checks.has_permissions(manage_messages=True)
@app_commands.describe(channel="Channel to unlock")
async def unlock(interaction: discord.Interaction, channel: discord.TextChannel = None):
    target_channel = channel or interaction.channel
    await target_channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await interaction.response.send_message(f"🔓 {target_channel.mention} is unlocked")

# --- Broadcast --- ADMIN
@client.tree.command(name="broadcast", description="Send a message to all members of the server", guild=guild)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(message="Message to send")
async def broadcast(interaction: discord.Interaction, message: str):
    await interaction.response.send_message("📨 Sending messages in progress...", ephemeral=True)
    success = 0
    failed = 0
    for member in interaction.guild.members:
        if not member.bot:
            try:
                await member.send(message)
                success += 1
            except:
                failed += 1
    await interaction.followup.send(f"✅ Message sent to {success} members. ❌ Failed for {failed} members.", ephemeral=True)

# ---------- STATS SYSTEM ----------

# --- UPTIME ---
@client.tree.command(name="uptime", description="How long has the bot been online", guild=guild)
async def uptime(interaction: Interaction):
    now = time.time()
    seconds = int(now - start_time)
    h, m = divmod(seconds, 3600)
    m, s = divmod(m, 60)
    await interaction.response.send_message(f"Uptime: {h}h {m}m {s}s")

# --- PING ---
@client.tree.command(name="ping", description="Check the bot's latency", guild=guild)
async def ping(interaction: Interaction):
    latency_ms = round(client.latency * 1000)
    await interaction.response.send_message(f"Pong 🌟 {latency_ms} ms")

# --- Profil ---
@client.tree.command(name="profil", description="See all your information (XP, stats, money)", guild=guild)
@app_commands.describe(user="User to be inspected")
async def profil(interaction: Interaction, user: discord.Member = None):
    user = user or interaction.user

    cursorxp.execute("SELECT xp, total_xp, level FROM xp WHERE user_id = ?", (user.id,))
    result_xp = cursorxp.fetchone()

    cursorstat.execute("SELECT messages, voice_seconds FROM stats WHERE user_id = ?", (user.id,))
    result_stats = cursorstat.fetchone()

    solde = Casino.get_balance(user.id)

    cursorcas.execute("SELECT user_id FROM economy ORDER BY balance DESC")
    classement = cursorcas.fetchall()
    rang_balance = next((i + 1 for i, (uid,) in enumerate(classement) if uid == user.id), "Not ranked")

    msg_rank = voc_rank = "Not ranked"
    if result_stats:
        messages, voice_seconds = result_stats
        cursorstat.execute("SELECT COUNT(*) + 1 FROM stats WHERE messages > ?", (messages,))
        msg_rank = cursorstat.fetchone()[0]
        cursorstat.execute("SELECT COUNT(*) + 1 FROM stats WHERE voice_seconds > ?", (voice_seconds,))
        voc_rank = cursorstat.fetchone()[0]

    embed = discord.Embed(title=f"📇 Profil de {user.name}", color=discord.Color.blurple())

    if result_xp:
        current_xp, total_xp, level = result_xp
        next_level_xp = get_xp_needed(level)

        cursorxp.execute("SELECT user_id FROM xp ORDER BY total_xp DESC")
        classement_xp = cursorxp.fetchall()
        rang_xp = next((i + 1 for i, (uid,) in enumerate(classement_xp) if uid == user.id), "Not ranked")

        embed.add_field(name="🏆 Level", value=str(level), inline=True)
        embed.add_field(name="✨ XP", value=f"{current_xp}/{next_level_xp}", inline=True)
        embed.add_field(name="📜 Total XP", value=f"{total_xp} (#{rang_xp})", inline=True)
    else:
        embed.add_field(name="XP", value="No data yet", inline=False)


    embed.add_field(name="💬 Messages", value=f"{messages} (#{msg_rank})" if result_stats else "N/A", inline=True)
    embed.add_field(name="🎧 Vocal", value=f"{format_duration(voice_seconds)} (#{voc_rank})" if result_stats else "N/A", inline=True)
    embed.add_field(name="💰 Money", value=f"{solde} 💵 (#{rang_balance})", inline=True)

    await interaction.response.send_message(embed=embed)

# --- Leaderboard ---
@client.tree.command(name="leaderboard", description="See rankings (XP, money, stats)", guild=guild)
async def leaderboard_command(interaction: Interaction):
    view = LeaderboardSelector(interaction)
    await interaction.response.send_message("📊 Select a category:", view=view)

# --- SERVERINFO --- ADMIN
@client.tree.command(name="serverinfo", description="Server information", guild=guild)
@app_commands.checks.has_permissions(administrator=True)
async def serverinfo(interaction: Interaction):
    guild_obj = interaction.guild

    online = len([m for m in guild_obj.members if m.status != discord.Status.offline])
    streaming = len([m for m in guild_obj.members if m.activity and str(m.activity.type) == "ActivityType.streaming"])
    in_voice = sum(len(vc.members) for vc in guild_obj.voice_channels)
    total = guild_obj.member_count
    boosts = guild_obj.premium_subscription_count

    description = (
        f"*Members* : {total:,}\n"
        f"*Online* : {online:,}\n"
        f"*In Vocal* : {in_voice:,}\n"
        f"*Streaming* : {streaming:,}\n"
        f"*Boost* : {boosts}"
    )

    embed = discord.Embed(title=f"{guild_obj.name} Statistics!", description=description, color=discord.Color.gold())
    if guild_obj.icon:
        embed.set_thumbnail(url=guild_obj.icon.url)

    await interaction.response.send_message(embed=embed)

# --- USERINFO --- ADMIN
@client.tree.command(name="userinfo", description="Member information", guild=guild)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(user="User to be inspected")
async def userinfo(interaction: Interaction, user: discord.Member = None):
    user = user or interaction.user
    member = interaction.guild.get_member(user.id)

    embed = discord.Embed(title=f"Information from {member.name}", color=discord.Color.blurple())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="ID", value=member.id, inline=True)
    embed.add_field(name="Created on", value=member.created_at.strftime("%Y-%m-%d %H:%M"), inline=True)
    embed.add_field(name="Joined on", value=member.joined_at.strftime("%Y-%m-%d %H:%M"), inline=True)
    embed.add_field(name="Roles", value=", ".join(r.mention for r in member.roles if r != interaction.guild.default_role), inline=False)
    embed.add_field(name="Status", value=str(member.status).capitalize(), inline=True)
    await interaction.response.send_message(embed=embed)

# ---------- ANIMATION ----------

# --- Giveaway ---
@client.tree.command(name="giveaway", description="Start a giveaway", guild=guild)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(reward="The prize to win", duration_minutes="Duration in minutes", winners="Number of winners", check_voice="The winner must be on voice chat.")
async def giveaway(interaction: discord.Interaction, reward: str, duration_minutes: int, winners: int, check_voice: bool = False):
    end_time = datetime.datetime.now(ZoneInfo("Europe/Paris")) + timedelta(minutes=duration_minutes)
    end_timestamp = int(end_time.timestamp())

    
    embed = discord.Embed(
        title=f"🎉 Giveaway: {reward}",
        description=(
            f"Click on the :gift: button to participate\n\n"
            f"**Number of winners:** {winners}\n"
            f"**Participants:** 0\n"
            f"**End of giveaway:** <t:{end_timestamp}:R>\n"
            f"{'🔊 Only voice members will be eligible.' if check_voice else ''}"
        ),
        color=discord.Color.purple()
    )
    embed.set_footer(text="Good luck, everyone!")

    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()

    view = GiveawayButton(
        timeout=duration_minutes * 60,
        reward=reward,
        winners=winners,
        end_timestamp=end_timestamp,
        message=message
    )
    await message.edit(view=view)

    await asyncio.sleep(duration_minutes * 60)

    guild = interaction.guild
    all_participants = [guild.get_member(uid) for uid in view.participants]
    all_participants = [m for m in all_participants if m is not None]

    if check_voice:
        all_participants = [
            m for m in all_participants if m.voice and m.voice.channel
        ]

    if not all_participants:
        await message.reply("No eligible participants, giveaway canceled.")
        await message.delete()
        return

    if len(all_participants) < winners:
        winners = len(all_participants)

    winner_list = random.sample(all_participants, winners)
    winner_mentions = ", ".join([m.mention for m in winner_list])

    await message.reply(f"🎉 Giveaway **{reward}** ended! Congratulations to : {winner_mentions}")
    await message.delete()

# ---------- PERMISSION ERROR ----------
@client.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    error_msg = f"❌ Error : {error}"

    if isinstance(error, MissingPermissions):
        missing = ", ".join(error.missing_permissions)
        error_msg = f"❌ Required permissions missing : {missing}"

    if interaction.response.is_done():
        await interaction.followup.send(error_msg, ephemeral=True)
    else:
        await interaction.response.send_message(error_msg, ephemeral=True)

client.run(TOKEN)