"""
TRASH COLLECTOR - Discord Cog
==============================
Scavenge vintage e-waste, build mining rigs, and mine El Virtual (₿v).

Game logic is sourced from game_engine.py (synced from Trash Collector 2).
This cog provides the Discord interface on top of that engine.
"""

import random
import time
import datetime
import discord
from discord.ext import commands, tasks
from discord import app_commands
from mining_db import MiningDB
from database import CreditDB

# =============================================================================
# GAME ENGINE IMPORTS (from Trash Collector 2)
# =============================================================================
# All core game logic lives in game_engine.py. Import everything from there
# so we get the latest scoring, parsing, and multiplier improvements.
from game_engine import (
    # Scoring
    TYPE_MULTIPLIERS, TYPE_SCORE_BOOST,
    era_bonus, compute_score,
    # Hardware database
    HARDWARE_DB, HARDWARE_LOOKUP,
    random_find, random_finds,
    # Rarity
    RARITY_ORDER, RARITY_EMOJI,
    # Game constants (non-economy)
    MINING_RATE, ACTIVE_MINING_MULTIPLIER,
    SCAVENGE_COOLDOWN, MINE_COOLDOWN, PARTS_PER_RIG,
    BTC_MIN_PRICE, BTC_MAX_PRICE, BTC_VOLATILITY, BTC_REVERSION,
    MARKET_REFRESH_SECONDS, MARKET_SLOTS, RARITY_PRICE_MULT,
    # Market
    update_btc_price,
    # Environmental helpers (used by local Discord-flavoured env functions)
    rig_total_watts, annual_kwh, annual_co2_kg, annual_co2_tonnes,
    trees_destroyed_equivalent, rainforest_hectares_destroyed,
    soccer_fields_destroyed, panda_habitat_percentage,
    arctic_ice_equivalent_m3, electricity_cost_annual,
    # Rig bonus multipliers (NEW in Trash Collector 2)
    diversity_multiplier, legendary_multiplier,
    # Combo bonus (heterogeneous stack synergy — FPGA as hypervisor)
    combo_multiplier,
    # Business Accountability & Planning Act — permit system
    assess_permit_tier, CPRM_THRESHOLD_BTC, CPRM_OVERHEAD_RATE, PERMIT_DURATION_DAYS,
)

# =============================================================================
# DISCORD-SPECIFIC OVERRIDES
# =============================================================================
# These values differ from the standalone game's economy.

# Credits per watt per hour (Discord balance, not standalone $$$)
ELECTRICITY_RATE = 0.001

# Mean-reversion target for El Virtual price in credits (standalone uses $50k)
BTC_BASE_PRICE = 50.0

# Discord embed colours per rarity (integer hex, not CSS strings)
RARITY_COLOR = {
    "mythic":    0xAA00FF,
    "legendary": 0xFFD700,
    "epic":      0x9B59B6,
    "rare":      0x3498DB,
    "uncommon":  0x2ECC71,
    "common":    0x95A5A6,
}


# =============================================================================
# DISCORD-FLAVOURED ENVIRONMENTAL FUNCTIONS
# =============================================================================
# These override game_engine versions to add emoji guilt ratings for Discord.

def guilt_rating_co2(co2_tonnes: float) -> str:
    """Shame-based guilt rating with Discord-friendly emojis."""
    if co2_tonnes < 0.001:
        return "🌱 PRISTINE — A butterfly thanks you"
    elif co2_tonnes < 0.01:
        return "🌿 NEGLIGIBLE — One fewer dandelion, maybe"
    elif co2_tonnes < 0.1:
        return "🍃 MINOR — A small shrub frowns at you"
    elif co2_tonnes < 1.0:
        return "🌳 MODERATE — Several trees are disappointed"
    elif co2_tonnes < 5.0:
        return "🔥 NOTABLE — A forest ranger files a report"
    elif co2_tonnes < 20.0:
        return "🏭 SIGNIFICANT — Visible from a weather satellite"
    elif co2_tonnes < 100.0:
        return "💀 SEVERE — Greta Thunberg has entered the chat"
    elif co2_tonnes < 500.0:
        return "☢️ CATASTROPHIC — Penguins are filing a class-action lawsuit"
    elif co2_tonnes < 5000.0:
        return "🌋 APOCALYPTIC — You are personally melting a glacier"
    elif co2_tonnes < 50000.0:
        return "💥 EXTINCTION-LEVEL — Congrats, you're a geological event"
    else:
        return "🕳️ COSMIC HORROR — The Sun asks you to tone it down"


def guilt_rating(total_watts: float) -> str:
    """Annual guilt rating from watt draw."""
    return guilt_rating_co2(annual_co2_tonnes(total_watts))


def env_from_kwh(kwh: float) -> dict:
    """Derive env metrics from kWh; uses emoji guilt rating for Discord."""
    import game_engine as _ge
    result = dict(_ge.env_from_kwh(kwh))
    result["guilt_rating"] = guilt_rating_co2(result["co2_tonnes"])
    return result


def full_environmental_report(parts: list, price_per_kwh: float = 0.12) -> dict:
    """Full env report for a rig; uses emoji guilt rating for Discord."""
    import game_engine as _ge
    result = dict(_ge.full_environmental_report(parts, price_per_kwh))
    result["guilt_rating"] = guilt_rating_co2(result["annual_co2_tonnes"])
    return result


# =============================================================================
# HELPER FUNCTIONS (Discord-side only)
# =============================================================================

def build_rig(n: int = 5) -> dict:
    """Build a demo rig from N random finds (used by /bitcoin_rig)."""
    finds = random_finds(n)
    scores = [compute_score(hw) for hw in finds]
    return {
        "parts": finds,
        "scores": scores,
        "total_score": round(sum(scores), 2),
        "part_count": len(finds),
        "rarest_find": min(finds, key=lambda x: {
            "mythic": 0, "legendary": 1, "epic": 2,
            "rare": 3, "uncommon": 4, "common": 5
        }.get(x.get("rarity", "common"), 5)),
    }


# =============================================================================
# DISCORD UI VIEWS
# =============================================================================

class MyRigsView(discord.ui.View):
    """Paginated mining rig overview with prev/next buttons."""

    RIGS_PER_PAGE = 10

    def __init__(self, cog, user_id, guild_id, rig_summaries, totals, page=0):
        super().__init__(timeout=120)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.rig_summaries = rig_summaries  # list of one-line strings per rig
        self.totals = totals                # dict with aggregate stats
        self.page = page
        self.max_page = max(0, (len(rig_summaries) - 1) // self.RIGS_PER_PAGE)
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = self.page <= 0
        self.next_btn.disabled = self.page >= self.max_page

    def build_embed(self):
        t = self.totals
        start = self.page * self.RIGS_PER_PAGE
        end = start + self.RIGS_PER_PAGE
        page_lines = self.rig_summaries[start:end]

        embed = discord.Embed(
            title="\u26cf\ufe0f  Your Mining Operation",
            color=0xF7931A,
        )

        embed.add_field(
            name=f"\u2699\ufe0f Rigs (page {self.page + 1}/{self.max_page + 1})",
            value="\n".join(page_lines) if page_lines else "No rigs.",
            inline=False,
        )

        embed.add_field(
            name="\U0001f4ca Totals",
            value=(
                f"**Online:** {t['online']} \u00b7 **Offline:** {t['offline']}\n"
                f"**Combined Score:** `{t['score']:,.0f}`\n"
                f"**Total Power Draw:** `{t['watts']:,.0f}W` \u00b7 "
                f"`{t['elec_hr']:,.4f}` cr/hr\n"
                f"**Lifetime Mined:** `{t['lifetime']:,.6f}` BTC"
            ),
            inline=False,
        )

        embed.add_field(
            name="\U0001f4b0 Wallet",
            value=(
                f"**El Virtual:** `{t['btc_balance']:,.6f}` BTC\n"
                f"**Pending:** `{t['pending_btc']:,.6f}` BTC / "
                f"`{t['pending_elec']:,.4f}` cr electricity\n"
                f"**BTC Price:** `{t['btc_price']:,.2f}` credits\n"
                f"**Social Credits:** `{t['credits']:,.1f}`"
            ),
            inline=False,
        )

        le = t['lifetime_env']
        embed.add_field(
            name="\U0001f30d Lifetime Environmental Destruction",
            value=(
                f"**Energy:** `{le['kwh']:,.2f}` kWh \u00b7 "
                f"**CO\u2082:** `{le['co2_kg']:,.2f}` kg\n"
                f"\U0001f333 Trees: `{le['trees_negated']:,.2f}` \u00b7 "
                f"\U0001f334 Rainforest: `{le['rainforest_hectares']:.6f}` ha \u00b7 "
                f"\U0001f9ca Ice: `{le['arctic_ice_m3']:.6f}` m\u00b3\n"
                f"**Guilt:** {le['guilt_rating']}"
            ),
            inline=False,
        )

        embed.set_footer(
            text=f"{len(self.rig_summaries)} rigs \u00b7 /my_rigs <name> for details"
        )
        return embed

    @discord.ui.button(label="\u25c0", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("Not your rigs.", ephemeral=True)
        self.page = max(0, self.page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="\u25b6", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("Not your rigs.", ephemeral=True)
        self.page = min(self.max_page, self.page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


class RigBuilderView(discord.ui.View):
    """Select menu for choosing 5 parts to assemble into a mining rig."""

    def __init__(self, cog, user_id, guild_id, rig_name, parts_data):
        super().__init__(timeout=120)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.rig_name = rig_name

        options = []
        for inv_id, hw in parts_data[:25]:
            score = compute_score(hw)
            rarity = hw.get("rarity", "common")
            emoji = RARITY_EMOJI.get(rarity, "\u26aa")
            label = f"{hw['name']} ({hw['year']})"[:100]
            desc = f"{rarity.title()} \u00b7 {hw['type']} \u00b7 Score: {score:,.0f} \u00b7 {hw.get('tdp_watts', 0)}W"[:100]
            options.append(discord.SelectOption(
                label=label,
                value=str(inv_id),
                description=desc,
                emoji=emoji,
            ))

        select = discord.ui.Select(
            placeholder="Select exactly 5 parts for your rig\u2026",
            options=options,
            min_values=5,
            max_values=5,
        )
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "\U0001f6a8 This isn't your rig to build, citizen.", ephemeral=True
            )
            return

        selected_ids = [int(v) for v in interaction.data["values"]]

        rig_id = self.cog.mdb.create_rig(
            self.user_id, self.guild_id, self.rig_name, selected_ids
        )

        hw_ids = self.cog.mdb.get_rig_components(rig_id)
        parts = [HARDWARE_LOOKUP[hid] for hid in hw_ids if hid in HARDWARE_LOOKUP]
        total_score = sum(compute_score(p) for p in parts)
        total_watts = rig_total_watts(parts)
        elec_hr = total_watts * ELECTRICITY_RATE

        embed = discord.Embed(
            title=f"\u26a1 Rig Assembled: {self.rig_name}",
            description="Your new mining rig is ready!",
            color=0x00FF88,
        )

        parts_text = []
        for p in parts:
            emoji = RARITY_EMOJI.get(p.get("rarity", "common"), "\u26aa")
            parts_text.append(
                f"{emoji} **{p['name']}** ({p['year']}) \u00b7 `{compute_score(p):,.0f}`"
            )
        embed.add_field(name="Components", value="\n".join(parts_text), inline=False)
        embed.add_field(name="Compute Score", value=f"`{total_score:,.2f}`", inline=True)
        embed.add_field(name="Power Draw", value=f"`{total_watts:,.1f}W`", inline=True)
        embed.add_field(
            name="Electricity Cost",
            value=f"`{elec_hr:,.4f}` credits/hr",
            inline=True,
        )

        rig_count = self.cog.mdb.count_rigs(self.user_id, self.guild_id)
        embed.set_footer(text=f"Rigs: {rig_count} \u00b7 Use /toggle_rig to start mining!")

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)


class SellConfirmView(discord.ui.View):
    """Confirmation prompt before selling a part."""

    def __init__(self, cog, user_id, guild_id, inv_id, hw, sell_price):
        super().__init__(timeout=30)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.inv_id = inv_id
        self.hw = hw
        self.sell_price = sell_price
        self.resolved = False

    @discord.ui.button(label="Confirm Sale", style=discord.ButtonStyle.danger)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("Not your sale.", ephemeral=True)
        self.resolved = True

        removed = self.cog.mdb.remove_hardware(self.inv_id, self.user_id, self.guild_id)
        if removed is None:
            for child in self.children:
                child.disabled = True
            return await interaction.response.edit_message(
                content="That part no longer exists in your inventory.", embed=None, view=self
            )

        self.cog.mdb.add_btc(self.user_id, self.guild_id, self.sell_price)
        new_btc = self.cog.mdb.get_btc_balance(self.user_id, self.guild_id)

        rarity = self.hw.get("rarity", "common")
        score = compute_score(self.hw)
        emoji = RARITY_EMOJI.get(rarity, "⚪")
        btc_price = self.cog._get_btc_price(self.guild_id)
        credit_value = round(self.sell_price * btc_price, 2)

        embed = discord.Embed(
            title="💰 Part Sold!",
            description=(
                f"You offloaded some hardware on the black market:\n\n"
                f"{emoji} **{self.hw['name']}** ({self.hw['year']})\n"
                f"*{self.hw.get('manufacturer', 'Unknown')}* · `{self.hw['type']}` · "
                f"`{self.hw.get('tdp_watts', 0)}W`\n"
                f"Score: `{score:,.0f}` · *{rarity.title()}*"
            ),
            color=RARITY_COLOR.get(rarity, 0x95A5A6),
        )
        embed.add_field(name="Received", value=f"`{self.sell_price:,.6f}` BTC", inline=True)
        embed.add_field(name="≈ Credits", value=f"`{credit_value:,.2f}`", inline=True)
        embed.add_field(name="Wallet", value=f"`{new_btc:,.6f}` BTC", inline=True)

        last_refresh = self.cog.mdb.get_market_refresh_time(self.guild_id)
        remaining = max(0, int(last_refresh + MARKET_REFRESH_SECONDS - time.time()))
        h, remainder = divmod(remaining, 3600)
        m, s = divmod(remainder, 60)
        embed.set_footer(text=f"Market restock in {h}h {m}m {s}s")

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("Not your sale.", ephemeral=True)
        self.resolved = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="Sale cancelled.", embed=None, view=self)

    async def on_timeout(self):
        if not self.resolved:
            for child in self.children:
                child.disabled = True


class GiveConfirmView(discord.ui.View):
    """Confirmation prompt before giving a part to another user."""

    def __init__(self, cog, user_id, guild_id, inv_id, hw, recipient):
        super().__init__(timeout=30)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.inv_id = inv_id
        self.hw = hw
        self.recipient = recipient
        self.resolved = False

    @discord.ui.button(label="Confirm Gift", style=discord.ButtonStyle.success)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("Not your gift.", ephemeral=True)
        self.resolved = True

        success = self.cog.mdb.transfer_hardware(self.inv_id, self.user_id, self.guild_id, self.recipient.id)
        if not success:
            for child in self.children:
                child.disabled = True
            return await interaction.response.edit_message(
                content="That part no longer exists in your inventory.", embed=None, view=self
            )

        rarity = self.hw.get("rarity", "common")
        score = compute_score(self.hw)
        emoji = RARITY_EMOJI.get(rarity, "⚪")

        embed = discord.Embed(
            title="🎁 Part Given!",
            description=(
                f"{interaction.user.mention} gave a part to {self.recipient.mention}!\n\n"
                f"{emoji} **{self.hw['name']}** ({self.hw['year']})\n"
                f"*{self.hw.get('manufacturer', 'Unknown')}* · `{self.hw['type']}` · "
                f"`{self.hw.get('tdp_watts', 0)}W`\n"
                f"Score: `{score:,.0f}` · *{rarity.title()}*"
            ),
            color=RARITY_COLOR.get(rarity, 0x95A5A6),
        )

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("Not your gift.", ephemeral=True)
        self.resolved = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="Gift cancelled.", embed=None, view=self)

    async def on_timeout(self):
        if not self.resolved:
            for child in self.children:
                child.disabled = True


SORT_MODES = [
    ("id", "ID ↑", lambda x: x[0]),
    ("score_desc", "Score ↓", lambda x: compute_score(x[1])),
    ("score_asc", "Score ↑", lambda x: compute_score(x[1])),
    ("rarity", "Rarity ↓", lambda x: ["mythic", "legendary", "epic", "rare", "uncommon", "common"].index(x[1].get("rarity", "common"))),
    ("year", "Year ↑", lambda x: x[1].get("year", 0)),
    ("type", "Type A-Z", lambda x: x[1].get("type", "")),
]


class InventoryView(discord.ui.View):
    """Paginated hardware inventory browser with sort options."""

    ITEMS_PER_PAGE = 10

    def __init__(self, cog, user_id, guild_id, parts_data, page=0, sort_idx=0):
        super().__init__(timeout=120)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.original_data = list(parts_data)
        self.sort_idx = sort_idx
        self.page = page
        self._apply_sort()
        self._update_buttons()

    def _apply_sort(self):
        name, label, key_fn = SORT_MODES[self.sort_idx]
        reverse = name in ("score_desc", "rarity")
        self.parts_data = sorted(self.original_data, key=key_fn, reverse=reverse)
        self.max_page = max(0, (len(self.parts_data) - 1) // self.ITEMS_PER_PAGE)
        self.page = min(self.page, self.max_page)
        self.sort_btn.label = f"Sort: {label}"

    def _update_buttons(self):
        self.prev_btn.disabled = self.page <= 0
        self.next_btn.disabled = self.page >= self.max_page

    def build_embed(self):
        start = self.page * self.ITEMS_PER_PAGE
        end = start + self.ITEMS_PER_PAGE
        page_parts = self.parts_data[start:end]

        _, sort_label, _ = SORT_MODES[self.sort_idx]
        embed = discord.Embed(
            title="\U0001f4e6 Hardware Inventory",
            description=f"You own **{len(self.parts_data)}** parts.  ·  Sorted by **{sort_label}**",
            color=0x3498DB,
        )

        lines = []
        for inv_id, hw in page_parts:
            emoji = RARITY_EMOJI.get(hw.get("rarity", "common"), "\u26aa")
            score = compute_score(hw)
            lines.append(
                f"{emoji} **{hw['name']}** ({hw['year']}) \u00b7 "
                f"`{hw['type']}` \u00b7 Score: `{score:,.0f}` \u00b7 "
                f"`{hw.get('tdp_watts', 0)}W` \u00b7 ID: `{inv_id}`"
            )

        embed.add_field(
            name=f"Page {self.page + 1}/{self.max_page + 1}",
            value="\n".join(lines) if lines else "Empty \u2014 go `/scavenge` some hardware!",
            inline=False,
        )
        return embed

    @discord.ui.button(label="\u25c0", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("Not your inventory.", ephemeral=True)
        self.page = max(0, self.page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Sort: ID ↑", style=discord.ButtonStyle.primary)
    async def sort_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("Not your inventory.", ephemeral=True)
        self.sort_idx = (self.sort_idx + 1) % len(SORT_MODES)
        self._apply_sort()
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="\u25b6", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("Not your inventory.", ephemeral=True)
        self.page = min(self.max_page, self.page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


# =============================================================================
# DISCORD COG
# =============================================================================

class TrashCollector(commands.Cog):
    """Trash Collector \u2014 scavenge vintage hardware, build mining rigs, mine El Virtual."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.mdb = MiningDB()
        self.credit_db = CreditDB()
        self._decree_channel_id = None  # set via /set_decree_channel or bot config

    async def cog_load(self):
        self.daily_state_decree.start()

    def cog_unload(self):
        self.daily_state_decree.cancel()

    # ── Daily State Decree ────────────────────────────────────────────────

    @tasks.loop(time=datetime.time(hour=0, minute=0, tzinfo=datetime.timezone.utc))
    async def daily_state_decree(self):
        """
        Fires at midnight UTC every day.
        Redistributes the CPRM pool for every guild, then posts a State Decree
        to the first text channel named 'bot-commands', 'general', or 'trash-collector'
        that the bot can see — or the first available text channel.
        """
        for guild in self.bot.guilds:
            gid = guild.id
            pool_total = self.mdb.get_cprm_pool_total(gid)

            if pool_total <= 0:
                continue  # quiet day — the State has nothing to announce

            contributions = self.mdb.get_cprm_pool(gid)  # [(user_id, amount)]
            if not contributions:
                continue

            overhead      = pool_total * CPRM_OVERHEAD_RATE
            redistributed = pool_total - overhead
            total_contrib = sum(amt for _, amt in contributions)

            # Pay each contributor their proportional share back
            for user_id, contrib in contributions:
                if total_contrib > 0:
                    share = redistributed * (contrib / total_contrib)
                    self.mdb.add_btc(user_id, gid, share)

            # Convert overhead BTC → credits at current market price
            # and deposit into the guild slush fund.
            btc_price      = self._get_btc_price(gid)
            overhead_creds = overhead * btc_price
            self.credit_db.add_to_slush_fund(gid, overhead_creds)

            date_str = datetime.date.today().isoformat()
            self.mdb.log_cprm_history(
                gid, date_str, pool_total, overhead, redistributed
            )
            self.mdb.clear_cprm_pool(gid)

            # ── Build the Decree embed ────────────────────────────────────
            top_contributors = sorted(contributions, key=lambda x: x[1], reverse=True)[:3]
            top_lines = []
            for rank, (user_id, amt) in enumerate(top_contributors, 1):
                member = guild.get_member(user_id)
                name   = member.display_name if member else f"Citizen #{user_id}"
                top_lines.append(f"{rank}. **{name}** — `{amt:,.6f}` BTC contributed")

            embed = discord.Embed(
                title="🏛️ MINISTRY OF COMPUTATIONAL PROSPERITY",
                description=(
                    "**DAILY REDISTRIBUTION ORDER**\n"
                    f"*{date_str} — Issued under authority of the "
                    "Business Accountability & Planning Act, Schedule 4*"
                ),
                color=0xAA0000,
            )
            embed.add_field(
                name="📊 Today's CPRM Summary",
                value=(
                    f"**Total Collected:** `{pool_total:,.6f}` BTC\n"
                    f"**Administrative Overhead (retained):** `{overhead:,.6f}` BTC "
                    f"(`{overhead_creds:,.1f}` cr → slush fund)\n"
                    f"**Redistributed to Compliant Operators:** `{redistributed:,.6f}` BTC\n"
                    f"**Contributing Citizens:** `{len(contributions)}`"
                ),
                inline=False,
            )
            if top_lines:
                embed.add_field(
                    name="🎖️ Notable Contributors",
                    value="\n".join(top_lines),
                    inline=False,
                )
            embed.add_field(
                name="📜 Official Notice",
                value=(
                    "*Citizens are reminded that mining without a valid permit constitutes a "
                    "Schedule 4 violation of the Business Accountability & Planning Act. "
                    "Renew your permit with* `/get_permit`*.*\n\n"
                    "*The State thanks you for your Computational Prosperity Contributions. "
                    "Your compliance has been noted.*"
                ),
                inline=False,
            )
            embed.set_footer(
                text="You use electricity to make money. We use electricity to eat. We are not the same."
            )

            # Find a suitable channel to post in
            channel = None
            preferred = ["trash-collector", "bot-commands", "bot-spam", "general"]
            for name in preferred:
                channel = discord.utils.get(guild.text_channels, name=name)
                if channel and channel.permissions_for(guild.me).send_messages:
                    break
            if channel is None:
                for ch in guild.text_channels:
                    if ch.permissions_for(guild.me).send_messages:
                        channel = ch
                        break

            if channel:
                await channel.send(embed=embed)

    @daily_state_decree.before_loop
    async def before_decree(self):
        await self.bot.wait_until_ready()

    # ── helpers ──────────────────────────────────────────────────────────

    def _resolve_parts(self, hw_ids):
        """Turn a list of hardware_id strings into hardware dicts."""
        return [HARDWARE_LOOKUP[hid] for hid in hw_ids if hid in HARDWARE_LOOKUP]

    def _rig_stats(self, rig_id):
        """Return (parts, total_score, total_watts, combo_name, combo_desc) for a rig.

        Applies diversity, legendary, and combo (FPGA hypervisor) bonuses from game_engine.
        """
        hw_ids = self.mdb.get_rig_components(rig_id)
        parts = self._resolve_parts(hw_ids)
        base_score = sum(compute_score(p) for p in parts)
        div_mult = diversity_multiplier(parts)
        leg_mult = legendary_multiplier(parts)
        combo_mult, combo_name, combo_desc = combo_multiplier(parts)
        total_score = base_score * div_mult * leg_mult * combo_mult
        total_watts = rig_total_watts(parts)
        return parts, total_score, total_watts, combo_name, combo_desc

    def _get_btc_price(self, guild_id):
        """Get the current El Virtual price, applying random-walk updates."""
        price, last_updated = self.mdb.get_btc_price(guild_id)
        new_price = update_btc_price(price, last_updated)
        self.mdb.set_btc_price(guild_id, new_price)
        return new_price

    def _inventory_with_hw(self, user_id, guild_id):
        """Return [(inv_id, hw_dict), ...] for the user's inventory."""
        raw = self.mdb.get_inventory(user_id, guild_id)
        result = []
        for inv_id, hw_id in raw:
            hw = HARDWARE_LOOKUP.get(hw_id)
            if hw:
                result.append((inv_id, hw))
        return result

    # ── /bitcoin_rig (legacy demo) ──────────────────────────────────────

    @app_commands.command(
        name="bitcoin_rig",
        description="Scavenge 5 random pieces of vintage hardware and assemble a cursed mining rig (demo).",
    )
    async def bitcoin_rig(self, interaction: discord.Interaction):
        rig = build_rig(5)
        env = full_environmental_report(rig["parts"])
        rarest = rig["rarest_find"]
        embed_color = RARITY_COLOR.get(rarest.get("rarity", "common"), 0x95A5A6)

        embed = discord.Embed(
            title="\U0001f5d1\ufe0f  TRASH COLLECTOR \u2014 Bitcoin Rig Assembly",
            description="You rummage through the e-waste bins and pull out\u2026 *this*.",
            color=embed_color,
        )

        parts_lines = []
        for part, score in zip(rig["parts"], rig["scores"]):
            emoji = RARITY_EMOJI.get(part.get("rarity", "common"), "\u26aa")
            tdp = part.get("tdp_watts", 0)
            parts_lines.append(
                f"{emoji} **{part['name']}** ({part['year']})\n"
                f"  `{part['type']:<11}` Score: `{score:>12,.2f}` \u00b7 TDP: `{tdp}W`"
            )
        embed.add_field(name="\u2699\ufe0f  Salvaged Parts", value="\n".join(parts_lines), inline=False)

        rarest_emoji = RARITY_EMOJI.get(rarest.get("rarity", "common"), "\u26aa")
        embed.add_field(
            name="\U0001f4ca  Rig Stats",
            value=(
                f"**Total Score:** `{rig['total_score']:,.2f}`\n"
                f"**Rarest Find:** {rarest_emoji} "
                f"{rarest['name']} (*{rarest.get('rarity', '?')}*)"
            ),
            inline=False,
        )

        embed.add_field(
            name="\U0001f30d  Environmental Destruction Report",
            value=(
                f"**Power Draw:** `{env['total_watts']:,.1f} W`\n"
                f"**Annual Energy:** `{env['annual_kwh']:,.1f} kWh`\n"
                f"**CO\u2082/year:** `{env['annual_co2_kg']:,.1f} kg` ({env['annual_co2_tonnes']:.4f} t)\n"
                f"**\U0001f333 Trees Negated:** `{env['trees_negated']:,.1f}`\n"
                f"**\u26bd Soccer Fields Lost:** `{env['soccer_fields']:.4f}`\n"
                f"**\U0001f4b0 Annual Power Bill:** `${env['annual_electricity_cost_usd']:,.2f}`\n"
                f"**Guilt Rating:** {env['guilt_rating']}"
            ),
            inline=False,
        )

        embed.set_footer(
            text=f"{len(HARDWARE_DB)} hardware entries in the database \u00b7 scores use era rarity bonuses"
        )
        await interaction.response.send_message(embed=embed)

    # ── /scavenge ────────────────────────────────────────────────────────

    @app_commands.command(
        name="scavenge",
        description="Dig through e-waste to find hardware parts (2 hr cooldown).",
    )
    async def scavenge(self, interaction: discord.Interaction):
        uid, gid = interaction.user.id, interaction.guild.id

        last = self.mdb.get_cooldown(uid, gid, "scavenge")
        remaining = SCAVENGE_COOLDOWN - (time.time() - last)
        if remaining > 0:
            m, s = divmod(int(remaining), 60)
            h, m = divmod(m, 60)
            await interaction.response.send_message(
                f"\u23f3 The dumpster is picked clean. Come back in **{h}h {m}m {s}s**.",
                ephemeral=True,
            )
            return

        num_finds = random.choices([1, 2, 3], weights=[40, 45, 15], k=1)[0]
        finds = random_finds(num_finds)

        for hw in finds:
            self.mdb.add_hardware(uid, gid, hw["id"])
        self.mdb.set_cooldown(uid, gid, "scavenge")

        best = min(
            finds,
            key=lambda x: RARITY_ORDER.index(x.get("rarity", "common"))
            if x.get("rarity", "common") in RARITY_ORDER
            else 99,
        )
        embed_color = RARITY_COLOR.get(best.get("rarity", "common"), 0x95A5A6)

        embed = discord.Embed(
            title="\U0001f5d1\ufe0f  Dumpster Diving\u2026",
            description=f"You rummage through the e-waste and find **{num_finds}** piece{'s' if num_finds > 1 else ''}!",
            color=embed_color,
        )

        lines = []
        for hw in finds:
            emoji = RARITY_EMOJI.get(hw.get("rarity", "common"), "\u26aa")
            score = compute_score(hw)
            lines.append(
                f"{emoji} **{hw['name']}** ({hw['year']}) \u00b7 "
                f"`{hw['type']}` \u00b7 Score: `{score:,.0f}` \u00b7 "
                f"`{hw.get('tdp_watts', 0)}W`\n"
                f"  *{hw.get('description', '')}*"
            )
        embed.add_field(name="Salvaged", value="\n".join(lines), inline=False)

        inv_count = len(self.mdb.get_inventory(uid, gid))
        embed.set_footer(text=f"You now have {inv_count} parts in inventory \u00b7 Need {PARTS_PER_RIG} to /build_rig")
        await interaction.response.send_message(embed=embed)

    # ── /parts ───────────────────────────────────────────────────────────

    @app_commands.command(
        name="parts",
        description="View your hardware parts inventory.",
    )
    async def parts(self, interaction: discord.Interaction):
        uid, gid = interaction.user.id, interaction.guild.id
        parts_data = self._inventory_with_hw(uid, gid)

        if not parts_data:
            await interaction.response.send_message(
                "\U0001f4e6 Your inventory is empty. Use `/scavenge` to find parts!",
                ephemeral=True,
            )
            return

        view = InventoryView(self, uid, gid, parts_data)
        await interaction.response.send_message(embed=view.build_embed(), view=view)

    # ── /build_rig ───────────────────────────────────────────────────────

    @app_commands.command(
        name="build_rig",
        description="Assemble 5 parts from your inventory into a named mining rig.",
    )
    @app_commands.describe(name="A name for your new rig")
    async def build_rig_cmd(self, interaction: discord.Interaction, name: str):
        uid, gid = interaction.user.id, interaction.guild.id

        if len(name) > 32:
            return await interaction.response.send_message(
                "Rig name must be 32 characters or fewer.", ephemeral=True
            )

        if self.mdb.get_rig_by_name(uid, gid, name):
            return await interaction.response.send_message(
                f"You already have a rig called **{name}**. Pick a different name.",
                ephemeral=True,
            )

        parts_data = self._inventory_with_hw(uid, gid)
        if len(parts_data) < PARTS_PER_RIG:
            return await interaction.response.send_message(
                f"You need at least **{PARTS_PER_RIG}** parts. You have **{len(parts_data)}**. `/scavenge` more!",
                ephemeral=True,
            )

        note = ""
        if len(parts_data) > 25:
            note = f"\n*Showing your 25 highest-scoring parts out of {len(parts_data)}.*"
            parts_data.sort(key=lambda x: compute_score(x[1]), reverse=True)
            parts_data = parts_data[:25]

        embed = discord.Embed(
            title=f"\U0001f527 Building Rig: {name}",
            description=f"Select exactly **{PARTS_PER_RIG}** parts from the dropdown below.{note}",
            color=0x3498DB,
        )

        view = RigBuilderView(self, uid, gid, name, parts_data)
        await interaction.response.send_message(embed=embed, view=view)

    # ── /auto_build ──────────────────────────────────────────────────────
    # Greedy rig assembler.  Costs 10% of your BTC balance as a "consultant
    # fee" — when you outsource the thinking, you pay for it. :-{D
    #
    # Algorithm (polynomial time, not TSP):
    #  1. Sort all loose parts by individual score descending.
    #  2. For each rig slot, draft parts to maximise type diversity + combo
    #     bonus: FPGA first (hypervisor anchor), then GPU, CPU, ASIC, TPU,
    #     then fill remaining slots with the highest-score leftovers.
    #  3. Repeat until fewer than PARTS_PER_RIG parts remain.
    #  4. Create every assembled rig, name them Auto-Rig #N.

    @app_commands.command(
        name="auto_build",
        description="Auto-assemble rigs from loose parts for a 10% BTC consultant fee.",
    )
    async def auto_build(self, interaction: discord.Interaction):
        uid, gid = interaction.user.id, interaction.guild.id
        await interaction.response.defer(ephemeral=False)

        # ── Inventory ──────────────────────────────────────────────────
        raw_inv = self.mdb.get_inventory(uid, gid)   # [(inv_id, hw_id), ...]
        if len(raw_inv) < PARTS_PER_RIG:
            return await interaction.followup.send(
                f"⚙️ You need at least **{PARTS_PER_RIG}** loose parts to auto-build. "
                f"You only have **{len(raw_inv)}**. `/scavenge` more first!",
                ephemeral=True,
            )

        # ── Consultant fee ─────────────────────────────────────────────
        btc_balance = self.mdb.get_btc_balance(uid, gid)
        fee = btc_balance * 0.10
        if btc_balance <= 0 or fee <= 0:
            fee = 0.0   # broke? fine, the AI works pro-bono this once
        self.mdb.add_btc(uid, gid, -fee)

        # ── Build candidate pool ───────────────────────────────────────
        # Attach hw dict + score to each inventory row, sort best-first.
        pool = []
        for inv_id, hw_id in raw_inv:
            hw = HARDWARE_LOOKUP.get(hw_id)
            if hw is None:
                continue
            pool.append({
                "inv_id": inv_id,
                "hw_id":  hw_id,
                "hw":     hw,
                "type":   hw.get("type", "CPU").upper(),
                "score":  compute_score(hw),
            })
        pool.sort(key=lambda x: x["score"], reverse=True)

        # Preferred type order — FPGA anchors the combo bonus, GPU/CPU are
        # the workhorses, ASIC + TPU unlock the deeper combo tiers.
        DRAFT_ORDER = ["FPGA", "GPU", "CPU", "ASIC", "TPU",
                       "NEUROMORPHIC", "DSP", "MCU", "MEMORY",
                       "MOTHERBOARD", "DATACENTER", "ARRAY"]

        assembled_rigs = []   # list of lists of pool entries
        used_inv_ids   = set()

        while True:
            remaining = [p for p in pool if p["inv_id"] not in used_inv_ids]
            if len(remaining) < PARTS_PER_RIG:
                break

            # Draft one rig
            rig_parts = []
            drafted_types = set()

            # Pass 1 — one of each preferred type, best score within type
            for want_type in DRAFT_ORDER:
                if len(rig_parts) >= PARTS_PER_RIG:
                    break
                candidates = [
                    p for p in remaining
                    if p["type"] == want_type
                    and p["inv_id"] not in used_inv_ids
                    and p["type"] not in drafted_types
                ]
                if candidates:
                    pick = candidates[0]  # already sorted best-first
                    rig_parts.append(pick)
                    drafted_types.add(pick["type"])
                    used_inv_ids.add(pick["inv_id"])

            # Pass 2 — fill remaining slots with highest-score leftovers
            for p in remaining:
                if len(rig_parts) >= PARTS_PER_RIG:
                    break
                if p["inv_id"] not in used_inv_ids:
                    rig_parts.append(p)
                    used_inv_ids.add(p["inv_id"])

            if len(rig_parts) == PARTS_PER_RIG:
                assembled_rigs.append(rig_parts)

        if not assembled_rigs:
            # Refund fee — nothing got built
            self.mdb.add_btc(uid, gid, fee)
            return await interaction.followup.send(
                "⚙️ Couldn't assemble any complete rigs from your parts.",
                ephemeral=True,
            )

        # ── Determine next Auto-Rig number ────────────────────────────
        existing_rigs = self.mdb.get_rigs(uid, gid)
        existing_names = {r[1] for r in existing_rigs}
        auto_counter = 1
        def next_auto_name():
            nonlocal auto_counter
            while True:
                candidate = f"Auto-Rig #{auto_counter}"
                auto_counter += 1
                if candidate not in existing_names:
                    existing_names.add(candidate)
                    return candidate

        # ── Create rigs in DB ──────────────────────────────────────────
        created = []
        for rig_parts in assembled_rigs:
            rig_name = next_auto_name()
            inv_ids  = [p["inv_id"] for p in rig_parts]
            rig_id   = self.mdb.create_rig(uid, gid, rig_name, inv_ids)
            parts_hw = [p["hw"] for p in rig_parts]
            _, score, watts, combo_name, _ = self._rig_stats(rig_id)
            created.append({
                "name":       rig_name,
                "score":      score,
                "watts":      watts,
                "parts":      rig_parts,
                "combo_name": combo_name,
            })

        # ── Build result embed ─────────────────────────────────────────
        total_score = sum(r["score"] for r in created)
        embed = discord.Embed(
            title=f"🤖 Auto-Build Complete — {len(created)} Rig{'s' if len(created) != 1 else ''} Assembled",
            description=(
                f"The AI consultant has spoken.\n"
                f"**Consultant fee charged:** `{fee:.6f}` BTC (10% of balance)\n"
                f"**Total rigs built:** `{len(created)}`\n"
                f"**Combined compute score:** `{total_score:,.0f}`"
            ),
            color=0xF7931A,
        )

        for r in created:
            types_present = {p["type"] for p in r["parts"]}
            type_str = " · ".join(sorted(types_present))
            combo_str = f"  🧬 **{r['combo_name']}**" if r["combo_name"] else ""
            part_names = ", ".join(p["hw"]["name"] for p in r["parts"])
            embed.add_field(
                name=f"⚙️ {r['name']}",
                value=(
                    f"Score: `{r['score']:,.0f}` · Power: `{r['watts']:,.0f}W`\n"
                    f"Types: `{type_str}`{combo_str}\n"
                    f"*{part_names}*"
                ),
                inline=False,
            )

        parts_left = len(raw_inv) - (len(created) * PARTS_PER_RIG)
        embed.set_footer(
            text=f"{parts_left} part(s) left in inventory · Use /toggle_all_rigs on=True to start mining"
        )
        await interaction.followup.send(embed=embed)

    # ── /build_all ────────────────────────────────────────────────────────

    @app_commands.command(
        name="build_all",
        description="Build as many rigs as possible from loose parts. Fast, dumb, free.",
    )
    @app_commands.describe(prefix="Name prefix for rigs (default: auto)")
    async def build_all(self, interaction: discord.Interaction, prefix: str = "auto"):
        uid, gid = interaction.user.id, interaction.guild.id
        await interaction.response.defer()

        raw_inv = self.mdb.get_inventory(uid, gid)
        if len(raw_inv) < PARTS_PER_RIG:
            return await interaction.followup.send(
                f"⚙️ Need at least **{PARTS_PER_RIG}** loose parts. You have **{len(raw_inv)}**.",
                ephemeral=True,
            )

        # Sort by score desc, build rigs in batches of PARTS_PER_RIG
        from game_engine import HARDWARE_LOOKUP, compute_score
        pool = sorted(
            [(inv_id, hw_id) for inv_id, hw_id in raw_inv if hw_id in HARDWARE_LOOKUP],
            key=lambda x: compute_score(HARDWARE_LOOKUP[x[1]]),
            reverse=True,
        )

        existing_names = {r[1] for r in self.mdb.get_rigs(uid, gid)}
        counter = 1
        built = 0
        total_score = 0.0

        while len(pool) >= PARTS_PER_RIG:
            batch = pool[:PARTS_PER_RIG]
            pool  = pool[PARTS_PER_RIG:]

            name = f"{prefix}_{counter}"
            while name in existing_names:
                counter += 1
                name = f"{prefix}_{counter}"
            existing_names.add(name)

            inv_ids = [inv_id for inv_id, _ in batch]
            rig_id  = self.mdb.create_rig(uid, gid, name, inv_ids)
            _, score, _, *_ = self._rig_stats(rig_id)
            total_score += score
            built += 1
            counter += 1

        parts_left = len(pool)
        embed = discord.Embed(
            title="⚙️ Build All Complete",
            color=0x2ECC71,
        )
        embed.add_field(
            name="Summary",
            value=(
                f"**Rigs built:** `{built:,}`\n"
                f"**Combined score:** `{total_score:,.0f}`\n"
                f"**Parts left over:** `{parts_left}`\n"
                f"*Fast build — no diversity optimisation. Use `/auto_build` for smarter stacks.*"
            ),
            inline=False,
        )
        embed.set_footer(text=f"Use /toggle_all_rigs on=True to start mining")
        await interaction.followup.send(embed=embed)

    # ── /scrap_all ────────────────────────────────────────────────────────

    @app_commands.command(
        name="scrap_all",
        description="Scrap every rig you own and return all parts to inventory.",
    )
    async def scrap_all(self, interaction: discord.Interaction):
        uid, gid = interaction.user.id, interaction.guild.id
        await interaction.response.defer()

        rigs = self.mdb.get_rigs(uid, gid)
        if not rigs:
            return await interaction.followup.send(
                "You don't own any rigs to scrap.", ephemeral=True
            )

        total_parts = 0
        scrapped    = 0
        for rig in rigs:
            hw_ids = self.mdb.scrap_rig(rig[0], uid, gid)
            if hw_ids is not None:
                total_parts += len(hw_ids)
                scrapped    += 1

        embed = discord.Embed(
            title="🔧 Scrap All Complete",
            color=0xE74C3C,
        )
        embed.add_field(
            name="Summary",
            value=(
                f"**Rigs scrapped:** `{scrapped:,}`\n"
                f"**Parts returned to inventory:** `{total_parts:,}`"
            ),
            inline=False,
        )
        embed.set_footer(text="Use /build_all or /auto_build to rebuild.")
        await interaction.followup.send(embed=embed)

    # ── /scrap_num ────────────────────────────────────────────────────────

    @app_commands.command(
        name="scrap_num",
        description="Scrap the N lowest-scoring rigs and return parts to inventory.",
    )
    @app_commands.describe(count="Number of rigs to scrap (lowest score first)")
    async def scrap_num(self, interaction: discord.Interaction, count: int):
        uid, gid = interaction.user.id, interaction.guild.id
        await interaction.response.defer()

        if count <= 0:
            return await interaction.followup.send(
                "Count must be a positive number.", ephemeral=True
            )

        rigs = self.mdb.get_rigs(uid, gid)
        if not rigs:
            return await interaction.followup.send(
                "You don't own any rigs to scrap.", ephemeral=True
            )

        # Score all rigs, sort lowest first
        scored = []
        for r in rigs:
            _, score, _, *_ = self._rig_stats(r[0])
            scored.append((score, r))
        scored.sort(key=lambda x: x[0])
        to_scrap = scored[:count]

        total_parts = 0
        scrapped    = 0
        for _, rig in to_scrap:
            hw_ids = self.mdb.scrap_rig(rig[0], uid, gid)
            if hw_ids is not None:
                total_parts += len(hw_ids)
                scrapped    += 1

        lowest  = to_scrap[0][0]  if to_scrap else 0
        highest = to_scrap[-1][0] if to_scrap else 0

        embed = discord.Embed(
            title=f"🔧 Scrapped {scrapped:,} Lowest-Scoring Rigs",
            color=0xE67E22,
        )
        embed.add_field(
            name="Summary",
            value=(
                f"**Rigs scrapped:** `{scrapped:,}` of `{len(rigs):,}` total\n"
                f"**Score range:** `{lowest:,.0f}` – `{highest:,.0f}`\n"
                f"**Parts returned:** `{total_parts:,}`"
            ),
            inline=False,
        )
        embed.set_footer(text=f"{len(rigs) - scrapped:,} rigs remaining.")
        await interaction.followup.send(embed=embed)

    # ── /sell_all_parts ───────────────────────────────────────────────────

    @app_commands.command(
        name="sell_all_parts",
        description="Sell every loose part in your inventory for BTC.",
    )
    async def sell_all_parts(self, interaction: discord.Interaction):
        uid, gid = interaction.user.id, interaction.guild.id
        await interaction.response.defer()

        raw_inv = self.mdb.get_inventory(uid, gid)
        if not raw_inv:
            return await interaction.followup.send(
                "Your inventory is empty — nothing to sell.", ephemeral=True
            )

        # Bulk sell — same optimised path as standalone sell_part_all
        total_btc   = 0.0
        rarity_counts = {}
        inv_ids_to_delete = []

        for inv_id, hw_id in raw_inv:
            hw = HARDWARE_LOOKUP.get(hw_id)
            if hw is None:
                continue
            rarity     = hw.get("rarity", "common")
            score      = compute_score(hw)
            sell_price = round(RARITY_PRICE_MULT.get(rarity, 0.002) * max(score, 1) * 0.5, 6)
            total_btc += sell_price
            rarity_counts[rarity] = rarity_counts.get(rarity, 0) + 1
            inv_ids_to_delete.append(inv_id)

        self.mdb.remove_hardware_bulk(inv_ids_to_delete, uid, gid)
        self.mdb.add_btc(uid, gid, total_btc)

        price      = self._get_btc_price(gid)
        btc_bal    = self.mdb.get_btc_balance(uid, gid)
        cred_value = total_btc * price

        embed = discord.Embed(
            title="💰 Sell All Parts Complete",
            color=0xF7931A,
        )
        embed.add_field(
            name="Summary",
            value=(
                f"**Parts sold:** `{len(inv_ids_to_delete):,}`\n"
                f"**Total earned:** `{total_btc:,.6f}` BTC\n"
                f"**Market value:** `{cred_value:,.2f}` credits (at `{price:,.2f}`/BTC)"
            ),
            inline=False,
        )

        # Rarity breakdown
        breakdown = ""
        for rarity in RARITY_ORDER:
            if rarity in rarity_counts:
                emoji = RARITY_EMOJI.get(rarity, "⚪")
                breakdown += f"{emoji} {rarity.title()}: `{rarity_counts[rarity]:,}`\n"
        if breakdown:
            embed.add_field(name="By Rarity", value=breakdown, inline=False)

        embed.set_footer(text=f"Wallet: {btc_bal:,.6f} BTC")
        await interaction.followup.send(embed=embed)

    # ── /my_rigs ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="my_rigs",
        description="View your mining rigs. No args = list all, or pick a rig for details.",
    )
    @app_commands.describe(name="Name of a specific rig to inspect (leave empty for overview)")
    async def my_rigs(self, interaction: discord.Interaction, name: str = None):
        uid, gid = interaction.user.id, interaction.guild.id
        rigs = self.mdb.get_rigs(uid, gid)

        if not rigs:
            return await interaction.response.send_message(
                "\u26cf\ufe0f You don't own any rigs yet. `/scavenge` parts and `/build_rig`!",
                ephemeral=True,
            )

        # Defer so Discord doesn't time out on large rig counts
        await interaction.response.defer()

        now = time.time()

        # ── Detail view for a single rig ──
        if name is not None:
            rig = None
            for r in rigs:
                if r[1].lower() == name.lower():
                    rig = r
                    break
            if rig is None:
                return await interaction.followup.send(
                    f"No rig named **{name}** found.", ephemeral=True
                )

            rig_id, rig_name, is_running, started_at, last_collected, total_mined = rig
            parts, score, watts, combo_name, combo_desc = self._rig_stats(rig_id)
            elec_hr = watts * ELECTRICITY_RATE

            if is_running and last_collected:
                hours = (now - last_collected) / 3600.0
                pending_btc = score * MINING_RATE * hours
                pending_elec = watts * ELECTRICITY_RATE * hours
                runtime = now - started_at if started_at else 0
                rh, rm = divmod(int(runtime), 3600)
                rm = rm // 60
                status = f"\U0001f7e2 RUNNING ({rh}h {rm}m)"
            else:
                pending_btc = 0
                pending_elec = 0
                status = "\U0001f534 OFFLINE"

            env = full_environmental_report(parts)

            embed = discord.Embed(
                title=f"\u2699\ufe0f {rig_name}",
                color=0xF7931A,
            )

            embed.add_field(
                name="Status",
                value=status,
                inline=True,
            )
            embed.add_field(
                name="Compute Score",
                value=f"`{score:,.2f}`",
                inline=True,
            )
            embed.add_field(
                name="Power Draw",
                value=f"`{watts:,.1f}W` \u00b7 `{elec_hr:,.4f}` cr/hr",
                inline=True,
            )

            # List every part
            part_lines = []
            for p in parts:
                rarity = p.get("rarity", "common")
                emoji = RARITY_EMOJI.get(rarity, "\u26aa")
                pscore = compute_score(p)
                ptdp = p.get("tdp_watts", 0)
                part_lines.append(
                    f"{emoji} **{p['name']}** \u2014 "
                    f"`{p['type']}` \u00b7 Score: `{pscore:,.0f}` \u00b7 "
                    f"`{ptdp:.0f}W` \u00b7 *{rarity.title()}*"
                )

            # Discord field limit is 1024 chars; chunk if needed
            chunk = ""
            field_num = 1
            for line in part_lines:
                if len(chunk) + len(line) + 1 > 1020:
                    embed.add_field(
                        name=f"Parts ({field_num})" if field_num > 1 else f"Parts ({len(parts)})",
                        value=chunk,
                        inline=False,
                    )
                    chunk = ""
                    field_num += 1
                chunk += line + "\n"
            if chunk:
                embed.add_field(
                    name=f"Parts ({field_num})" if field_num > 1 else f"Parts ({len(parts)})",
                    value=chunk,
                    inline=False,
                )

            embed.add_field(
                name="\U0001f4b0 Mining",
                value=(
                    f"**Pending BTC:** `{pending_btc:,.6f}`\n"
                    f"**Pending Electricity:** `{pending_elec:,.4f}` cr\n"
                    f"**Lifetime Mined:** `{total_mined:,.6f}` BTC"
                ),
                inline=False,
            )

            if combo_name:
                embed.add_field(
                    name=f"\U0001f9ec Combo Bonus — {combo_name}",
                    value=combo_desc or "Heterogeneous stack synergy active.",
                    inline=False,
                )

            embed.add_field(
                name="\U0001f30d Environmental Destruction",
                value=(
                    f"\U0001f333 Trees/yr: `{env['trees_negated']:,.1f}` \u00b7 "
                    f"\U0001f334 Rainforest/yr: `{env['rainforest_hectares']:.4f}` ha\n"
                    f"**Guilt:** {env['guilt_rating']}"
                ),
                inline=False,
            )

            embed.set_footer(text="Use /my_rigs (no args) for the full overview.")
            return await interaction.followup.send(embed=embed)

        # ── Overview of all rigs (paginated) ──
        btc_balance = self.mdb.get_btc_balance(uid, gid)
        btc_price = self._get_btc_price(gid)
        credits = self.credit_db.get_credit(uid, gid)

        total_pending_btc = 0.0
        total_pending_elec = 0.0
        total_score = 0.0
        total_watts = 0.0
        total_lifetime = 0.0
        online_count = 0
        offline_count = 0
        rig_lines = []

        # Pre-score every rig so we can sort highest score first
        scored_rigs = []
        for r in rigs:
            rig_id = r[0]
            _, score, watts, *_ = self._rig_stats(rig_id)
            scored_rigs.append((score, watts, r))
        scored_rigs.sort(key=lambda x: x[0], reverse=True)

        for score, watts, (rig_id, rig_name, is_running, started_at, last_collected, total_mined) in scored_rigs:
            total_score += score
            total_watts += watts if is_running else 0
            total_lifetime += total_mined

            if is_running and last_collected:
                hours = (now - last_collected) / 3600.0
                pending_btc = score * MINING_RATE * hours
                pending_elec = watts * ELECTRICITY_RATE * hours
                total_pending_btc += pending_btc
                total_pending_elec += pending_elec
                online_count += 1
                status_dot = "\U0001f7e2"
            else:
                offline_count += 1
                status_dot = "\U0001f534"

            rig_lines.append(
                f"{status_dot} **{rig_name}** \u2014 "
                f"Score: `{score:,.0f}` \u00b7 `{watts:,.0f}W` \u00b7 "
                f"Mined: `{total_mined:,.4f}`"
            )

        total_kwh = self.mdb.get_total_kwh(uid, gid)
        lifetime_env = env_from_kwh(total_kwh)

        totals = {
            "online": online_count,
            "offline": offline_count,
            "score": total_score,
            "watts": total_watts,
            "elec_hr": total_watts * ELECTRICITY_RATE,
            "lifetime": total_lifetime,
            "btc_balance": btc_balance,
            "pending_btc": total_pending_btc,
            "pending_elec": total_pending_elec,
            "btc_price": btc_price,
            "credits": credits,
            "lifetime_env": lifetime_env,
        }

        view = MyRigsView(self, uid, gid, rig_lines, totals)
        await interaction.followup.send(embed=view.build_embed(), view=view)

    @my_rigs.autocomplete("name")
    async def my_rigs_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        rigs = self.mdb.get_rigs(interaction.user.id, interaction.guild.id)
        return [
            app_commands.Choice(name=r[1], value=r[1])
            for r in rigs
            if current.lower() in r[1].lower()
        ][:25]

    # ── /scrap_rig ───────────────────────────────────────────────────────

    @app_commands.command(
        name="scrap_rig",
        description="Disassemble a rig and return parts to your inventory.",
    )
    @app_commands.describe(name="Name of the rig to scrap")
    async def scrap_rig_cmd(self, interaction: discord.Interaction, name: str):
        uid, gid = interaction.user.id, interaction.guild.id
        rig = self.mdb.get_rig_by_name(uid, gid, name)
        if not rig:
            return await interaction.response.send_message(
                f"No rig named **{name}** found.", ephemeral=True
            )

        rig_id, rig_name, is_running, started_at, last_collected, total_mined = rig

        collected_btc = 0.0
        electricity_cost = 0.0
        # If running, auto-collect pending earnings first
        if is_running and last_collected:
            parts, score, watts, *_ = self._rig_stats(rig_id)
            hours = (time.time() - last_collected) / 3600.0
            collected_btc = score * MINING_RATE * hours
            electricity_cost = watts * ELECTRICITY_RATE * hours
            kwh_used = (watts / 1000.0) * hours

            current_credits = self.credit_db.get_credit(uid, gid)
            if current_credits < electricity_cost:
                if electricity_cost > 0:
                    ratio = max(0, current_credits / electricity_cost)
                else:
                    ratio = 1.0
                collected_btc *= ratio
                electricity_cost = current_credits
                kwh_used *= ratio

            if collected_btc > 0:
                self.mdb.add_btc(uid, gid, collected_btc)
            if electricity_cost > 0:
                self.credit_db.update_credit(uid, gid, -electricity_cost)
                new_credits = self.credit_db.get_credit(uid, gid)
                self.bot.dispatch("social_credit_change", interaction.user, new_credits)
            if kwh_used > 0:
                self.mdb.add_kwh(uid, gid, kwh_used)

        hw_ids = self.mdb.scrap_rig(rig_id, uid, gid)
        if hw_ids is None:
            return await interaction.response.send_message("Failed to scrap rig.", ephemeral=True)

        parts = self._resolve_parts(hw_ids)
        parts_text = ", ".join(p["name"] for p in parts)

        desc = f"**{rig_name}** has been scrapped. {len(parts)} parts returned to inventory."
        if collected_btc > 0:
            desc += f"\nFinal collection: `+{collected_btc:,.6f}` BTC, `-{electricity_cost:,.4f}` electricity."

        embed = discord.Embed(
            title="\U0001f527 Rig Scrapped",
            description=desc,
            color=0xE74C3C,
        )
        embed.add_field(name="Returned Parts", value=parts_text, inline=False)
        await interaction.response.send_message(embed=embed)

    @scrap_rig_cmd.autocomplete("name")
    async def scrap_rig_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        rigs = self.mdb.get_rigs(interaction.user.id, interaction.guild.id)
        return [
            app_commands.Choice(name=r[1], value=r[1])
            for r in rigs
            if current.lower() in r[1].lower()
        ][:25]

    # ── /toggle_rig ──────────────────────────────────────────────────────

    @app_commands.command(
        name="toggle_rig",
        description="Turn a mining rig on or off.",
    )
    @app_commands.describe(name="Name of the rig to toggle")
    async def toggle_rig_cmd(self, interaction: discord.Interaction, name: str):
        uid, gid = interaction.user.id, interaction.guild.id
        rig = self.mdb.get_rig_by_name(uid, gid, name)
        if not rig:
            return await interaction.response.send_message(
                f"No rig named **{name}** found.", ephemeral=True
            )

        rig_id = rig[0]
        was_running = bool(rig[2])
        btc_mined = 0.0
        elec_cost = 0.0

        # If turning OFF, auto-collect pending earnings
        if was_running and rig[4]:
            parts, score, watts, *_ = self._rig_stats(rig_id)
            hours = (time.time() - rig[4]) / 3600.0
            btc_mined = score * MINING_RATE * hours
            elec_cost = watts * ELECTRICITY_RATE * hours
            kwh_used = (watts / 1000.0) * hours

            current_credits = self.credit_db.get_credit(uid, gid)
            if current_credits < elec_cost:
                if elec_cost > 0:
                    ratio = max(0, current_credits / elec_cost)
                else:
                    ratio = 1.0
                btc_mined *= ratio
                elec_cost = current_credits
                kwh_used *= ratio

            if btc_mined > 0:
                self.mdb.add_btc(uid, gid, btc_mined)
                self.mdb.update_rig_collection(rig_id, btc_mined)
            if elec_cost > 0:
                self.credit_db.update_credit(uid, gid, -elec_cost)
                new_credits = self.credit_db.get_credit(uid, gid)
                self.bot.dispatch("social_credit_change", interaction.user, new_credits)
            if kwh_used > 0:
                self.mdb.add_kwh(uid, gid, kwh_used)

        new_state = self.mdb.toggle_rig(rig_id, uid, gid)
        if new_state is None:
            return await interaction.response.send_message("Rig not found.", ephemeral=True)

        parts, score, watts = self._rig_stats(rig_id)
        elec_hr = watts * ELECTRICITY_RATE

        if new_state:
            embed = discord.Embed(
                title=f"\U0001f7e2 {name} \u2014 ONLINE",
                description=(
                    f"Rig is now mining El Virtual.\n"
                    f"**Compute:** `{score:,.2f}` \u00b7 **Draw:** `{watts:,.1f}W` "
                    f"\u00b7 **Cost:** `{elec_hr:,.4f}` cr/hr"
                ),
                color=0x2ECC71,
            )
        else:
            desc = f"Rig powered down."
            if was_running:
                desc += (
                    f"\nCollected `{btc_mined:,.6f}` BTC, "
                    f"paid `{elec_cost:,.4f}` electricity."
                )
            embed = discord.Embed(
                title=f"\U0001f534 {name} \u2014 OFFLINE",
                description=desc,
                color=0xE74C3C,
            )
        await interaction.response.send_message(embed=embed)

    @toggle_rig_cmd.autocomplete("name")
    async def toggle_rig_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        rigs = self.mdb.get_rigs(interaction.user.id, interaction.guild.id)
        return [
            app_commands.Choice(name=r[1], value=r[1])
            for r in rigs
            if current.lower() in r[1].lower()
        ][:25]

    # ── /toggle_all_rigs ──────────────────────────────────────────────────

    @app_commands.command(
        name="toggle_all_rigs",
        description="Turn all your mining rigs on or off at once.",
    )
    @app_commands.describe(on="True = turn all rigs ON, False = turn all rigs OFF")
    async def toggle_all_rigs_cmd(self, interaction: discord.Interaction, on: bool):
        uid, gid = interaction.user.id, interaction.guild.id
        rigs = self.mdb.get_rigs(uid, gid)

        if not rigs:
            return await interaction.response.send_message(
                "\u26cf\ufe0f You don't own any rigs yet.", ephemeral=True
            )

        toggled = []
        total_collected_btc = 0.0
        total_elec_cost = 0.0

        for rig_id, rig_name, is_running, started_at, last_collected, total_mined in rigs:
            was_running = bool(is_running)

            # Skip rigs already in the desired state
            if was_running == on:
                continue

            # If turning OFF a running rig, collect pending earnings first
            if was_running and not on and last_collected:
                parts, score, watts, *_ = self._rig_stats(rig_id)
                hours = (time.time() - last_collected) / 3600.0
                btc_mined = score * MINING_RATE * hours
                elec_cost = watts * ELECTRICITY_RATE * hours
                kwh_used = (watts / 1000.0) * hours

                current_credits = self.credit_db.get_credit(uid, gid)
                if current_credits < elec_cost:
                    if elec_cost > 0:
                        ratio = max(0, current_credits / elec_cost)
                    else:
                        ratio = 1.0
                    btc_mined *= ratio
                    elec_cost = current_credits
                    kwh_used *= ratio

                if btc_mined > 0:
                    self.mdb.add_btc(uid, gid, btc_mined)
                    self.mdb.update_rig_collection(rig_id, btc_mined)
                if elec_cost > 0:
                    self.credit_db.update_credit(uid, gid, -elec_cost)
                if kwh_used > 0:
                    self.mdb.add_kwh(uid, gid, kwh_used)

                total_collected_btc += btc_mined
                total_elec_cost += elec_cost

            self.mdb.set_rig_running(rig_id, uid, gid, on)
            toggled.append(rig_name)

        if not toggled:
            state_word = "online" if on else "offline"
            return await interaction.response.send_message(
                f"All your rigs are already {state_word}.", ephemeral=True
            )

        # Dispatch credit change event once if any electricity was paid
        if total_elec_cost > 0:
            new_credits = self.credit_db.get_credit(uid, gid)
            self.bot.dispatch("social_credit_change", interaction.user, new_credits)

        if on:
            rig_list = ", ".join(f"**{n}**" for n in toggled)
            embed = discord.Embed(
                title=f"\U0001f7e2 {len(toggled)} Rig{'s' if len(toggled) != 1 else ''} \u2014 ONLINE",
                description=f"Started: {rig_list}",
                color=0x2ECC71,
            )
        else:
            rig_list = ", ".join(f"**{n}**" for n in toggled)
            desc = f"Stopped: {rig_list}"
            if total_collected_btc > 0:
                desc += (
                    f"\n\nFinal collection: `+{total_collected_btc:,.6f}` BTC, "
                    f"`-{total_elec_cost:,.4f}` electricity."
                )
            embed = discord.Embed(
                title=f"\U0001f534 {len(toggled)} Rig{'s' if len(toggled) != 1 else ''} \u2014 OFFLINE",
                description=desc,
                color=0xE74C3C,
            )

        await interaction.response.send_message(embed=embed)

    # ── /mine (active mining, 1 hr cooldown) ─────────────────────────────

    @app_commands.command(
        name="mine",
        description="Manually crank your rigs for a bonus mining cycle (1 hr cooldown).",
    )
    async def mine(self, interaction: discord.Interaction):
        uid, gid = interaction.user.id, interaction.guild.id

        last = self.mdb.get_cooldown(uid, gid, "mine")
        remaining = MINE_COOLDOWN - (time.time() - last)
        if remaining > 0:
            m, s = divmod(int(remaining), 60)
            return await interaction.response.send_message(
                f"\u23f3 Mining cooldown: **{m}m {s}s** remaining.", ephemeral=True
            )

        rigs = self.mdb.get_rigs(uid, gid)
        running = [(r[0], r[1]) for r in rigs if r[2]]

        if not running:
            return await interaction.response.send_message(
                "\u26a0\ufe0f You need at least one **running** rig to mine. Use `/toggle_rig` first.",
                ephemeral=True,
            )

        await interaction.response.defer()

        total_btc = 0.0
        total_elec = 0.0
        total_kwh_cycle = 0.0

        for rig_id, rig_name in running:
            parts, score, watts, *_ = self._rig_stats(rig_id)
            bonus_btc = score * MINING_RATE * ACTIVE_MINING_MULTIPLIER
            bonus_elec = watts * ELECTRICITY_RATE
            total_btc += bonus_btc
            total_elec += bonus_elec
            total_kwh_cycle += watts / 1000.0  # 1 hour of operation

        current_credits = self.credit_db.get_credit(uid, gid)
        if current_credits < total_elec:
            return await interaction.followup.send(
                f"\u26a1 Not enough credits for electricity! "
                f"Need `{total_elec:,.4f}`, have `{current_credits:,.1f}`.",
                ephemeral=True,
            )

        self.credit_db.update_credit(uid, gid, -total_elec)
        self.mdb.add_btc(uid, gid, total_btc)
        self.mdb.set_cooldown(uid, gid, "mine")

        if total_kwh_cycle > 0:
            self.mdb.add_kwh(uid, gid, total_kwh_cycle)

        # ── CPRM Assessment ───────────────────────────────────────────────
        all_rigs = self.mdb.get_rigs(uid, gid)
        total_rig_score = sum(
            self._rig_stats(r[0])[1] for r in all_rigs
        )
        tier_info = assess_permit_tier(total_rig_score)
        tier_num  = tier_info["tier"]

        cprm_deducted = 0.0
        cprm_applies  = (total_btc >= CPRM_THRESHOLD_BTC and tier_num > 0)
        if cprm_applies:
            cprm_deducted = total_btc * tier_info["cprm_rate"]
            self.mdb.add_btc(uid, gid, -cprm_deducted)
            self.mdb.add_cprm_contribution(uid, gid, cprm_deducted)

        new_credits = self.credit_db.get_credit(uid, gid)
        btc_bal = self.mdb.get_btc_balance(uid, gid)
        self.bot.dispatch("social_credit_change", interaction.user, new_credits)

        price = self._get_btc_price(gid)
        value = (total_btc - cprm_deducted) * price

        cycle_env = env_from_kwh(total_kwh_cycle)

        embed = discord.Embed(
            title="⛏️  Active Mining Cycle Complete!",
            color=0xF7931A,
        )
        embed.add_field(name="Rigs", value=f"{len(running)} rigs cranked", inline=True)
        embed.add_field(name="Total Mined", value=f"`{total_btc:,.6f}` BTC", inline=True)
        embed.add_field(name="Electricity", value=f"`{total_elec:,.4f}` credits", inline=True)
        embed.add_field(name="Market Value", value=f"`{value:,.2f}` credits", inline=True)
        embed.add_field(
            name="🌍 Environmental Cost",
            value=(
                f"CO₂: `{cycle_env['co2_kg']:,.2f}` kg · "
                f"🌴 Rainforest: `{cycle_env['rainforest_hectares']:.6f}` ha · "
                f"🌳 Trees: `{cycle_env['trees_negated']:,.2f}`"
            ),
            inline=False,
        )
        if cprm_applies:
            embed.add_field(
                name="🏛️ CPRM Deducted",
                value=(
                    f"`{cprm_deducted:,.6f}` BTC "
                    f"({tier_info['cprm_rate']*100:.0f}% · Tier {tier_num} — {tier_info['name']})"
                ),
                inline=False,
            )
        embed.set_footer(text=f"Wallet: {btc_bal:,.6f} BTC · Credits: {new_credits:,.1f}")
        await interaction.followup.send(embed=embed)

    # ── /get_permit ───────────────────────────────────────────────────────

    @app_commands.command(
        name="get_permit",
        description=(
            "Apply for or renew your Business Accountability & Planning Act mining permit. "
            "Fee paid in credits."
        ),
    )
    async def get_permit(self, interaction: discord.Interaction):
        import datetime as _dt
        uid, gid = interaction.user.id, interaction.guild.id
        await interaction.response.defer(ephemeral=True)

        now = time.time()

        # Assess current tier from total rig score
        all_rigs = self.mdb.get_rigs(uid, gid)
        total_score = 0.0
        for r in all_rigs:
            _, score, _, *_ = self._rig_stats(r[0])
            total_score += score

        tier_info  = assess_permit_tier(total_score)
        tier_num   = tier_info["tier"]
        tier_name  = tier_info["name"]
        weekly_fee = tier_info["weekly_fee"]

        if tier_num == 0:
            return await interaction.followup.send(
                "🏛️ **Ministry of Computational Prosperity**\n\n"
                "The State has reviewed your operation and determined you are operating at "
                "**Hobbyist (Exempt)** scale.\n\n"
                "No permit is required at this time. The State will continue monitoring your activity. "
                "That is all.",
                ephemeral=True,
            )

        # Check existing permit
        existing_tier, existing_expires, existing_score = self.mdb.get_permit(uid, gid)
        credits = self.credit_db.get_credit(uid, gid)

        if credits < weekly_fee:
            return await interaction.followup.send(
                f"🏛️ **Ministry of Computational Prosperity — Application Denied**\n\n"
                f"Your application for a **Tier {tier_num} — {tier_name}** permit has been reviewed.\n\n"
                f"**Required fee:** `{weekly_fee:,.0f}` credits\n"
                f"**Your balance:** `{credits:,.1f}` credits\n\n"
                f"Insufficient funds. Your operation is currently in violation of Schedule 4 "
                f"of the Business Accountability & Planning Act.\n\n"
                f"*The Ministry recommends you acquire more credits before reapplying. "
                f"Continued non-compliance has been noted.*",
                ephemeral=True,
            )

        # Deduct fee and issue/renew permit
        # If renewing before expiry, add 7 days from current expiry; otherwise from now
        base_time = max(now, existing_expires) if existing_expires > now else now
        new_expires = base_time + (PERMIT_DURATION_DAYS * 86400)
        self.credit_db.update_credit(uid, gid, -weekly_fee)
        self.credit_db.add_to_slush_fund(gid, weekly_fee)  # fee goes straight to State coffers
        self.mdb.upsert_permit(uid, gid, tier_num, new_expires, total_score)

        new_credits = self.credit_db.get_credit(uid, gid)
        expiry_str  = _dt.datetime.fromtimestamp(new_expires).strftime("%Y-%m-%d %H:%M UTC")
        renewed     = existing_expires > now

        embed = discord.Embed(
            title="🏛️ Ministry of Computational Prosperity",
            description=(
                f"{'Permit Renewed' if renewed else 'Permit Issued'} — "
                f"**Tier {tier_num}: {tier_name}**"
            ),
            color=0xF7931A,
        )
        embed.add_field(
            name="Permit Details",
            value=(
                f"**Tier:** {tier_num} — {tier_name}\n"
                f"**Valid Until:** `{expiry_str}`\n"
                f"**Duration:** {PERMIT_DURATION_DAYS} days\n"
                f"**Fee Paid:** `{weekly_fee:,.0f}` credits"
            ),
            inline=False,
        )
        embed.add_field(
            name="Your Current Assessment",
            value=(
                f"**Total Rig Score:** `{total_score:,.0f}`\n"
                f"**CPRM Rate:** `{tier_info['cprm_rate']*100:.0f}%` on collections over "
                f"`{CPRM_THRESHOLD_BTC:.0f}` BTC\n"
                f"**Credits Remaining:** `{new_credits:,.1f}`"
            ),
            inline=False,
        )
        embed.add_field(
            name="Official Notice",
            value=f"*{tier_info['flavour']}*",
            inline=False,
        )
        embed.set_footer(
            text="You use electricity to make money. We use electricity to eat. We are not the same."
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /collect_btc (passive earnings) ──────────────────────────────────

    @app_commands.command(
        name="collect_btc",
        description="Collect accumulated El Virtual from your running rigs and pay the electricity bill.",
    )
    async def collect_btc(self, interaction: discord.Interaction):
        uid, gid = interaction.user.id, interaction.guild.id
        rigs = self.mdb.get_rigs(uid, gid)
        running = [r for r in rigs if r[2]]  # is_running

        if not running:
            return await interaction.response.send_message(
                "No running rigs to collect from.", ephemeral=True
            )

        await interaction.response.defer()

        now = time.time()
        total_btc = 0.0
        total_elec = 0.0
        total_kwh_this_cycle = 0.0
        per_rig_btc = {}
        total_hours = 0.0

        for rig_id, name, _, started_at, last_collected, total_mined in running:
            parts, score, watts, *_ = self._rig_stats(rig_id)
            hours = (now - (last_collected or now)) / 3600.0
            btc = score * MINING_RATE * hours
            elec = watts * ELECTRICITY_RATE * hours
            total_btc += btc
            total_elec += elec
            total_kwh_this_cycle += (watts / 1000.0) * hours
            per_rig_btc[rig_id] = btc
            total_hours += hours

        avg_hours = total_hours / len(running) if running else 0
        ah, am = divmod(int(avg_hours * 60), 60)

        current_credits = self.credit_db.get_credit(uid, gid)
        shutdown = False

        if current_credits >= total_elec:
            self.credit_db.update_credit(uid, gid, -total_elec)
            self.mdb.add_btc(uid, gid, total_btc)
            for r in running:
                self.mdb.update_rig_collection(r[0], per_rig_btc.get(r[0], 0))
            actual_btc = total_btc
            actual_elec = total_elec
            if total_kwh_this_cycle > 0:
                self.mdb.add_kwh(uid, gid, total_kwh_this_cycle)
        else:
            if total_elec > 0:
                ratio = max(0, current_credits / total_elec)
            else:
                ratio = 1.0
            actual_btc = total_btc * ratio
            actual_elec = current_credits
            self.credit_db.update_credit(uid, gid, -actual_elec)
            self.mdb.add_btc(uid, gid, actual_btc)
            for r in running:
                self.mdb.shutdown_rig(r[0])
            shutdown = True
            if total_kwh_this_cycle > 0:
                self.mdb.add_kwh(uid, gid, total_kwh_this_cycle * ratio)

        # ── CPRM Assessment ───────────────────────────────────────────────
        # Assess permit tier against current total rig score, then deduct
        # the Computational Prosperity Redistribution Mechanism contribution
        # if this collection exceeds the State's threshold.
        all_rigs = self.mdb.get_rigs(uid, gid)
        total_rig_score = 0.0
        for r in all_rigs:
            _, score, _, *_ = self._rig_stats(r[0])
            total_rig_score += score

        tier_info = assess_permit_tier(total_rig_score)
        tier_num  = tier_info["tier"]
        tier_name = tier_info["name"]

        # Update permit record with current score
        existing_tier, existing_expires, _ = self.mdb.get_permit(uid, gid)
        if existing_expires == 0:
            # No permit on record — issue a grace permit expiring now
            # (player will need /get_permit to renew for next cycle)
            import datetime as _dt
            self.mdb.upsert_permit(uid, gid, tier_num, now, total_rig_score)
        else:
            self.mdb.upsert_permit(uid, gid, tier_num, existing_expires, total_rig_score)

        permit_expires = self.mdb.get_permit(uid, gid)[1]
        permit_valid   = permit_expires > now
        permit_days_left = max(0, (permit_expires - now) / 86400)

        # Deduct CPRM if collection is over threshold and tier > 0
        cprm_deducted = 0.0
        cprm_applies = (actual_btc >= CPRM_THRESHOLD_BTC and tier_num > 0)
        if cprm_applies:
            cprm_deducted = actual_btc * tier_info["cprm_rate"]
            self.mdb.add_btc(uid, gid, -cprm_deducted)
            self.mdb.add_cprm_contribution(uid, gid, cprm_deducted)

        new_credits = self.credit_db.get_credit(uid, gid)
        btc_bal     = self.mdb.get_btc_balance(uid, gid)
        self.bot.dispatch("social_credit_change", interaction.user, new_credits)

        price     = self._get_btc_price(gid)
        cycle_env = env_from_kwh(total_kwh_this_cycle)

        # ── Embed ─────────────────────────────────────────────────────────
        embed = discord.Embed(
            title="⚡ Mining Collection",
            color=0xE74C3C if shutdown else 0x2ECC71,
        )

        summary = (
            f"**Rigs Collected:** {len(running)} (avg {ah}h {am}m)\n"
            f"**Collected:** `{actual_btc:,.6f}` El Virtual\n"
            f"**Electricity Bill:** `{actual_elec:,.4f}` credits\n"
            f"**Net Value:** `{actual_btc * price:,.2f}` credits (at `{price:,.2f}`/BTC)"
        )
        if shutdown:
            summary += (
                f"\n\n⚠️ **INSUFFICIENT FUNDS** — all rigs shut down!\n"
                f"You could only afford `{actual_elec:,.4f}` of `{total_elec:,.4f}` electricity.\n"
                f"Received `{actual_btc:,.6f}` of `{total_btc:,.6f}` BTC (partial)."
            )
        embed.add_field(name="Summary", value=summary, inline=False)

        embed.add_field(
            name="🌍 Environmental Cost",
            value=(
                f"**Energy Used:** `{cycle_env['kwh']:,.2f}` kWh · "
                f"**CO₂:** `{cycle_env['co2_kg']:,.2f}` kg\n"
                f"🌳 Trees: `{cycle_env['trees_negated']:,.2f}` · "
                f"🌴 Rainforest: `{cycle_env['rainforest_hectares']:.6f}` ha\n"
                f"*Was it worth it?*"
            ),
            inline=False,
        )

        # CPRM / Permit status field
        if tier_num == 0:
            permit_text = (
                f"**Tier 0 — {tier_name}**\n"
                f"The State has not yet noticed your operation. Keep it that way.\n"
                f"*No CPRM applicable · No permit required*"
            )
        else:
            permit_status = (
                f"✅ Valid ({permit_days_left:.1f}d remaining)"
                if permit_valid
                else "❌ **EXPIRED** — renew with `/get_permit`"
            )
            cprm_line = (
                f"**CPRM Deducted:** `{cprm_deducted:,.6f}` BTC "
                f"({tier_info['cprm_rate']*100:.0f}% of `{actual_btc:,.6f}`)"
                if cprm_applies
                else f"*Collection under {CPRM_THRESHOLD_BTC:.0f} BTC threshold — CPRM not triggered*"
            )
            permit_text = (
                f"**Tier {tier_num} — {tier_name}**\n"
                f"Permit: {permit_status}\n"
                f"{cprm_line}"
            )

        embed.add_field(
            name="🏛️ Ministry of Computational Prosperity",
            value=permit_text,
            inline=False,
        )

        embed.set_footer(
            text=f"Wallet: {btc_bal:,.6f} BTC · Credits: {new_credits:,.1f}"
        )
        await interaction.followup.send(embed=embed)

    # ── /btc_price ───────────────────────────────────────────────────────

    @app_commands.command(
        name="btc_price",
        description="Check the current El Virtual exchange rate.",
    )
    async def btc_price_cmd(self, interaction: discord.Interaction):
        price = self._get_btc_price(interaction.guild.id)

        if price > BTC_BASE_PRICE * 1.2:
            trend = "\U0001f4c8 BULL"
            color = 0x2ECC71
        elif price < BTC_BASE_PRICE * 0.8:
            trend = "\U0001f4c9 BEAR"
            color = 0xE74C3C
        else:
            trend = "\U0001f4ca STABLE"
            color = 0xF7931A

        embed = discord.Embed(
            title="\U0001f4b1 El Virtual Exchange",
            color=color,
        )
        embed.add_field(name="Current Price", value=f"`{price:,.2f}` credits per BTC", inline=False)
        embed.add_field(name="Market Trend", value=trend, inline=True)
        embed.add_field(name="Base Price", value=f"`{BTC_BASE_PRICE:,.2f}`", inline=True)
        embed.add_field(
            name="Range",
            value=f"`{BTC_MIN_PRICE:,.0f}` \u2013 `{BTC_MAX_PRICE:,.0f}` credits",
            inline=True,
        )
        embed.set_footer(text="Price fluctuates over time \u00b7 Buy low, sell high!")
        await interaction.response.send_message(embed=embed)

    # ── /buy_btc ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="buy_btc",
        description="Buy El Virtual with Social Credits at the current market rate.",
    )
    @app_commands.describe(amount="Amount of Social Credits to spend on El Virtual")
    async def buy_btc_cmd(self, interaction: discord.Interaction, amount: float):
        uid, gid = interaction.user.id, interaction.guild.id

        if amount <= 0:
            return await interaction.response.send_message(
                "Amount must be positive.", ephemeral=True
            )

        credits = self.credit_db.get_credit(uid, gid)
        if credits < amount:
            return await interaction.response.send_message(
                f"Insufficient credits. You have `{credits:,.1f}` Social Credits.",
                ephemeral=True,
            )

        price = self._get_btc_price(gid)
        btc_bought = round(amount / price, 6)

        self.credit_db.update_credit(uid, gid, -amount)
        self.mdb.add_btc(uid, gid, btc_bought)

        new_credits = self.credit_db.get_credit(uid, gid)
        new_btc = self.mdb.get_btc_balance(uid, gid)
        self.bot.dispatch("social_credit_change", interaction.user, new_credits)

        embed = discord.Embed(
            title="\U0001f4b0 El Virtual Purchased!",
            color=0xF7931A,
        )
        embed.add_field(name="Spent", value=f"`{amount:,.2f}` credits", inline=True)
        embed.add_field(name="Price", value=f"`{price:,.2f}` cr/BTC", inline=True)
        embed.add_field(name="Received", value=f"`{btc_bought:,.6f}` BTC", inline=True)
        embed.set_footer(text=f"Wallet: {new_btc:,.6f} BTC \u00b7 Credits: {new_credits:,.1f}")
        await interaction.response.send_message(embed=embed)

    # ── /sell_btc ────────────────────────────────────────────────────────

    @app_commands.command(
        name="sell_btc",
        description="Sell El Virtual for Social Credits at the current market rate.",
    )
    @app_commands.describe(amount="Amount of El Virtual to sell")
    async def sell_btc_cmd(self, interaction: discord.Interaction, amount: float):
        uid, gid = interaction.user.id, interaction.guild.id

        if amount <= 0:
            return await interaction.response.send_message(
                "Amount must be positive.", ephemeral=True
            )

        balance = self.mdb.get_btc_balance(uid, gid)
        if balance < amount:
            return await interaction.response.send_message(
                f"Insufficient BTC. You have `{balance:,.6f}` El Virtual.",
                ephemeral=True,
            )

        price = self._get_btc_price(gid)
        payout = round(amount * price, 2)

        self.mdb.remove_btc(uid, gid, amount)
        self.credit_db.update_credit(uid, gid, payout)

        new_credits = self.credit_db.get_credit(uid, gid)
        new_btc = self.mdb.get_btc_balance(uid, gid)
        self.bot.dispatch("social_credit_change", interaction.user, new_credits)

        embed = discord.Embed(
            title="\U0001f4b5 El Virtual Sold!",
            color=0x2ECC71,
        )
        embed.add_field(name="Sold", value=f"`{amount:,.6f}` BTC", inline=True)
        embed.add_field(name="Price", value=f"`{price:,.2f}` cr/BTC", inline=True)
        embed.add_field(name="Received", value=f"`{payout:,.2f}` credits", inline=True)
        embed.set_footer(text=f"Wallet: {new_btc:,.6f} BTC \u00b7 Credits: {new_credits:,.1f}")
        await interaction.response.send_message(embed=embed)

    # ── Parts Market helpers ─────────────────────────────────────────────

    def _refresh_market_if_needed(self, guild_id):
        """Check if the market needs restocking, and restock if so. Returns current stock."""
        last_refresh = self.mdb.get_market_refresh_time(guild_id)
        now = time.time()

        current_stock = self.mdb.get_market_stock(guild_id)
        if now - last_refresh >= MARKET_REFRESH_SECONDS or len(current_stock) != MARKET_SLOTS:
            # Weighted selection: favour common/uncommon, rarer parts appear less often
            rarity_weights = {
                "common": 35, "uncommon": 25, "rare": 18,
                "epic": 12, "legendary": 7, "mythic": 3,
            }
            by_rarity = {}
            for hw in HARDWARE_DB:
                r = hw.get("rarity", "common")
                by_rarity.setdefault(r, []).append(hw)

            # Build a weighted pool
            pool = []
            weights = []
            for hw in HARDWARE_DB:
                r = hw.get("rarity", "common")
                w = rarity_weights.get(r, 10)
                pool.append(hw)
                weights.append(w)

            picks = random.choices(pool, weights=weights, k=MARKET_SLOTS)

            items = []
            for slot, hw in enumerate(picks, start=1):
                score = compute_score(hw)
                rarity = hw.get("rarity", "common")
                base_mult = RARITY_PRICE_MULT.get(rarity, 0.005)
                # Price = base rarity multiplier * score, with some randomness
                btc_price = round(base_mult * max(score, 1) * random.uniform(0.8, 1.3), 6)
                items.append((slot, hw["id"], btc_price))

            self.mdb.set_market_stock(guild_id, items)
            self.mdb.set_market_refresh_time(guild_id, now)

        return self.mdb.get_market_stock(guild_id)

    # ── /parts_market ─────────────────────────────────────────────────────

    @app_commands.command(
        name="parts_market",
        description="Browse the black market for hardware parts. Stock rotates every 3 hours.",
    )
    async def parts_market_cmd(self, interaction: discord.Interaction):
        gid = interaction.guild.id
        stock = self._refresh_market_if_needed(gid)
        btc_balance = self.mdb.get_btc_balance(interaction.user.id, gid)

        if not stock:
            return await interaction.response.send_message(
                "The market is empty. Check back later.", ephemeral=True
            )

        last_refresh = self.mdb.get_market_refresh_time(gid)
        next_refresh = last_refresh + MARKET_REFRESH_SECONDS
        remaining = max(0, int(next_refresh - time.time()))
        h, remainder = divmod(remaining, 3600)
        m, s = divmod(remainder, 60)

        embed = discord.Embed(
            title="\U0001f3ea Black Market Parts Dealer",
            description=(
                "A shady vendor spreads out some hardware on a blanket...\n"
                f"Use `/buy_part <slots>` to purchase (e.g. `1` or `1,3,5`).\n\n"
                f"Your wallet: `{btc_balance:,.6f}` BTC"
            ),
            color=0x2C2F33,
        )

        for slot, hw_id, btc_price in stock:
            hw = HARDWARE_LOOKUP.get(hw_id)
            if not hw:
                continue
            rarity = hw.get("rarity", "common")
            emoji = RARITY_EMOJI.get(rarity, "\u26aa")
            score = compute_score(hw)
            embed.add_field(
                name=f"Slot {slot}: {emoji} {hw['name']} ({hw['year']})",
                value=(
                    f"`{hw['type']}` \u00b7 Score: `{score:,.0f}` \u00b7 "
                    f"`{hw.get('tdp_watts', 0)}W`\n"
                    f"*{rarity.title()}* \u00b7 Price: **`{btc_price:,.6f}` BTC**"
                ),
                inline=True,
            )

        embed.set_footer(text=f"Stock refreshes in {h}h {m}m {s}s")
        await interaction.response.send_message(embed=embed)

    # ── /buy_part ──────────────────────────────────────────────────────────

    @app_commands.command(
        name="buy_part",
        description="Buy one or more parts from the black market using El Virtual.",
    )
    @app_commands.describe(slots="Slot number(s) to buy, comma-separated (e.g. 1 or 1,3,5)")
    async def buy_part_cmd(self, interaction: discord.Interaction, slots: str):
        uid, gid = interaction.user.id, interaction.guild.id

        # Parse slot numbers
        raw_parts = [p.strip() for p in slots.split(",") if p.strip()]
        slot_nums = []
        for raw in raw_parts:
            if not raw.isdigit():
                return await interaction.response.send_message(
                    f"`{raw}` is not a valid slot number.", ephemeral=True
                )
            n = int(raw)
            if n < 1 or n > MARKET_SLOTS:
                return await interaction.response.send_message(
                    f"Slot `{n}` is out of range (1-{MARKET_SLOTS}).", ephemeral=True
                )
            slot_nums.append(n)

        if not slot_nums:
            return await interaction.response.send_message(
                "No slot numbers provided.", ephemeral=True
            )

        # Deduplicate while preserving order
        seen = set()
        unique_slots = []
        for n in slot_nums:
            if n not in seen:
                seen.add(n)
                unique_slots.append(n)

        # Ensure market is current
        self._refresh_market_if_needed(gid)
        stock = self.mdb.get_market_stock(gid)
        stock_map = {s: (hw_id, btc_price) for s, hw_id, btc_price in stock}

        # Validate all slots and compute total cost before buying anything
        to_buy = []  # list of (slot, hw_id, hw, btc_price)
        total_cost = 0.0
        for s in unique_slots:
            if s not in stock_map:
                return await interaction.response.send_message(
                    f"Slot {s} is empty \u2014 someone already bought it or the market refreshed.",
                    ephemeral=True,
                )
            hw_id, btc_price = stock_map[s]
            hw = HARDWARE_LOOKUP.get(hw_id)
            if not hw:
                return await interaction.response.send_message(
                    f"Slot {s}: that part no longer exists in the catalogue.", ephemeral=True
                )
            to_buy.append((s, hw_id, hw, btc_price))
            total_cost += btc_price

        btc_balance = self.mdb.get_btc_balance(uid, gid)
        if btc_balance < total_cost:
            return await interaction.response.send_message(
                f"Not enough BTC. You need `{total_cost:,.6f}` but have `{btc_balance:,.6f}`.",
                ephemeral=True,
            )

        # Execute all purchases
        for s, hw_id, hw, btc_price in to_buy:
            self.mdb.remove_btc(uid, gid, btc_price)
            self.mdb.add_hardware(uid, gid, hw_id)
            self.mdb.remove_market_slot(gid, s)

        new_btc = self.mdb.get_btc_balance(uid, gid)

        # Build embed
        if len(to_buy) == 1:
            s, hw_id, hw, btc_price = to_buy[0]
            rarity = hw.get("rarity", "common")
            emoji = RARITY_EMOJI.get(rarity, "\u26aa")
            score = compute_score(hw)
            embed = discord.Embed(
                title="\U0001f4e6 Part Purchased!",
                description=(
                    f"You slip the vendor some crypto and walk away with:\n\n"
                    f"{emoji} **{hw['name']}** ({hw['year']})\n"
                    f"`{hw['type']}` \u00b7 Score: `{score:,.0f}` \u00b7 "
                    f"*{rarity.title()}*"
                ),
                color=RARITY_COLOR.get(rarity, 0x95A5A6),
            )
            embed.add_field(name="Paid", value=f"`{btc_price:,.6f}` BTC", inline=True)
            embed.add_field(name="Wallet", value=f"`{new_btc:,.6f}` BTC", inline=True)
            embed.set_footer(text="Part added to your inventory.")
        else:
            lines = []
            for s, hw_id, hw, btc_price in to_buy:
                rarity = hw.get("rarity", "common")
                emoji = RARITY_EMOJI.get(rarity, "\u26aa")
                score = compute_score(hw)
                lines.append(
                    f"{emoji} **{hw['name']}** ({hw['year']}) \u2014 "
                    f"`{hw['type']}` \u00b7 Score: `{score:,.0f}` \u00b7 "
                    f"*{rarity.title()}* \u00b7 `{btc_price:,.6f}` BTC"
                )
            embed = discord.Embed(
                title=f"\U0001f4e6 {len(to_buy)} Parts Purchased!",
                description=(
                    f"You slip the vendor some crypto and walk away with:\n\n"
                    + "\n".join(lines)
                ),
                color=0xF1C40F,
            )
            embed.add_field(name="Total Paid", value=f"`{total_cost:,.6f}` BTC", inline=True)
            embed.add_field(name="Wallet", value=f"`{new_btc:,.6f}` BTC", inline=True)
            embed.set_footer(text=f"{len(to_buy)} parts added to your inventory.")

        await interaction.response.send_message(embed=embed)

    # ── /sell_part ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="sell_part",
        description="Sell a part from your inventory for El Virtual.",
    )
    @app_commands.describe(part_id="The ID of the part to sell (shown in /parts)")
    async def sell_part_cmd(self, interaction: discord.Interaction, part_id: int):
        uid, gid = interaction.user.id, interaction.guild.id

        # Direct lookup by ID — no need to load the full inventory
        hw_id = self.mdb.get_hardware_by_id(part_id, uid, gid)
        if hw_id is None:
            return await interaction.response.send_message(
                "No part with that ID in your inventory. Check `/parts` for your IDs.",
                ephemeral=True,
            )

        hw = HARDWARE_LOOKUP.get(hw_id)
        if hw is None:
            return await interaction.response.send_message(
                "That part no longer exists in the catalogue.", ephemeral=True
            )

        rarity = hw.get("rarity", "common")
        score = compute_score(hw)
        sell_price = round(RARITY_PRICE_MULT.get(rarity, 0.002) * max(score, 1) * 0.5, 6)
        emoji = RARITY_EMOJI.get(rarity, "⚪")
        btc_price = self._get_btc_price(gid)
        credit_value = round(sell_price * btc_price, 2)

        # Show confirmation before selling
        embed = discord.Embed(
            title="🏷️ Confirm Sale",
            description=(
                f"Are you sure you want to sell this part?\n\n"
                f"{emoji} **{hw['name']}** ({hw['year']})\n"
                f"*{hw.get('manufacturer', 'Unknown')}* · `{hw['type']}` · "
                f"`{hw.get('tdp_watts', 0)}W`\n"
                f"Score: `{score:,.0f}` · *{rarity.title()}*\n\n"
                f"You will receive **`{sell_price:,.6f}`** BTC "
                f"(≈ `{credit_value:,.2f}` credits)"
            ),
            color=RARITY_COLOR.get(rarity, 0x95A5A6),
        )
        last_refresh = self.mdb.get_market_refresh_time(gid)
        remaining = max(0, int(last_refresh + MARKET_REFRESH_SECONDS - time.time()))
        h, remainder = divmod(remaining, 3600)
        m, s = divmod(remainder, 60)
        embed.set_footer(text=f"Sell price is 50% of market base value. Expires in 30s. · Market restock in {h}h {m}m {s}s")

        view = SellConfirmView(self, uid, gid, part_id, hw, sell_price)
        await interaction.response.send_message(embed=embed, view=view)

    # ── /give_part ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="give_part",
        description="Give a hardware part from your inventory to another user.",
    )
    @app_commands.describe(
        part_id="The ID of the part to give (shown in /parts)",
        recipient="The user to give the part to",
    )
    async def give_part_cmd(self, interaction: discord.Interaction, part_id: int, recipient: discord.Member):
        uid, gid = interaction.user.id, interaction.guild.id

        # Cannot give to yourself
        if recipient.id == uid:
            return await interaction.response.send_message(
                "You can't give a part to yourself.", ephemeral=True
            )

        # Cannot give to bots
        if recipient.bot:
            return await interaction.response.send_message(
                "You can't give parts to bots.", ephemeral=True
            )

        # Look up the part
        hw_id = self.mdb.get_hardware_by_id(part_id, uid, gid)
        if hw_id is None:
            return await interaction.response.send_message(
                "No part with that ID in your inventory. Check `/parts` for your IDs.",
                ephemeral=True,
            )

        hw = HARDWARE_LOOKUP.get(hw_id)
        if hw is None:
            return await interaction.response.send_message(
                "That part no longer exists in the catalogue.", ephemeral=True
            )

        rarity = hw.get("rarity", "common")
        score = compute_score(hw)
        emoji = RARITY_EMOJI.get(rarity, "⚪")

        # Show confirmation before giving
        embed = discord.Embed(
            title="🎁 Confirm Gift",
            description=(
                f"Are you sure you want to give this part to {recipient.mention}?\n\n"
                f"{emoji} **{hw['name']}** ({hw['year']})\n"
                f"*{hw.get('manufacturer', 'Unknown')}* · `{hw['type']}` · "
                f"`{hw.get('tdp_watts', 0)}W`\n"
                f"Score: `{score:,.0f}` · *{rarity.title()}*"
            ),
            color=RARITY_COLOR.get(rarity, 0x95A5A6),
        )
        embed.set_footer(text="Expires in 30s")

        view = GiveConfirmView(self, uid, gid, part_id, hw, recipient)
        await interaction.response.send_message(embed=embed, view=view)

    # ── /btc_wallet ──────────────────────────────────────────────────────

    @app_commands.command(
        name="btc_wallet",
        description="Check your El Virtual wallet balance.",
    )
    async def btc_wallet_cmd(self, interaction: discord.Interaction):
        uid, gid = interaction.user.id, interaction.guild.id
        balance = self.mdb.get_btc_balance(uid, gid)
        price = self._get_btc_price(gid)
        value = balance * price
        credits = self.credit_db.get_credit(uid, gid)

        embed = discord.Embed(
            title="\U0001f4b0 El Virtual Wallet",
            color=0xF7931A,
        )
        embed.add_field(name="BTC Balance", value=f"`{balance:,.6f}` El Virtual", inline=True)
        embed.add_field(name="Market Value", value=f"`{value:,.2f}` credits", inline=True)
        embed.add_field(name="Social Credits", value=f"`{credits:,.1f}`", inline=True)
        embed.add_field(
            name="Current Price",
            value=f"`{price:,.2f}` credits per BTC",
            inline=False,
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(TrashCollector(bot))
