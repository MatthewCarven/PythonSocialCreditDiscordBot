import discord
import sqlite3
import random
import io
import asyncio
from PIL import Image, ImageDraw, ImageFont
from pyfastnoiselite.pyfastnoiselite import FastNoiseLite, NoiseType, FractalType
import numpy as np
from database import CreditDB

EMOJI_MAP = {
    -1: "⬛",   # Unexplored
    0: "🟩",    # Grass
    1: "🌲",    # Forest
    2: "⛰️",    # Mountain
    3: "🌊",    # Water
    4: "⛲",    # Fountain
    5: "🏖️",    # Beach with umbrella
    6: "🏝️",    # Island
    7: "🏜️",    # Desert
    8: "🌋",    # Volcano
    9: "🏔️",    # Snow-capped mountain
    10: "🏕️",   # Camping
    11: "⛺",   # Tent
    12: "🏠",   # House
    13: "🏡",   # House with garden
    14: "🏘️",   # Houses
    15: "🏚️",   # Derelict house
    16: "🛖",   # Hut
    17: "🏗️",   # Construction site
    18: "🏭",   # Factory
    19: "🏢",   # Office building
    20: "🏬",   # Department store
    21: "🏤",   # Post office
    22: "🏥",   # Hospital
    23: "🏦",   # Bank
    24: "🏨",   # Hotel
    25: "🏪",   # Convenience store
    26: "🏫",   # School
    27: "🏩",   # Love hotel
    28: "💒",   # Wedding
    29: "🏛️",   # Classical building
    30: "⛪",   # Church
    31: "🕌",   # Mosque
    32: "🕍",   # Synagogue
    33: "🛕",   # Hindu temple
    34: "🕋",   # Kaaba
    35: "⛩️",   # Shinto shrine
    36: "🛤️",   # Railway track
    37: "🛣️",   # Motorway
    38: "🎑",   # Rice scene
    39: "🏞️",   # National park
    40: "🏙️",   # Cityscape
    41: "🍏",   # Green Apple
    42: "🍎",   # Red Apple
    43: "🍐",   # Pear
    44: "🍊",   # Tangerine
    45: "🍋",   # Lemon
    46: "🍌",   # Banana
    47: "🍉",   # Watermelon
    48: "🍇",   # Grapes
    49: "🍓",   # Strawberry
    50: "🫐",   # Blueberries
    51: "🍈",   # Melon
    52: "🍒",   # Cherries
    53: "🍑",   # Peach
    54: "🥭",   # Mango
    55: "🍍",   # Pineapple
    56: "🥥",   # Coconut
    57: "🥝",   # Kiwi
    58: "🍅",   # Tomato
    59: "🍆",   # Eggplant
    60: "🥑",   # Avocado
    61: "🫛",   # Pea Pod
    62: "🥦",   # Broccoli
    63: "🥬",   # Leafy Green
    64: "🥒",   # Cucumber
    65: "🌶️",   # Hot Pepper
    66: "🫑",   # Bell Pepper
    67: "🌽",   # Corn
    68: "🥕",   # Carrot
    69: "🫒",   # Olive
    70: "🧄",   # Garlic
    71: "🧅",   # Onion
    72: "🥔",   # Potato
    73: "🍠",   # Sweet Potato
    74: "🫚"    # Ginger Root
}

# ---------------------------------------------------------------------------
# Generation type presets
# Each preset tweaks the thresholds and noise offsets used during world gen.
# ---------------------------------------------------------------------------
GENERATION_TYPES = {
    'continental': {
        'water_level': 0.45, 'beach_level': 0.48,
        'mountain_level': 0.70, 'high_mountain_level': 0.78,
        'temp_offset': 0.0, 'moist_offset': 0.0, 'elev_scale': 1.0,
    },
    'archipelago': {
        'water_level': 0.53, 'beach_level': 0.56,
        'mountain_level': 0.72, 'high_mountain_level': 0.80,
        'temp_offset': 0.1, 'moist_offset': 0.0, 'elev_scale': 1.2,
    },
    'pangaea': {
        'water_level': 0.38, 'beach_level': 0.41,
        'mountain_level': 0.72, 'high_mountain_level': 0.82,
        'temp_offset': 0.0, 'moist_offset': 0.05, 'elev_scale': 1.0,
    },
    'frozen': {
        'water_level': 0.45, 'beach_level': 0.48,
        'mountain_level': 0.67, 'high_mountain_level': 0.76,
        'temp_offset': -0.35, 'moist_offset': 0.1, 'elev_scale': 1.0,
    },
    'scorched': {
        'water_level': 0.40, 'beach_level': 0.43,
        'mountain_level': 0.71, 'high_mountain_level': 0.80,
        'temp_offset': 0.35, 'moist_offset': -0.25, 'elev_scale': 1.0,
    },
    'volatile': {
        'water_level': 0.45, 'beach_level': 0.48,
        'mountain_level': 0.62, 'high_mountain_level': 0.72,
        'temp_offset': 0.0, 'moist_offset': 0.0, 'elev_scale': 0.5,
    },
}

BASE_ELEV_FREQ  = 0.004
BASE_BIOME_FREQ = 0.003
WARP_FREQ       = 0.008
WARP_STRENGTH   = 50.0

WORLD_WIDTH  = 500
WORLD_HEIGHT = 500

# Module-level globals set by _init_generators
WORLD_PARAMS = GENERATION_TYPES['continental']
WORLD_TYPE   = 'continental'
SEED         = 0

_elev_gen   = None
_warp_gen_x = None
_warp_gen_y = None
_temp_gen   = None
_moist_gen  = None

# ---------------------------------------------------------------------------
# Seed / world config persistence
# ---------------------------------------------------------------------------

def _load_or_create_seed(db_path='real_estate_bot.db'):
    with sqlite3.connect(db_path) as con:
        cur = con.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS world_config (key TEXT PRIMARY KEY, value TEXT)")

        cur.execute("SELECT value FROM world_config WHERE key = 'seed'")
        row = cur.fetchone()
        if row:
            seed = int(row[0])
        else:
            seed = random.randint(0, 999999)
            cur.execute("INSERT INTO world_config (key, value) VALUES ('seed', ?)", (str(seed),))

        cur.execute("SELECT value FROM world_config WHERE key = 'generation_type'")
        row = cur.fetchone()
        if row:
            gen_type = row[0]
        else:
            gen_type = random.choice(list(GENERATION_TYPES.keys()))
            cur.execute("INSERT INTO world_config (key, value) VALUES ('generation_type', ?)", (gen_type,))

        cur.execute("SELECT value FROM world_config WHERE key = 'width'")
        row = cur.fetchone()
        width = int(row[0]) if row else 500

        cur.execute("SELECT value FROM world_config WHERE key = 'height'")
        row = cur.fetchone()
        height = int(row[0]) if row else 500

        con.commit()
    return seed, gen_type, width, height


def _init_generators(seed, gen_type='continental'):
    global _elev_gen, _warp_gen_x, _warp_gen_y, _temp_gen, _moist_gen
    global WORLD_PARAMS, WORLD_TYPE, SEED

    p  = GENERATION_TYPES.get(gen_type, GENERATION_TYPES['continental'])
    es = p.get('elev_scale', 1.0)

    _elev_gen = FastNoiseLite()
    _elev_gen.seed = seed
    _elev_gen.noise_type     = NoiseType.NoiseType_OpenSimplex2
    _elev_gen.fractal_type   = FractalType.FractalType_FBm
    _elev_gen.fractal_octaves    = 6
    _elev_gen.fractal_lacunarity = 2.0
    _elev_gen.fractal_gain       = 0.5
    _elev_gen.frequency = BASE_ELEV_FREQ / max(es, 0.1)

    _warp_gen_x = FastNoiseLite()
    _warp_gen_x.seed = seed + 500
    _warp_gen_x.noise_type   = NoiseType.NoiseType_OpenSimplex2
    _warp_gen_x.fractal_type = FractalType.FractalType_FBm
    _warp_gen_x.fractal_octaves = 3
    _warp_gen_x.frequency = WARP_FREQ

    _warp_gen_y = FastNoiseLite()
    _warp_gen_y.seed = seed + 700
    _warp_gen_y.noise_type   = NoiseType.NoiseType_OpenSimplex2
    _warp_gen_y.fractal_type = FractalType.FractalType_FBm
    _warp_gen_y.fractal_octaves = 3
    _warp_gen_y.frequency = WARP_FREQ

    _temp_gen = FastNoiseLite()
    _temp_gen.seed = seed + 1000
    _temp_gen.noise_type   = NoiseType.NoiseType_OpenSimplex2
    _temp_gen.fractal_type = FractalType.FractalType_FBm
    _temp_gen.fractal_octaves = 4
    _temp_gen.frequency = BASE_BIOME_FREQ

    _moist_gen = FastNoiseLite()
    _moist_gen.seed = seed + 2000
    _moist_gen.noise_type   = NoiseType.NoiseType_OpenSimplex2
    _moist_gen.fractal_type = FractalType.FractalType_FBm
    _moist_gen.fractal_octaves = 4
    _moist_gen.frequency = BASE_BIOME_FREQ

    WORLD_PARAMS = p
    WORLD_TYPE   = gen_type
    SEED         = seed


_initial_seed, _initial_type, _initial_width, _initial_height = _load_or_create_seed()
WORLD_WIDTH  = _initial_width
WORLD_HEIGHT = _initial_height
_init_generators(_initial_seed, _initial_type)

# ---------------------------------------------------------------------------
# Noise sampling — single source of truth
# ---------------------------------------------------------------------------

def _get_noise_values(x, y):
    wx = x + _warp_gen_x.get_noise(x * WARP_FREQ, y * WARP_FREQ) * WARP_STRENGTH
    wy = y + _warp_gen_y.get_noise(x * WARP_FREQ + 5.2, y * WARP_FREQ + 1.3) * WARP_STRENGTH

    elevation   = (_elev_gen.get_noise(wx, wy) + 1) / 2
    temperature = (_temp_gen.get_noise(x, y)   + 1) / 2
    moisture    = (_moist_gen.get_noise(x, y)  + 1) / 2

    # Latitude gradient: equator (centre) warm, poles (edges) cold
    if WORLD_HEIGHT > 0:
        lat = abs(y / WORLD_HEIGHT - 0.5) * 2  # 0 at equator, 1 at poles
        temperature = temperature * 0.7 + (1.0 - lat) * 0.3

    # Island falloff: blend elevation toward ocean at world edges
    if WORLD_WIDTH > 0 and WORLD_HEIGHT > 0:
        dx = abs(x / WORLD_WIDTH  - 0.5) * 2
        dy = abs(y / WORLD_HEIGHT - 0.5) * 2
        dist    = max(dx, dy)
        falloff = max(0.0, 1.0 - max(0.0, dist - 0.6) / 0.4)
        wl      = WORLD_PARAMS['water_level']
        elevation = elevation * falloff + wl * 0.4 * (1.0 - falloff)

    # Elevation lapse rate: higher land = colder
    wl = WORLD_PARAMS['water_level']
    if elevation > wl:
        land_pct = (elevation - wl) / max(1.0 - wl, 0.001)
        temperature = max(0.0, temperature - land_pct * 0.35)

    temperature = max(0.0, min(1.0, temperature + WORLD_PARAMS.get('temp_offset',  0.0)))
    moisture    = max(0.0, min(1.0, moisture    + WORLD_PARAMS.get('moist_offset', 0.0)))

    return elevation, temperature, moisture

# ---------------------------------------------------------------------------
# Tile type (gameplay / DB)
# ---------------------------------------------------------------------------

def _tile_hash(x, y):
    """Deterministic, seed-dependent hash for tile (x, y). Returns float in [0, 1]."""
    h = (x * 1664525 ^ y * 1013904223 ^ SEED * 22695477) & 0xFFFFFFFF
    h = (((h >> 16) ^ h) * 0x45d9f3b) & 0xFFFFFFFF
    h = ((h >> 16) ^ h) & 0xFFFFFFFF
    return h / 0xFFFFFFFF


def get_tile_type(x, y):
    elevation, temperature, moisture = _get_noise_values(x, y)
    p = WORLD_PARAMS
    wl, bl, ml, hml = p['water_level'], p['beach_level'], p['mountain_level'], p['high_mountain_level']

    if elevation < wl:
        return 3   # Water
    if elevation < bl:
        return 6 if temperature > 0.65 else 5   # Island / Beach

    if elevation > hml:
        if temperature > 0.70 and moisture < 0.30:
            return 8   # Volcano
        return 9       # Snow peak
    if elevation > ml:
        return 2       # Mountain

    # Land biome
    if temperature > 0.68:
        if moisture < 0.30:
            return 7   # Desert
        if moisture > 0.65:
            return 5   # Lush tropical
        base = 0       # Savanna/grass
    elif temperature < 0.32:
        base = 9 if moisture < 0.45 else 1   # Tundra / Taiga
    else:
        base = 1 if moisture > 0.55 else 0   # Forest / Grass

    if base == 0:
        h = _tile_hash(x, y)
        if h > 0.88:
            bldgs = [12,13,14,16,19,20,21,22,23,24,25,26,29,30,31,32,33,34,35]
            return bldgs[int(_tile_hash(x + 1000, y) * len(bldgs))]
        if h < 0.12:
            return 41 + int(_tile_hash(x, y + 1000) * 34)

    return base

def generate_world(db_path, width=500, height=500, seed=None, gen_type='continental'):
    """Pre-generate the entire bounded world and store all tiles in the DB."""
    global WORLD_WIDTH, WORLD_HEIGHT
    WORLD_WIDTH  = width
    WORLD_HEIGHT = height

    if seed is None:
        seed = random.randint(0, 999999)

    _init_generators(seed, gen_type)

    with sqlite3.connect(db_path) as con:
        cur = con.cursor()
        cur.execute("DELETE FROM world_map")
        for key, val in [('seed', seed), ('generation_type', gen_type),
                          ('width', width), ('height', height)]:
            cur.execute(
                "INSERT OR REPLACE INTO world_config (key, value) VALUES (?, ?)",
                (key, str(val))
            )
        con.commit()

    p = WORLD_PARAMS
    wl, bl, ml, hml = p['water_level'], p['beach_level'], p['mountain_level'], p['high_mountain_level']

    ys = np.arange(height, dtype=np.float32)
    xs = np.arange(width,  dtype=np.float32)
    xx, yy = np.meshgrid(xs, ys)
    flat_x = xx.ravel()
    flat_y = yy.ravel()
    coords = np.stack([flat_x, flat_y], axis=0)

    # Domain warp
    wx_coords = np.stack([flat_x * WARP_FREQ,       flat_y * WARP_FREQ      ], axis=0)
    wy_coords = np.stack([flat_x * WARP_FREQ + 5.2, flat_y * WARP_FREQ + 1.3], axis=0)
    warped_x  = flat_x + _warp_gen_x.gen_from_coords(wx_coords) * WARP_STRENGTH
    warped_y  = flat_y + _warp_gen_y.gen_from_coords(wy_coords) * WARP_STRENGTH

    elevation   = (_elev_gen.gen_from_coords(np.stack([warped_x, warped_y], axis=0)) + 1) / 2
    temperature = (_temp_gen.gen_from_coords(coords)  + 1) / 2
    moisture    = (_moist_gen.gen_from_coords(coords)  + 1) / 2

    # Island falloff
    cx, cy = width / 2.0, height / 2.0
    dist    = np.maximum(np.abs(flat_x - cx) / cx, np.abs(flat_y - cy) / cy)
    falloff = np.clip(1.0 - np.maximum(0.0, dist - 0.6) / 0.4, 0.0, 1.0)
    elevation = elevation * falloff + wl * 0.4 * (1.0 - falloff)

    # Latitude gradient
    lat         = np.abs(flat_y / height - 0.5) * 2
    temperature = temperature * 0.7 + (1.0 - lat) * 0.3

    # Elevation lapse rate
    land_pct    = np.where(elevation > wl, (elevation - wl) / max(1.0 - wl, 0.001), 0.0)
    temperature = np.clip(temperature - land_pct * 0.35, 0.0, 1.0)

    temperature = np.clip(temperature + p.get('temp_offset',  0.0), 0.0, 1.0)
    moisture    = np.clip(moisture    + p.get('moist_offset', 0.0), 0.0, 1.0)

    n = width * height
    hot      = temperature > 0.68
    cold     = temperature < 0.32
    temperate = ~hot & ~cold

    # Vectorised biome classification
    tile_types = np.full(n, 3, dtype=np.int32)   # default: water

    mid_land = (elevation >= bl) & (elevation <= ml)
    tile_types[mid_land] = 0   # grass default for land
    tile_types[mid_land & hot  & (moisture < 0.30)]              = 7   # desert
    tile_types[mid_land & hot  & (moisture > 0.65)]              = 5   # tropical
    tile_types[mid_land & cold & (moisture < 0.45)]              = 9   # tundra
    tile_types[mid_land & cold & (moisture >= 0.45)]             = 1   # taiga
    tile_types[mid_land & temperate & (moisture > 0.55)]         = 1   # forest

    coast = (elevation >= wl) & (elevation < bl)
    tile_types[coast]                             = 5
    tile_types[coast & (temperature > 0.65)]      = 6

    mountain = (elevation > ml) & (elevation <= hml)
    tile_types[mountain] = 2

    hi_mt = elevation > hml
    tile_types[hi_mt]                                             = 9
    tile_types[hi_mt & (temperature > 0.70) & (moisture < 0.30)] = 8

    # Hash-based features on grass tiles
    grass_idx = np.where(tile_types == 0)[0]
    bldgs = [12,13,14,16,19,20,21,22,23,24,25,26,29,30,31,32,33,34,35]
    for idx in grass_idx:
        xi, yi = int(flat_x[idx]), int(flat_y[idx])
        h = _tile_hash(xi, yi)
        if h > 0.88:
            tile_types[idx] = bldgs[int(_tile_hash(xi + 1000, yi) * len(bldgs))]
        elif h < 0.12:
            tile_types[idx] = 41 + int(_tile_hash(xi, yi + 1000) * 34)

    # Batch write to DB
    with sqlite3.connect(db_path) as con:
        cur = con.cursor()
        data = [
            (int(flat_x[i]), int(flat_y[i]), int(tile_types[i]))
            for i in range(n)
        ]
        cur.executemany(
            "INSERT OR REPLACE INTO world_map (x, y, tile_type) VALUES (?, ?, ?)",
            data
        )
        con.commit()

    return seed


# ---------------------------------------------------------------------------
# Color rendering
# ---------------------------------------------------------------------------

def _lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def _noise_to_color(elevation, temperature, moisture):
    p = WORLD_PARAMS
    wl  = p['water_level']
    bl  = p['beach_level']
    ml  = p['mountain_level']
    hml = p['high_mountain_level']

    # Water — 4 depth bands: abyss → deep → ocean → shallow → cyan
    if elevation < wl:
        t = elevation / max(wl, 0.001)
        if t < 0.30:
            return _lerp_color((3,  6,  40),  (10,  28,  92),  t / 0.30)
        if t < 0.58:
            return _lerp_color((10, 28,  92),  (22,  80, 152),  (t - 0.30) / 0.28)
        if t < 0.82:
            return _lerp_color((22, 80,  152), (48, 148, 195),  (t - 0.58) / 0.24)
        return     _lerp_color((48, 148, 195), (75, 198, 218),  (t - 0.82) / 0.18)

    # Coast — shallow water → wet sand → dry sand
    if elevation < bl:
        t = (elevation - wl) / max(bl - wl, 0.001)
        if t < 0.40:
            return _lerp_color((75, 198, 218), (158, 212, 195), t / 0.40)
        return     _lerp_color((158, 212, 195), (215, 198, 130), (t - 0.40) / 0.60)

    # Very high — volcano or snow peaks
    if elevation > hml:
        t = (elevation - hml) / max(1.0 - hml, 0.001)
        if temperature > 0.75 and moisture < 0.25:
            return _lerp_color((200, 60, 20), (240, 120, 40), t)
        if t < 0.50:
            return _lerp_color((155, 135, 120), (218, 224, 232), t / 0.50)
        return     _lerp_color((218, 224, 232), (242, 246, 255), (t - 0.50) / 0.50)

    # Mountain
    if elevation > ml:
        t = (elevation - ml) / max(hml - ml, 0.001)
        return _lerp_color((98, 86, 70), (155, 135, 120), t)

    # Hot biomes
    if temperature > 0.68:
        if moisture < 0.30:
            return _lerp_color((205, 178, 72), (230, 208, 120), moisture / 0.30)  # Desert
        if moisture < 0.55:
            return _lerp_color((138, 170, 48), (88, 158, 46),  (moisture - 0.30) / 0.25)  # Savanna
        if moisture < 0.78:
            return _lerp_color((88,  158, 46),  (32, 128, 52),  (moisture - 0.55) / 0.23)  # Tropical
        return     _lerp_color((32,  128, 52),  (12,  88, 32),  (moisture - 0.78) / 0.22)  # Deep jungle

    # Cold biomes
    if temperature < 0.32:
        if moisture < 0.45:
            return _lerp_color((172, 190, 168), (198, 215, 195), moisture / 0.45)           # Tundra
        if moisture < 0.70:
            return _lerp_color((40,  88,  52),  (58, 112,  68),  (moisture - 0.45) / 0.25) # Taiga
        return     _lerp_color((58,  112, 68),  (25,  75,  42),  (moisture - 0.70) / 0.30) # Dense taiga

    # Temperate — 5 green bands from dry to ancient forest
    if moisture > 0.78:
        return _lerp_color((20,  78,  32),  (8,   52,  20),  (moisture - 0.78) / 0.22)  # Ancient forest
    if moisture > 0.58:
        return _lerp_color((45, 115,  44),  (20,  78,  32),  (moisture - 0.58) / 0.20)  # Forest
    if moisture > 0.38:
        return _lerp_color((85, 152,  52),  (45, 115,  44),  (moisture - 0.38) / 0.20)  # Lush grass / light forest
    if moisture > 0.20:
        return _lerp_color((122, 168, 62),  (85, 152,  52),  (moisture - 0.20) / 0.18)  # Grassland
    return         _lerp_color((148, 175, 68), (122, 168,  62), moisture / 0.20)          # Dry grass

# ---------------------------------------------------------------------------
# Viewport image (11x11 tiles, navigation view)
# ---------------------------------------------------------------------------

VIEWPORT_RADIUS  = 5
VIEWPORT_TILE_PX = 28


# ---------------------------------------------------------------------------
# Emoji overlay helpers
# ---------------------------------------------------------------------------

_EMOJI_FONT       = None
_EMOJI_FONT_READY = False

def _load_emoji_font(size):
    global _EMOJI_FONT, _EMOJI_FONT_READY
    if not _EMOJI_FONT_READY:
        _EMOJI_FONT_READY = True
        for path in [r"C:\Windows\Fonts\seguiemj.ttf", r"C:\Windows\Fonts\seguisym.ttf"]:
            try:
                _EMOJI_FONT = ImageFont.truetype(path, size)
                break
            except (IOError, OSError):
                pass
    return _EMOJI_FONT


def render_viewport_image(center_x, center_y):
    diameter = VIEWPORT_RADIUS * 2 + 1
    img_w = diameter * VIEWPORT_TILE_PX
    img_h = diameter * VIEWPORT_TILE_PX
    img  = Image.new("RGB", (img_w, img_h), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    for dy in range(diameter):
        for dx in range(diameter):
            wx = center_x - VIEWPORT_RADIUS + dx
            wy = center_y + VIEWPORT_RADIUS - dy   # flip Y: top of image = high world Y
            elevation, temperature, moisture = _get_noise_values(wx, wy)
            color = _noise_to_color(elevation, temperature, moisture)
            x0 = dx * VIEWPORT_TILE_PX
            y0 = dy * VIEWPORT_TILE_PX
            draw.rectangle([x0, y0, x0 + VIEWPORT_TILE_PX - 1, y0 + VIEWPORT_TILE_PX - 1], fill=color)

            tile_type = get_tile_type(wx, wy)
            if 41 <= tile_type <= 74:
                emoji = EMOJI_MAP[tile_type]
                font = _load_emoji_font(VIEWPORT_TILE_PX - 6)
                if font:
                    try:
                        bbox = draw.textbbox((0, 0), emoji, font=font)
                        tx = x0 + (VIEWPORT_TILE_PX - (bbox[2] - bbox[0])) // 2 - bbox[0]
                        ty = y0 + (VIEWPORT_TILE_PX - (bbox[3] - bbox[1])) // 2 - bbox[1]
                        draw.text((tx, ty), emoji, font=font, fill=(255, 255, 255), embedded_color=True)
                    except Exception:
                        pass

    # Crosshair at center tile
    cx = VIEWPORT_RADIUS * VIEWPORT_TILE_PX + VIEWPORT_TILE_PX // 2
    cy = VIEWPORT_RADIUS * VIEWPORT_TILE_PX + VIEWPORT_TILE_PX // 2
    r  = VIEWPORT_TILE_PX // 2 - 2
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 255, 255), width=2)
    draw.line([cx, cy - r - 3, cx, cy - r + 2],   fill=(255, 255, 255), width=1)
    draw.line([cx, cy + r - 2, cx, cy + r + 3],   fill=(255, 255, 255), width=1)
    draw.line([cx - r - 3, cy, cx - r + 2, cy],   fill=(255, 255, 255), width=1)
    draw.line([cx + r - 2, cy, cx + r + 3, cy],   fill=(255, 255, 255), width=1)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# ---------------------------------------------------------------------------
# Large overview image
# ---------------------------------------------------------------------------

def generate_map_image(center_x, center_y, radius=75):
    diameter = radius * 2 + 1
    tile_px  = max(2, 800 // diameter)
    img  = Image.new("RGB", (diameter * tile_px, diameter * tile_px), (20, 20, 40))
    draw = ImageDraw.Draw(img)

    for dy in range(diameter):
        for dx in range(diameter):
            wx = center_x - radius + dx
            wy = center_y + radius - dy
            elevation, temperature, moisture = _get_noise_values(wx, wy)
            color = _noise_to_color(elevation, temperature, moisture)
            x0 = dx * tile_px
            y0 = dy * tile_px
            draw.rectangle([x0, y0, x0 + tile_px - 1, y0 + tile_px - 1], fill=color)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# ---------------------------------------------------------------------------
# World reset confirm/reroll view
# ---------------------------------------------------------------------------

class WorldResetView(discord.ui.View):
    def __init__(self, db_path, seed, gen_type, image_bytes):
        super().__init__(timeout=300)
        self.db_path     = db_path
        self.seed        = seed
        self.gen_type    = gen_type
        self.image_bytes = image_bytes  # stored so we can re-use without re-rendering

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.channel.send(
            content=f"🌍 A new world has been generated!\n**Seed:** `{self.seed}`\n**Type:** {self.gen_type.title()}",
            file=discord.File(io.BytesIO(self.image_bytes), filename="new_world.png")
        )
        await interaction.response.edit_message(
            content="✅ New world announced to the channel!",
            attachments=[],
            view=None
        )
        self.stop()

    @discord.ui.button(label="🎲 Reroll", style=discord.ButtonStyle.secondary)
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        new_seed = random.randint(0, 999999)
        new_type = random.choice(list(GENERATION_TYPES.keys()))

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, generate_world, self.db_path, WORLD_WIDTH, WORLD_HEIGHT, new_seed, new_type
        )

        buf = await loop.run_in_executor(None, generate_map_image, WORLD_WIDTH // 2, WORLD_HEIGHT // 2, 150)

        self.seed        = new_seed
        self.gen_type    = new_type
        self.image_bytes = buf.read()

        await interaction.edit_original_response(
            content=f"🌍 World rerolled!\n**Seed:** `{new_seed}`\n**Type:** {new_type.title()}",
            attachments=[discord.File(io.BytesIO(self.image_bytes), filename="new_world.png")],
            view=self
        )


# ---------------------------------------------------------------------------
# Navigation view
# ---------------------------------------------------------------------------

class MapNavigation(discord.ui.View):
    def __init__(self, db_path, user, x=50, y=50):
        super().__init__(timeout=None)
        self.db_path = db_path
        self.user    = user
        self.x       = x
        self.y       = y
        self.step    = 1

    async def update_map(self, interaction: discord.Interaction):
        self.x = max(0, min(WORLD_WIDTH  - 1, self.x))
        self.y = max(0, min(WORLD_HEIGHT - 1, self.y))

        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute(
                "INSERT OR REPLACE INTO last_location (user_id, x, y) VALUES (?, ?, ?)",
                (str(self.user.id), self.x, self.y)
            )
            con.commit()

        loop = asyncio.get_running_loop()
        buf  = await loop.run_in_executor(None, render_viewport_image, self.x, self.y)

        embed = discord.Embed(
            title="🗺️ World Map",
            description=f"**Location:** ({self.x}, {self.y})  |  **World:** {WORLD_TYPE.title()}  |  **Seed:** `{SEED}`",
            color=discord.Color.green()
        )
        embed.set_image(url="attachment://viewport.png")
        embed.set_footer(text="Use the navigation buttons to explore")

        await interaction.response.edit_message(
            embed=embed,
            attachments=[discord.File(buf, filename="viewport.png")],
            view=self
        )

    @discord.ui.button(label="↖️", style=discord.ButtonStyle.secondary, row=0)
    async def move_up_left(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.x -= self.step; self.y += self.step
        await self.update_map(interaction)

    @discord.ui.button(label="⬆️", style=discord.ButtonStyle.secondary, row=0)
    async def move_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.y += self.step
        await self.update_map(interaction)

    @discord.ui.button(label="↗️", style=discord.ButtonStyle.secondary, row=0)
    async def move_up_right(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.x += self.step; self.y += self.step
        await self.update_map(interaction)

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary, row=1)
    async def move_left(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.x -= self.step
        await self.update_map(interaction)

    @discord.ui.button(label="🔍", style=discord.ButtonStyle.primary, row=1)
    async def inspect(self, interaction: discord.Interaction, button: discord.ui.Button):
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute(
                "SELECT tile_type, owner_id FROM world_map WHERE x = ? AND y = ?",
                (self.x, self.y)
            )
            tile = cur.fetchone()
            if tile:
                tile_type, owner_id = tile
            else:
                tile_type = get_tile_type(self.x, self.y)
                cur.execute(
                    "INSERT OR IGNORE INTO world_map (x, y, tile_type) VALUES (?, ?, ?)",
                    (self.x, self.y, tile_type)
                )
                con.commit()
                owner_id = None

            cur.execute("SELECT balance FROM users WHERE user_id = ?", (str(interaction.user.id),))
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO users (user_id, balance) VALUES (?, ?)",
                    (str(interaction.user.id), 1000)
                )
                con.commit()

        tile_emoji = EMOJI_MAP.get(tile_type, "❓")
        owner_name = "Unowned"
        if owner_id:
            try:
                owner = await interaction.client.fetch_user(int(owner_id))
                owner_name = owner.name
            except (discord.NotFound, ValueError):
                owner_name = "Unknown User"

        embed = discord.Embed(
            title="Tile Information",
            description=f"**Tile:** {tile_emoji}\n**Coordinates:** ({self.x}, {self.y})\n**Owner:** {owner_name}"
        )
        view = TileActionView(self.db_path, interaction.user, self.x, self.y, tile_type, owner_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary, row=1)
    async def move_right(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.x += self.step
        await self.update_map(interaction)

    @discord.ui.button(label="↙️", style=discord.ButtonStyle.secondary, row=2)
    async def move_down_left(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.x -= self.step; self.y -= self.step
        await self.update_map(interaction)

    @discord.ui.button(label="⬇️", style=discord.ButtonStyle.secondary, row=2)
    async def move_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.y -= self.step
        await self.update_map(interaction)

    @discord.ui.button(label="↘️", style=discord.ButtonStyle.secondary, row=2)
    async def move_down_right(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.x += self.step; self.y -= self.step
        await self.update_map(interaction)

    @discord.ui.button(label="🚶 Walk", style=discord.ButtonStyle.secondary, row=3)
    async def toggle_sprint(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.step == 1:
            self.step    = 10
            button.label = "🏃 Sprint"
            button.style = discord.ButtonStyle.success
        else:
            self.step    = 1
            button.label = "🚶 Walk"
            button.style = discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)


# ---------------------------------------------------------------------------
# Tile action view (claim land)
# ---------------------------------------------------------------------------

class TileActionView(discord.ui.View):
    def __init__(self, db_path, user, x, y, tile_type, owner_id):
        super().__init__(timeout=180)
        self.db_path   = db_path
        self.user      = user
        self.x         = x
        self.y         = y
        self.tile_type = tile_type
        self.owner_id  = owner_id
        self.credit_db = CreditDB()
        self.land_price = 100

        claim_button = discord.ui.Button(
            label=f"Claim Land ({self.land_price} SC)",
            style=discord.ButtonStyle.green,
            disabled=(owner_id is not None)
        )
        claim_button.callback = self.claim_land
        self.add_item(claim_button)

    async def claim_land(self, interaction: discord.Interaction):
        user_id  = self.user.id
        guild_id = interaction.guild.id

        current_credit = self.credit_db.get_credit(user_id, guild_id)

        if current_credit >= self.land_price:
            self.credit_db.update_credit(user_id, guild_id, -self.land_price)

            with sqlite3.connect(self.db_path) as con:
                cur = con.cursor()
                cur.execute(
                    "UPDATE world_map SET owner_id = ? WHERE x = ? AND y = ?",
                    (str(user_id), self.x, self.y)
                )
                con.commit()

            new_credit = current_credit - self.land_price
            await interaction.response.edit_message(
                content=f"You have successfully claimed the land at ({self.x}, {self.y}) for {self.land_price} Social Credits. Your new balance is {new_credit:.2f} SC.",
                view=None
            )
        else:
            await interaction.response.edit_message(
                content=f"You do not have enough Social Credits to claim this land. You need {self.land_price} SC, but you only have {current_credit:.2f} SC.",
                view=None
            )
        self.stop()
