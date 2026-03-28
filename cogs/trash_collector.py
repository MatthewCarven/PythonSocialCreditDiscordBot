"""
TRASH COLLECTOR - Hardware Definitions Database
================================================
A comprehensive catalogue of computational hardware spanning 50+ years.
Each entry represents a "trash find" the player can discover and combine
into the ultimate SUPER-HYPER-MEGA-ULTRA graphics rig.

Compute Score Formula:
    score = clock_mhz * (word_bits / 8) * cores * type_multiplier * era_bonus

Type Multipliers:
    CPU          = 1.0
    GPU          = 2.5  (parallel processing bonus)
    FPU          = 1.5  (floating point bonus)
    DSP          = 1.3  (signal processing bonus)
    MCU          = 0.6  (microcontroller penalty)
    APU          = 2.0  (accelerated processing)
    CUSTOM       = 1.8  (custom silicon bonus)
    COPROCESSOR  = 1.2

Era Bonus (rarity multiplier - older = rarer = more valuable in-game):
    pre-1975     = 5.0
    1975-1984    = 4.0
    1985-1994    = 3.0
    1995-2004    = 2.0
    2005-2014    = 1.5
    2015+        = 1.0

Usage:
    import random
    from trash_collector_hardware import HARDWARE_DB, compute_score, random_find

    # Get a random piece of hardware
    hw = random_find()
    print(f"You found: {hw['name']}! Score: {compute_score(hw)}")

    # Combine finds
    total = sum(compute_score(random_find()) for _ in range(5))
    print(f"Your rig scores: {total}")
"""

import random
import math
import time
import csv
import os
import discord
from discord.ext import commands
from discord import app_commands
from mining_db import MiningDB
from database import CreditDB

# =============================================================================
# TYPE MULTIPLIERS
# =============================================================================
TYPE_MULTIPLIERS = {
    "CPU":         1.0,
    "GPU":         2.5,
    "FPU":         1.5,
    "DSP":         1.3,
    "DSC":         1.3,
    "MCU":         0.6,
    "APU":         2.0,
    "CUSTOM":      1.8,
    "COPROCESSOR": 1.2,
    "FPGA":        1.4,
    "NPU":         2.2,
    "TPU":         2.8,
    "ASIC":        2.0,
    "SOC":         1.7,
    "DATACENTER":  5.0,
    "ARRAY":       3.5,
}

# =============================================================================
# ERA BONUS (rarity / collectibility)
# =============================================================================
def era_bonus(year: int) -> float:
    if year < 1975:
        return 5.0
    elif year < 1985:
        return 4.0
    elif year < 1995:
        return 3.0
    elif year < 2005:
        return 2.0
    elif year < 2015:
        return 1.5
    else:
        return 1.0


def compute_score(hw: dict) -> float:
    """Calculate the compute score for a piece of hardware.

    Uses hashrate_mhs when available (trash2 items), otherwise falls back
    to the classic clock * word_bits * cores formula (trash1 items).
    """
    hw_type = hw.get("type", "CPU")
    year = hw.get("year", 2000)
    tmult = TYPE_MULTIPLIERS.get(hw_type, 1.0)
    eb = era_bonus(year)

    hashrate = hw.get("hashrate_mhs", 0)
    if hashrate:
        # Hashrate-based scoring: log-scale so PH/s datacenter scores don't
        # utterly dwarf everything, but still rewards bigger rigs heavily.
        import math
        return round(math.log2(hashrate + 1) * 100 * tmult * eb, 2)

    clock = hw.get("clock_mhz", 0)
    bits = hw.get("word_bits", 8)
    cores = hw.get("cores", 1)
    return round(clock * (bits / 8) * cores * tmult * eb, 2)


# =============================================================================
# THE HARDWARE DATABASE  (loaded from trash.csv)
# =============================================================================
_INT_FIELDS = {"year", "word_bits", "cores", "process_nm", "transistors"}
_FLOAT_FIELDS = {"clock_mhz", "tdp_watts", "hashrate_mhs"}


def _load_hardware_csv(filename="trash.csv"):
    """Load hardware entries from a CSV file and return a list of dicts."""
    # look next to this file first, then project root
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, filename),
        os.path.join(here, "..", filename),
    ]
    for path in candidates:
        if os.path.isfile(path):
            break
    else:
        raise FileNotFoundError(f"Cannot find {filename} in {candidates}")

    entries = []
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            for k in _INT_FIELDS:
                if k in row and row[k]:
                    try:
                        row[k] = int(float(row[k]))
                    except (ValueError, TypeError):
                        row[k] = 0
            for k in _FLOAT_FIELDS:
                if k in row and row[k]:
                    try:
                        row[k] = float(row[k])
                    except (ValueError, TypeError):
                        row[k] = 0.0
            entries.append(row)
    return entries


HARDWARE_DB = _load_hardware_csv("trash.csv") + _load_hardware_csv("trash2.csv")
_HARDWARE_DB_PLACEHOLDER = [  # kept so the rest of the file parses; never used
]  # placeholder empty


# Fast lookup by hardware id
HARDWARE_LOOKUP = {hw["id"]: hw for hw in HARDWARE_DB}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def random_find() -> dict:
    """Simulate finding a random piece of hardware in the trash."""
    return random.choice(HARDWARE_DB)


def random_finds(n: int = 5) -> list:
    """Find multiple random hardware pieces."""
    return random.choices(HARDWARE_DB, k=n)


def build_rig(n: int = 5) -> dict:
    """Build a rig from N random finds and calculate total score."""
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


def get_by_era(start_year: int, end_year: int) -> list:
    """Get all hardware from a specific era."""
    return [hw for hw in HARDWARE_DB if start_year <= hw["year"] <= end_year]


def get_by_type(hw_type: str) -> list:
    """Get all hardware of a specific type."""
    return [hw for hw in HARDWARE_DB if hw["type"] == hw_type]


def get_by_manufacturer(manufacturer: str) -> list:
    """Get hardware by manufacturer (case-insensitive partial match)."""
    m = manufacturer.lower()
    return [hw for hw in HARDWARE_DB if m in hw["manufacturer"].lower()]


def leaderboard(n: int = 10) -> list:
    """Get top N hardware by compute score."""
    scored = [(hw, compute_score(hw)) for hw in HARDWARE_DB]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:n]




# =============================================================================
# ENVIRONMENTAL DESTRUCTION ENGINE
# =============================================================================
# Because every compute score needs a guilt trip.
#
# METHODOLOGY:
# ============
# We calculate environmental impact based on:
#   1. Power consumption (TDP watts) of all hardware running simultaneously
#   2. Assumed 24/7 operation (this IS a mining rig after all)
#   3. Global average carbon intensity of electricity: ~475g CO2/kWh (IEA)
#   4. Rainforest absorption rate: ~7.6 tonnes CO2 per hectare per year
#   5. One soccer field ≈ 0.714 hectares
#   6. Bonus: we also track in trees, pandas displaced, and ice caps melted.
#
# REAL FACTS USED:
#   - A mature tree absorbs ~22kg CO2/year (European Environment Agency)
#   - Amazon deforestation rate ~10,000 km²/year ≈ 1M hectares/year
#   - Global electricity carbon intensity: ~475g CO2/kWh (IEA 2023)
#   - Bitcoin network uses ~120 TWh/year (Cambridge estimate)
#   - A single RTX 4090 mining rig ≈ 3942 kWh/year
#   - Giant panda habitat: ~5900 km² remaining in the wild (WWF)

# --- Constants ---
CO2_GRAMS_PER_KWH = 475.0           # Global average grid carbon intensity
KG_CO2_PER_TREE_PER_YEAR = 22.0     # Mature tree annual CO2 absorption
TONNES_CO2_PER_HECTARE_YEAR = 7.6   # Tropical rainforest absorption
HECTARES_PER_SOCCER_FIELD = 0.714   # FIFA standard pitch
SQ_KM_PER_HECTARE = 0.01
PANDA_HABITAT_SQ_KM = 5900.0        # Total remaining wild giant panda habitat
ARCTIC_ICE_VOLUME_KM3 = 16500.0     # Summer + winter average Arctic sea ice
KG_CO2_PER_KM3_ICE_MELT = 3.3e12   # Very rough estimate
HOURS_PER_YEAR = 8760.0
GRAMS_PER_KG = 1000.0
KG_PER_TONNE = 1000.0

# =============================================================================
# MINING GAME CONSTANTS
# =============================================================================
ELECTRICITY_RATE = 0.001          # Social Credits per watt per hour
MINING_RATE = 1.0 / 5_000_000    # BTC per compute-score per hour
ACTIVE_MINING_MULTIPLIER = 2.0    # /mine gives 2x a one-hour cycle
SCAVENGE_COOLDOWN = 7200          # 2 hours
MINE_COOLDOWN = 3600              # 1 hour
PARTS_PER_RIG = 5
BTC_BASE_PRICE = 50.0             # Mean-reversion target (credits per El Virtual)
BTC_MIN_PRICE = 5.0
BTC_MAX_PRICE = 500.0
BTC_VOLATILITY = 0.03             # Per-hour price volatility
BTC_REVERSION = 0.01              # Mean-reversion strength per hour
MARKET_REFRESH_SECONDS = 10800    # 3 hours between market restocks
MARKET_SLOTS = 12                 # Number of parts available at a time

# BTC price multipliers per rarity for the parts market
RARITY_PRICE_MULT = {
    "common":    0.002,
    "uncommon":  0.005,
    "rare":      0.012,
    "epic":      0.025,
    "legendary": 0.060,
    "mythic":    0.150,
}


def update_btc_price(current_price: float, last_updated: float) -> float:
    """Random walk with mean reversion, stepped hourly."""
    elapsed_hours = (time.time() - last_updated) / 3600.0
    if elapsed_hours < 0.01:
        return current_price
    steps = max(1, min(int(elapsed_hours), 168))  # cap at 1 week of steps
    price = current_price
    for _ in range(steps):
        drift = BTC_REVERSION * (BTC_BASE_PRICE - price)
        shock = random.gauss(0, BTC_VOLATILITY * price)
        price += drift + shock
    return round(max(BTC_MIN_PRICE, min(BTC_MAX_PRICE, price)), 2)


def rig_total_watts(parts: list) -> float:
    """Total TDP of all parts in a rig."""
    return sum(hw.get("tdp_watts", 0) for hw in parts)


def annual_kwh(total_watts: float) -> float:
    """Annual energy consumption in kWh (24/7 operation)."""
    return (total_watts / 1000.0) * HOURS_PER_YEAR


def annual_co2_kg(total_watts: float) -> float:
    """Annual CO2 emissions in kg."""
    kwh = annual_kwh(total_watts)
    return (kwh * CO2_GRAMS_PER_KWH) / GRAMS_PER_KG


def annual_co2_tonnes(total_watts: float) -> float:
    """Annual CO2 emissions in metric tonnes."""
    return annual_co2_kg(total_watts) / KG_PER_TONNE


def trees_destroyed_equivalent(total_watts: float) -> float:
    """Number of trees whose annual CO2 absorption your rig negates."""
    return annual_co2_kg(total_watts) / KG_CO2_PER_TREE_PER_YEAR


def rainforest_hectares_destroyed(total_watts: float) -> float:
    """Hectares of rainforest whose absorption capacity your rig cancels out, per year."""
    return annual_co2_tonnes(total_watts) / TONNES_CO2_PER_HECTARE_YEAR


def soccer_fields_destroyed(total_watts: float) -> float:
    """Soccer fields of rainforest equivalent destroyed per year."""
    return rainforest_hectares_destroyed(total_watts) / HECTARES_PER_SOCCER_FIELD


def panda_habitat_percentage(total_watts: float) -> float:
    """Percentage of remaining giant panda habitat-equivalent your rig destroys."""
    hectares = rainforest_hectares_destroyed(total_watts)
    sq_km = hectares * SQ_KM_PER_HECTARE
    return (sq_km / PANDA_HABITAT_SQ_KM) * 100.0


def arctic_ice_equivalent_cm3(total_watts: float) -> float:
    """Cubic metres of Arctic ice your CO2 would melt (very rough estimate)."""
    co2_kg = annual_co2_kg(total_watts)
    # ~3.3 billion tonnes CO2 per km³ ice melt (extremely rough)
    km3 = co2_kg / KG_CO2_PER_KM3_ICE_MELT
    return km3 * 1e9  # Convert to cubic metres


def electricity_cost_annual(total_watts: float, price_per_kwh: float = 0.12) -> float:
    """Annual electricity cost in USD (default US avg ~$0.12/kWh)."""
    return annual_kwh(total_watts) * price_per_kwh


def guilt_rating_co2(co2_tonnes: float) -> str:
    """Return a shame-based guilt rating from raw CO2 tonnes."""
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
    """Return a shame-based guilt rating string (annual projection from watts)."""
    return guilt_rating_co2(annual_co2_tonnes(total_watts))


def env_from_kwh(kwh: float) -> dict:
    """Derive all environmental destruction metrics from actual kWh consumed."""
    co2_kg = (kwh * CO2_GRAMS_PER_KWH) / GRAMS_PER_KG
    co2_tonnes = co2_kg / KG_PER_TONNE
    rainforest = co2_tonnes / TONNES_CO2_PER_HECTARE_YEAR
    return {
        "kwh": round(kwh, 2),
        "co2_kg": round(co2_kg, 2),
        "co2_tonnes": round(co2_tonnes, 6),
        "trees_negated": round(co2_kg / KG_CO2_PER_TREE_PER_YEAR, 2),
        "rainforest_hectares": round(rainforest, 6),
        "soccer_fields": round(rainforest / HECTARES_PER_SOCCER_FIELD, 6),
        "panda_habitat_pct": round((rainforest * SQ_KM_PER_HECTARE / PANDA_HABITAT_SQ_KM) * 100, 10),
        "arctic_ice_m3": round((co2_kg / KG_CO2_PER_KM3_ICE_MELT) * 1e9, 6),
        "guilt_rating": guilt_rating_co2(co2_tonnes),
    }


def full_environmental_report(parts: list, price_per_kwh: float = 0.12) -> dict:
    """Generate a complete environmental destruction report for a rig."""
    watts = rig_total_watts(parts)
    report = {
        "total_watts": round(watts, 2),
        "annual_kwh": round(annual_kwh(watts), 2),
        "annual_co2_kg": round(annual_co2_kg(watts), 2),
        "annual_co2_tonnes": round(annual_co2_tonnes(watts), 4),
        "trees_negated": round(trees_destroyed_equivalent(watts), 1),
        "rainforest_hectares": round(rainforest_hectares_destroyed(watts), 4),
        "soccer_fields": round(soccer_fields_destroyed(watts), 4),
        "panda_habitat_pct": round(panda_habitat_percentage(watts), 8),
        "arctic_ice_m3": round(arctic_ice_equivalent_cm3(watts), 4),
        "annual_electricity_cost_usd": round(electricity_cost_annual(watts, price_per_kwh), 2),
        "guilt_rating": guilt_rating_co2(annual_co2_tonnes(watts)),
    }
    return report


def print_environmental_report(parts: list, price_per_kwh: float = 0.12):
    """Pretty-print the environmental destruction report."""
    r = full_environmental_report(parts, price_per_kwh)
    print()
    print("=" * 70)
    print("  🌍 ENVIRONMENTAL DESTRUCTION REPORT 🌍")
    print("=" * 70)
    print(f"  Total Rig Power Draw:      {r['total_watts']:>12,.1f} W")
    print(f"  Annual Energy Use:         {r['annual_kwh']:>12,.1f} kWh")
    print(f"  Annual CO₂ Emissions:      {r['annual_co2_kg']:>12,.1f} kg")
    print(f"                             {r['annual_co2_tonnes']:>12,.4f} tonnes")
    print(f"  ─────────────────────────────────────────────")
    print(f"  🌳 Trees Negated:          {r['trees_negated']:>12,.1f}")
    print(f"  🌴 Rainforest Destroyed:   {r['rainforest_hectares']:>12,.4f} hectares/yr")
    print(f"  ⚽ Soccer Fields Lost:      {r['soccer_fields']:>12,.4f}")
    print(f"  🐼 Panda Habitat Erased:   {r['panda_habitat_pct']:>12.8f} %")
    print(f"  🧊 Arctic Ice Melted:      {r['arctic_ice_m3']:>12,.4f} m³")
    print(f"  💰 Annual Power Bill:      ${r['annual_electricity_cost_usd']:>11,.2f}")
    print(f"  ─────────────────────────────────────────────")
    print(f"  GUILT RATING: {r['guilt_rating']}")
    print("=" * 70)
    print()

# =============================================================================
# RARITY HELPERS
# =============================================================================

RARITY_ORDER = ["mythic", "legendary", "epic", "rare", "uncommon", "common"]

RARITY_EMOJI = {
    "mythic":    "\U0001f30c",
    "legendary": "\u2b50",
    "epic":      "\U0001f7e3",
    "rare":      "\U0001f535",
    "uncommon":  "\U0001f7e2",
    "common":    "\u26aa",
}

RARITY_COLOR = {
    "mythic":    0xAA00FF,
    "legendary": 0xFFD700,
    "epic":      0x9B59B6,
    "rare":      0x3498DB,
    "uncommon":  0x2ECC71,
    "common":    0x95A5A6,
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

    # ── helpers ──────────────────────────────────────────────────────────

    def _resolve_parts(self, hw_ids):
        """Turn a list of hardware_id strings into hardware dicts."""
        return [HARDWARE_LOOKUP[hid] for hid in hw_ids if hid in HARDWARE_LOOKUP]

    def _rig_stats(self, rig_id):
        """Return (parts, total_score, total_watts) for a rig."""
        hw_ids = self.mdb.get_rig_components(rig_id)
        parts = self._resolve_parts(hw_ids)
        total_score = sum(compute_score(p) for p in parts)
        total_watts = rig_total_watts(parts)
        return parts, total_score, total_watts

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
            parts, score, watts = self._rig_stats(rig_id)
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

        for rig_id, rig_name, is_running, started_at, last_collected, total_mined in rigs:
            parts, score, watts = self._rig_stats(rig_id)
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
            parts, score, watts = self._rig_stats(rig_id)
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
            parts, score, watts = self._rig_stats(rig_id)
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
                parts, score, watts = self._rig_stats(rig_id)
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
            parts, score, watts = self._rig_stats(rig_id)
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

        new_credits = self.credit_db.get_credit(uid, gid)
        btc_bal = self.mdb.get_btc_balance(uid, gid)
        self.bot.dispatch("social_credit_change", interaction.user, new_credits)

        price = self._get_btc_price(gid)
        value = total_btc * price

        cycle_env = env_from_kwh(total_kwh_cycle)

        embed = discord.Embed(
            title="\u26cf\ufe0f  Active Mining Cycle Complete!",
            color=0xF7931A,
        )
        embed.add_field(name="Rigs", value=f"{len(running)} rigs cranked", inline=True)
        embed.add_field(name="Total Mined", value=f"`{total_btc:,.6f}` BTC", inline=True)
        embed.add_field(name="Electricity", value=f"`{total_elec:,.4f}` credits", inline=True)
        embed.add_field(name="Market Value", value=f"`{value:,.2f}` credits", inline=True)
        embed.add_field(
            name="\U0001f30d Environmental Cost",
            value=(
                f"CO\u2082: `{cycle_env['co2_kg']:,.2f}` kg \u00b7 "
                f"\U0001f334 Rainforest: `{cycle_env['rainforest_hectares']:.6f}` ha \u00b7 "
                f"\U0001f333 Trees: `{cycle_env['trees_negated']:,.2f}`"
            ),
            inline=False,
        )
        embed.set_footer(text=f"Wallet: {btc_bal:,.6f} BTC \u00b7 Credits: {new_credits:,.1f}")
        await interaction.followup.send(embed=embed)

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
            parts, score, watts = self._rig_stats(rig_id)
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

        new_credits = self.credit_db.get_credit(uid, gid)
        btc_bal = self.mdb.get_btc_balance(uid, gid)
        self.bot.dispatch("social_credit_change", interaction.user, new_credits)

        price = self._get_btc_price(gid)
        cycle_env = env_from_kwh(total_kwh_this_cycle)

        embed = discord.Embed(
            title="\u26a1 Mining Collection",
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
                f"\n\n\u26a0\ufe0f **INSUFFICIENT FUNDS** \u2014 all rigs shut down!\n"
                f"You could only afford `{actual_elec:,.4f}` of `{total_elec:,.4f}` electricity.\n"
                f"Received `{actual_btc:,.6f}` of `{total_btc:,.6f}` BTC (partial)."
            )
        embed.add_field(name="Summary", value=summary, inline=False)

        embed.add_field(
            name="\U0001f30d Environmental Cost",
            value=(
                f"**Energy Used:** `{cycle_env['kwh']:,.2f}` kWh \u00b7 "
                f"**CO\u2082:** `{cycle_env['co2_kg']:,.2f}` kg\n"
                f"\U0001f333 Trees: `{cycle_env['trees_negated']:,.2f}` \u00b7 "
                f"\U0001f334 Rainforest: `{cycle_env['rainforest_hectares']:.6f}` ha\n"
                f"*Was it worth it?*"
            ),
            inline=False,
        )

        embed.set_footer(text=f"Wallet: {btc_bal:,.6f} BTC \u00b7 Credits: {new_credits:,.1f}")
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
