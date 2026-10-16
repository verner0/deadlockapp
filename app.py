from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
import random
import json
import os
import re
import ssl
import time
import secrets
import urllib.error
import urllib.request

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)

# Central spiltilstand baseret på din Deadlock/Underlords randomizer-logikkæde
GAME_STATE = {
    "phase": "lobby",
    "players": {},
    "items_per_player": 6,
    "banned_heroes": [],
    "banned_items": [],
    "banned_categories": [],
    "enabled_tiers": [1, 2, 3, 4, 5],
    "slot_tiers": {str(i): [1, 2, 3, 4, 5] for i in range(6)},
    "version": 0
}

def bump_state():
    GAME_STATE["version"] += 1

# Hero icons: exact file names on the images.deadlocked.gg CDN (they differ from the hero names).
HERO_ICON_BASE = "https://assets.deadlock-api.com/images/heroes"
HERO_ICON_FILES = {
    "Abrams": "bull_sm", "Apollo": "fencer_sm", "Baba": "baba_sm", "Bebop": "bebop_sm",
    "Billy": "punkgoat_sm", "Calico": "nano_sm", "Celeste": "unicorn_sm", "Deadman Danny": "deadpack_sm",
    "Drifter": "drifter_sm", "Dynamo": "sumo_sm", "Graves": "necro_sm", "Grey Talon": "archer_sm",
    "Haze": "haze_sm", "Holliday": "astro_sm", "Infernus": "inferno_sm", "Ivy": "tengu_sm",
    "Kelvin": "kelvin_sm", "Lady Geist": "spectre_sm", "Lash": "lash_sm", "McGinnis": "engineer_sm",
    "Mina": "vampirebat_sm", "Mirage": "mirage_sm", "Mo & Krill": "digger_sm", "Paige": "bookworm_sm",
    "Paradox": "chrono_sm", "Pocket": "synth_sm", "Rat King": "ratking_sm", "Rem": "familiar_sm",
    "Seven": "gigawatt_sm", "Shiv": "shiv_sm", "Silver": "werewolf_sm", "Sinclair": "magician_sm",
    "Solomon": "chessmaster_sm", "The Doorman": "doorman_sm", "Venator": "priest_sm", "Victor": "frank_sm",
    "Vindicta": "hornet_sm", "Viscous": "viscous_sm", "Vyper": "kali_sm", "Warden": "warden_sm",
    "Wraith": "wraith_sm", "Yamato": "yamato_sm",
}
# Use Deadlocked.gg's actual small hero-icon filenames (e.g. nano_sm.webp).
FALLBACK_HEROES = {
    name: f"{HERO_ICON_BASE}/{file_name.removesuffix('_sm')}_card.png"
    for name, file_name in sorted(HERO_ICON_FILES.items())
}
# Announced heroes without a known icon yet (shown greyed out without a picture)
FALLBACK_HEROES["Nurse Harrow"] = ""
FALLBACK_HEROES["Violet"] = ""

# Heroes announced but not playable yet: shown greyed out, never assigned, cannot be banned.
# Remove a name from this set once the hero is released.
KNOWN_UPCOMING_HEROES = {"Nurse Harrow", "Violet"}

# Complete shop item list (156 items) used when the live API cannot be reached.
FALLBACK_ITEM_NAMES = {
    "weapon": {
        1: ["Close Quarters", "Extended Magazine", "Headshot Booster", "High-Velocity Rounds",
            "Monster Rounds", "Rapid Rounds", "Restorative Shot"],
        2: ["Active Reload", "Fleetfoot", "Intensifying Magazine", "Kinetic Dash", "Long Range",
            "Melee Charge", "Mystic Shot", "Opening Rounds", "Recharging Rush", "Slowing Bullets",
            "Spirit Shredder Bullets", "Split Shot", "Stalker", "Swift Striker", "Titanic Magazine",
            "Weakening Headshot"],
        3: ["Alchemical Fire", "Ballistic Enchantment", "Berserker", "Blood Tribute", "Burst Fire",
            "Cultist Sacrifice", "Escalating Resilience", "Express Shot", "Headhunter", "Heroic Aura",
            "Hollow Point", "Hunter's Aura", "Point Blank", "Shadow Weave", "Sharpshooter",
            "Spirit Rend", "Tesla Bullets", "Toxic Bullets", "Weighted Shots"],
        4: ["Armor Piercing Rounds", "Capacitor", "Crippling Headshot", "Crushing Fists", "Frenzy",
            "Glass Cannon", "Lucky Shot", "Ricochet", "Silencer", "Spellslinger", "Spiritual Overflow"],
    },
    "vitality": {
        1: ["Extra Health", "Extra Regen", "Extra Stamina", "Grit", "Healing Rite", "Melee Lifesteal",
            "Rebuttal", "Sprint Boots"],
        2: ["Battle Vest", "Bullet Lifesteal", "Debuff Reducer", "Enchanter's Emblem", "Enduring Speed",
            "Guardian Ward", "Healbane", "Healing Booster", "Reactive Barrier", "Restorative Locket",
            "Return Fire", "Spirit Lifesteal", "Spirit Shielding", "Trophy Collector", "Weapon Shielding"],
        3: ["Bullet Resilience", "Counterspell", "Dispel Magic", "Fortitude", "Fury Trance",
            "Healing Nova", "Lifestrike", "Majestic Leap", "Metal Skin", "Rescue Beam",
            "Spirit Resilience", "Stamina Mastery", "Veil Walker", "Warp Stone"],
        4: ["Cheat Death", "Colossus", "Divine Barrier", "Diviner's Kevlar", "Healing Tempo",
            "Indomitable", "Infuser", "Inhibitor", "Juggernaut", "Leech", "Phantom Strike",
            "Plated Armor", "Siphon Bullets", "Spellbreaker", "Unstoppable", "Vampiric Burst", "Witchmail"],
    },
    "spirit": {
        1: ["Extra Charge", "Extra Spirit", "Golden Goose Egg", "Mystic Burst", "Mystic Expansion",
            "Mystic Regeneration", "Rusted Barrel", "Spirit Strike"],
        2: ["Arcane Surge", "Bullet Resist Shredder", "Cold Front", "Compress Cooldown",
            "Duration Extender", "Improved Spirit", "Mystic Slow", "Mystic Vulnerability",
            "Quicksilver Reload", "Slowing Hex", "Spirit Sap", "Suppressor"],
        3: ["Decay", "Disarming Hex", "Greater Expansion", "Knockdown", "Radiant Regeneration",
            "Rapid Recharge", "Silence Wave", "Spirit Snatch", "Superior Cooldown", "Superior Duration",
            "Surge of Power", "Tankbuster", "Torment Pulse"],
        4: ["Arctic Blast", "Boundless Spirit", "Cursed Relic", "Echo Shard", "Escalating Exposure",
            "Ethereal Shift", "Focus Lens", "Lightning Scroll", "Magic Carpet", "Mercurial Magnum",
            "Mystic Reverb", "Refresher", "Scourge", "Spirit Burn", "Transcendent Cooldown", "Vortex Web"],
    },
}

# Item icon file names that differ from the item name (exact names from images.deadlocked.gg).
ITEM_ICON_FILE_OVERRIDES = {
    "Extended Magazine": "basic_magazine", "Recharging Rush": "recharging_rounds", "Stalker": "backstabber",
    "Ballistic Enchantment": "alchemical_seal", "Sharpshooter": "sharp_shooter",
    "Spirit Rend": "spellslinger_headshots", "Spellslinger": "spell_slinger", "Dispel Magic": "debuff_remover",
    "Golden Goose Egg": "goose_egg", "Mystic Expansion": "mystic_reach", "Mystic Regeneration": "mystic_regen",
    "Compress Cooldown": "improved_cooldown", "Silence Wave": "silence_glyph", "Cursed Relic": "curse",
    # Tier 5 / Legendary items: explicit slugs keep their icons on the same
    # assets-bucket CDN used by the rest of the randomizer's item pool.
    "Haunting Shot": "haunting_shot", "Infinite Rounds": "infinite_rounds",
    "Runed Gauntlets": "runed_gauntlets", "Celestial Blessing": "celestial_blessing",
    "Cloak of Opportunity": "cloak_of_opportunity", "Electric Slippers": "electric_slippers",
    "Eternal Gift": "eternal_gift", "Nullification Burst": "nullification_burst",
    "Seraphim Wings": "seraphim_wings", "Shadow Strike": "shadow_strike",
    "Frostbite Charm": "frostbite_charm", "Mystic Conduit": "mystic_conduit",
    "Mystical Piano": "mystical_piano", "Omnicharge Signet": "omnicharge_signet",
    "Prism Blast": "prism_blast", "Shrink Ray": "shrink_ray",
    "Unstable Concoction": "unstable_concoction",
}


def guess_item_icon(category, name):
    slug = ITEM_ICON_FILE_OVERRIDES.get(name) or re.sub(
        r"[^a-z0-9]+", "_", name.lower().replace("'", "")
    ).strip("_")
    return f"https://assets-bucket.deadlock-api.com/assets-api-res/images/items/{category}/{slug}.webp"


# Street Brawl's 17 Legendary (Tier 5) items. They are not always present in
# the normal shop-upgrade API endpoint, so explicitly include them in the pool.
LEGENDARY_ITEM_NAMES = {
    "weapon": ["Haunting Shot", "Infinite Rounds", "Runed Gauntlets"],
    "vitality": ["Celestial Blessing", "Cloak of Opportunity", "Electric Slippers",
                 "Eternal Gift", "Nullification Burst", "Seraphim Wings", "Shadow Strike"],
    "spirit": ["Frostbite Charm", "Mystic Conduit", "Mystical Piano", "Omnicharge Signet",
               "Prism Blast", "Shrink Ray", "Unstable Concoction"],
}

FALLBACK_ITEM_NAMES = {
    category: {**tiers, 5: LEGENDARY_ITEM_NAMES[category]}
    for category, tiers in FALLBACK_ITEM_NAMES.items()
}

FALLBACK_ITEM_CATEGORIES = {
    category: {
        name: {"img": guess_item_icon(category, name), "tier": tier}
        for tier, names in tiers.items()
        for name in names
    }
    for category, tiers in FALLBACK_ITEM_NAMES.items()
}


def add_legendary_items(categories):
    """Ensure all 17 Street Brawl Legendary items are in the selectable pool."""
    categories = {category: dict(categories.get(category, {})) for category in ("weapon", "vitality", "spirit")}
    for category, names in LEGENDARY_ITEM_NAMES.items():
        for name in names:
            # Preserve live API image data when present; otherwise use the existing item CDN.
            if name not in categories[category]:
                categories[category][name] = {"img": guess_item_icon(category, name), "tier": 5}
            else:
                categories[category][name]["tier"] = 5
                current_icon = categories[category][name].get("img")
                # Keep a valid live API image when present; otherwise use the
                # established item CDN with an explicit Legendary slug.
                if not isinstance(current_icon, str) or not current_icon.strip():
                    categories[category][name]["img"] = guess_item_icon(category, name)
        categories[category] = dict(sorted(categories[category].items(), key=lambda pair: (pair[1].get("tier", 1), pair[0])))
    return categories

# ---------------------------------------------------------------------------
# Live data loading: heroes and items (with icons) come from the Deadlock asset API.
# Order of sources: live API -> local cache file -> built-in fallback lists above.
# ---------------------------------------------------------------------------
# Can be overridden without editing the code, e.g. set DEADLOCK_ASSETS_API=https://other-host
API_BASE = os.environ.get("DEADLOCK_ASSETS_API", "https://assets.deadlock-api.com").rstrip("/")
API_PATHS = {
    "heroes": ["/v2/heroes", "/v2/heroes?only_active=true"],
    "items": ["/v2/items/by-type/upgrade", "/v2/items"],
}
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deadlock_data_cache.json")
ITEM_SLOT_ALIASES = {
    "weapon": "weapon",
    "vitality": "vitality",
    "armor": "vitality",
    "spirit": "spirit",
    "tech": "spirit",
}
HERO_IMAGE_KEYS = ["icon_hero_card_webp", "icon_image_small", "icon_hero_card", "hero_card", "hero_card_image", "selection_image", "top_bar_vertical_image", "top_bar_image", "minimap_image", "portrait", "portrait_image", "image_webp", "image"]
ITEM_IMAGE_KEYS = ["image_webp", "shop_image_small", "shop_image", "image"]

# These containers are mutated in place so every reference keeps pointing at the live data.
HEROES = {}
UNRELEASED_HEROES = set()
ITEM_CATEGORIES = {"weapon": {}, "vitality": {}, "spirit": {}}
ALL_ITEMS = {}
DATA_SOURCE = {"name": "fallback"}
LOAD_LOG = []


def log_step(message):
    """Print a diagnostic line and keep the latest ones for the /api/debug page."""
    print(f"[data] {message}")
    LOAD_LOG.append(message)
    del LOAD_LOG[:-30]


def build_ssl_context():
    try:
        import certifi  # optional; fixes missing CA bundles on some Python installs
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def describe_error(error):
    if isinstance(error, urllib.error.HTTPError):
        return f"HTTP {error.code} {error.reason}"
    reason = getattr(error, "reason", error)
    if isinstance(reason, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(reason):
        return (f"SSL certificate error ({reason}). Try 'pip install certifi' "
                "(on macOS also run 'Install Certificates.command' for your Python version)")
    return f"{type(error).__name__}: {error}"


def fetch_json(path, timeout=15):
    request_obj = urllib.request.Request(
        API_BASE + path,
        headers={"User-Agent": "Mozilla/5.0 (compatible; deadlock-randomizer/1.0)", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request_obj, timeout=timeout, context=build_ssl_context()) as response:
        return json.loads(response.read().decode("utf-8"))


def first_image(entry, keys):
    """Return a likely hero/item image URL from the API's varying image schemas."""
    images = entry.get("images") if isinstance(entry.get("images"), dict) else {}
    sources = (images, entry)
    for source in sources:
        for key in keys:
            value = source.get(key) if isinstance(source, dict) else None
            if isinstance(value, dict):
                value = value.get("url") or value.get("webp") or value.get("png") or value.get("src")
            if isinstance(value, str) and value.strip():
                value = value.strip()
                if value.startswith(("http://", "https://")):
                    return value
                if value.startswith("/"):
                    return "https://assets-bucket.deadlock-api.com" + value
    # API versions may place images deeper in a nested object, or use new field names.
    for source in sources:
        if not isinstance(source, dict):
            continue
        for key, value in source.items():
            key_lower = str(key).lower()
            if not any(token in key_lower for token in ("image", "icon", "portrait", "card")):
                continue
            if isinstance(value, dict):
                value = value.get("url") or value.get("webp") or value.get("png") or value.get("src")
            if isinstance(value, str) and value.strip():
                value = value.strip()
                if value.startswith(("http://", "https://")):
                    return value
                if value.startswith("/"):
                    return "https://assets-bucket.deadlock-api.com" + value
    return ""

def parse_heroes(raw_heroes):
    """Convert the raw hero list into {name: icon_url}. Test/disabled heroes are skipped;
    announced-but-unreleased heroes (KNOWN_UPCOMING_HEROES) are kept so they can be shown greyed out."""
    result = {}
    for hero in raw_heroes or []:
        if not isinstance(hero, dict) or hero.get("disabled"):
            continue
        name = hero.get("name")
        if not name:
            continue
        not_playable = hero.get("in_development") or hero.get("player_selectable") is False
        if not_playable and name not in KNOWN_UPCOMING_HEROES:
            continue
        result[name] = first_image(hero, HERO_IMAGE_KEYS) or FALLBACK_HEROES.get(name, "")
    return dict(sorted(result.items()))


def parse_items(raw_items):
    """Convert the raw item list into {category: {name: {img, tier}}} for shop upgrades only."""
    categories = {"weapon": {}, "vitality": {}, "spirit": {}}
    for item in raw_items or []:
        if not isinstance(item, dict) or item.get("disabled"):
            continue
        if item.get("type") not in (None, "upgrade") or item.get("shopable") is False:
            continue
        raw_slot = str(item.get("item_slot_type") or item.get("shop_the_tab") or item.get("category") or "").lower()
        category = ITEM_SLOT_ALIASES.get(raw_slot)
        if not category:
            if "weapon" in raw_slot:
                category = "weapon"
            elif "vitality" in raw_slot or "armor" in raw_slot:
                category = "vitality"
            elif "spirit" in raw_slot or "tech" in raw_slot:
                category = "spirit"
        name = item.get("name")
        if not category or not name:
            continue
        tier_value = item.get("item_tier")
        if isinstance(tier_value, str):
            digits = "".join(ch for ch in tier_value if ch.isdigit())
            tier_value = int(digits) if digits else None
        try:
            tier = int(tier_value) if tier_value else 1
        except (TypeError, ValueError):
            tier = 1
        if tier not in (1, 2, 3, 4, 5):
            tier = 1
        categories[category][name] = {"img": first_image(item, ITEM_IMAGE_KEYS) or guess_item_icon(category, name), "tier": tier}
    for category in categories:
        categories[category] = dict(
            sorted(categories[category].items(), key=lambda pair: (pair[1]["tier"], pair[0]))
        )
    return categories


def fetch_first_working(paths, parser, label):
    """Try each endpoint in turn and return the first parse result that contains data."""
    for path in paths:
        try:
            raw = fetch_json(path)
            if isinstance(raw, dict):
                raw = raw.get("items") or raw.get("heroes") or raw.get("data") or []
            parsed = parser(raw)
            count = sum(len(v) for v in parsed.values()) if label == "items" else len(parsed)
            log_step(f"{label}: {path} -> {len(raw)} raw entries, {count} usable")
            if raw and not count and isinstance(raw[0], dict):
                log_step(f"{label}: nothing usable; first entry keys: {sorted(raw[0])[:25]}")
            if count:
                return parsed
        except Exception as error:
            log_step(f"{label}: {path} failed: {describe_error(error)}")
    return None


def apply_game_data(heroes, categories, source_name):
    HEROES.clear()
    HEROES.update(heroes)
    # Upcoming heroes must always be listed (greyed out), even if the source lacks them.
    for name in KNOWN_UPCOMING_HEROES:
        if not HEROES.get(name):
            HEROES[name] = FALLBACK_HEROES.get(name, "")
    UNRELEASED_HEROES.clear()
    UNRELEASED_HEROES.update(KNOWN_UPCOMING_HEROES)
    for category in ITEM_CATEGORIES:
        ITEM_CATEGORIES[category].clear()
        ITEM_CATEGORIES[category].update(categories.get(category, {}))
    ALL_ITEMS.clear()
    for category, items in ITEM_CATEGORIES.items():
        for name, data in items.items():
            ALL_ITEMS[name] = {"category": category, "img": data["img"], "tier": data["tier"]}
    DATA_SOURCE["name"] = source_name


def load_game_data(force_refresh=False):
    """Load heroes/items. Returns the source used: 'api', 'cache' or 'fallback'."""
    if not force_refresh and HEROES and ALL_ITEMS and DATA_SOURCE["name"] == "api":
        return "api"
    del LOAD_LOG[:]
    heroes = fetch_first_working(API_PATHS["heroes"], parse_heroes, "heroes")
    categories = fetch_first_working(API_PATHS["items"], parse_items, "items")
    if heroes and categories:
        categories = add_legendary_items(categories)
        apply_game_data(heroes, categories, "api")
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as cache_handle:
                json.dump({"heroes": heroes, "categories": categories}, cache_handle)
        except OSError as error:
            log_step(f"could not write cache: {error}")
        return "api"
    log_step("API data incomplete - trying cache, then built-in lists")
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as cache_handle:
            cached = json.load(cache_handle)
        if cached.get("heroes") and cached.get("categories"):
            cached_categories = add_legendary_items(cached["categories"])
            apply_game_data(cached["heroes"], cached_categories, "cache")
            return "cache"
    except Exception as error:
        log_step(f"cache not usable: {describe_error(error)}")
    apply_game_data(FALLBACK_HEROES, FALLBACK_ITEM_CATEGORIES, "fallback")
    return "fallback"


load_game_data()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="da">
<head>
    <meta charset="UTF-8">
    <title>Deadlock Item Randomizer</title>
    <style>
        body { background: #12141a; color: #e8eaf0; font-family: 'Segoe UI', Tahoma, sans-serif; margin: 0; padding: 20px; }
        .layout { display: flex; gap: 20px; max-width: 1450px; margin: 0 auto; }
        .main-content { flex: 1; background: #1a1d26; padding: 25px; border-radius: 12px; border: 1px solid #2a2f40; }
        .sidebar { width: 380px; background: #1a1d26; padding: 20px; border-radius: 12px; border: 1px solid #2a2f40; max-height: 90vh; overflow-y: auto; }
        
        h1, h2, h3 { color: #e3a93b; text-shadow: 0 2px 4px rgba(0,0,0,0.5); }
        .card { background: #222634; padding: 18px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #5d6478; }
        .btn { background: #e3a93b; color: #1a1306; border: none; padding: 8px 14px; font-weight: bold; border-radius: 6px; cursor: pointer; text-decoration: none; display: inline-block; transition: 0.2s; font-size: 13px; }
        .btn:hover { background: #c18f2c; transform: translateY(-1px); }
        .btn-sec { background: #2a2f40; color: #e8eaf0; border: 1px solid #5d6478; }
        .btn-danger { background: #c06c6c; color: #fff; }
        .btn-success { background: #6cc070; color: #1a1306; }
        .btn:disabled { opacity: 0.4; cursor: not-allowed; }
        
        .slot-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; margin-top: 15px; }
        .slot-card { background: #12141a; padding: 12px; border-radius: 8px; border: 2px solid #3b4259; position: relative; }
        .slot-card.locked { border-color: #6cc070; background: #161f18; }
        .slot-card.result-flash { animation: itemResultPulse 1.8s ease-out 1; border-color: #e3a93b !important; }
        @keyframes itemResultPulse { 0% { box-shadow: 0 0 0 0 rgba(227,169,59,.95); transform: scale(1.025); background:#4a3a1d; } 45% { box-shadow: 0 0 22px 5px rgba(227,169,59,.45); } 100% { box-shadow: 0 0 0 0 rgba(227,169,59,0); transform: scale(1); } }
        .action-result { animation: actionResultPulse 1.7s ease-out 1; }
        @keyframes actionResultPulse { 0% { background:#4a3a1d; } 100% { background:#2a2f40; } }
        
        .hero-img { width: 64px; height: 64px; border-radius: 50%; border: 2px solid #e3a93b; object-fit: cover; background: #000; }
        .item-img { width: 32px; height: 32px; border-radius: 4px; object-fit: cover; background: #111; vertical-align: middle; }
        
        .badge { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; }
        .cat-weapon { background: #e8923d; color: #fff; }
        .cat-vitality { background: #6cc070; color: #1a1306; }
        .cat-spirit { background: #b585f2; color: #1a1306; }
        .badge-legendary { background: #f39c12; color: #fff; font-weight: bold; }
        
        .ban-chip { display: inline-flex; align-items: center; gap: 6px; padding: 4px 8px; background: #2a1a1a; border: 1px solid #c06c6c; border-radius: 4px; margin: 3px; font-size: 12px; color: #ff8888; }
        .ban-chip a { color: #ff4444; text-decoration: none; font-weight: bold; cursor: pointer; }
        
        .item-list-mini { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
        .item-chip { display: flex; align-items: center; gap: 6px; background: #12141a; padding: 4px 8px; border-radius: 4px; font-size: 11px; border: 1px solid #3b4259; }
        .item-chip.banned { opacity: 0.3; text-decoration: line-through; border-color: #c06c6c; }
        .item-chip.unreleased { opacity: 0.45; filter: grayscale(1); border-style: dashed; cursor: not-allowed; }
        .item-chip.unreleased .hero-mini { filter: grayscale(1); }
        .hero-mini { width: 22px; height: 22px; border-radius: 50%; object-fit: cover; background: #000; border: 1px solid #5d6478; }
        
        /* True Random Reel Overlay Styling */
        #reel-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 999; justify-content: center; align-items: center; }
        .reel-box { background: #1a1d26; padding: 30px; border-radius: 12px; border: 2px solid #e3a93b; text-align: center; width: 500px; box-shadow: 0 10px 30px rgba(0,0,0,0.8); }
        .reel-window { display: flex; justify-content: center; gap: 15px; margin: 20px 0; background: #12141a; padding: 15px; border-radius: 8px; }
        .reel-slot { width: 120px; height: 110px; background: #222634; border-radius: 6px; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 8px; }
        .reel-slot.highlight { border: 2px solid #6cc070; background: #2a2f40; }
    </style>
    <script>
        let currentVersion = {{ state_version }};
        let isSpinning = false;
        const failedImageUrls = new Set();
        // Short, subtle case-opening ticks using Web Audio (no external sound files needed).
        let tickAudioContext = null;
        function playCaseTick() {
            try {
                tickAudioContext = tickAudioContext || new (window.AudioContext || window.webkitAudioContext)();
                if (tickAudioContext.state === 'suspended') tickAudioContext.resume();
                const osc = tickAudioContext.createOscillator();
                const gain = tickAudioContext.createGain();
                osc.type = 'square'; osc.frequency.value = 850 + Math.random() * 450;
                gain.gain.setValueAtTime(0.035, tickAudioContext.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, tickAudioContext.currentTime + 0.035);
                osc.connect(gain); gain.connect(tickAudioContext.destination);
                osc.start(); osc.stop(tickAudioContext.currentTime + 0.04);
            } catch (e) { /* Sound is optional if browser audio is unavailable. */ }
        }
        function setReelImage(id, url) {
            const img = document.getElementById(id);
            if (!url || failedImageUrls.has(url)) { img.style.display = "none"; return; }
            if (img.dataset.currentSrc === url) return;
            img.dataset.currentSrc = url; img.style.display = "inline-block"; img.src = url;
        }

        // Auto-Sync Polling (Sørg for at modstanderen opdaterer uden manuel genindlæsning)
        setInterval(async () => {
            if (isSpinning) return;
            try {
                const response = await fetch('/api/state');
                const data = await response.json();
                if (data.version !== currentVersion) {
                    window.location.reload();
                }
            } catch (err) {}
        }, 1500);

        // Ægte True Random Reel Roulette-animation overført direkte fra desktop-scriptet
        function startTrueRandomReel(slotIdx, event) {
            event.preventDefault();
            isSpinning = true;
            
            const overlay = document.getElementById('reel-overlay');
            overlay.style.display = 'flex';
            
            const itemsObj = {{ active_items_dict_json | safe }};
            const enabledTiers = new Set({{ enabled_tiers | tojson }});
            const slotTierMap = {{ slot_tiers | tojson }};
            const slotAllowed = new Set((slotTierMap[String(slotIdx)] || [1,2,3,4,5]).map(Number).filter(t => enabledTiers.has(t)));
            const itemKeys = Object.keys(itemsObj).filter(name => slotAllowed.has(Number(itemsObj[name].tier || 1)));
            
            if (itemKeys.length === 0) {
                alert("Item-puljen er tom! Fjern nogle bans.");
                overlay.style.display = 'none';
                isSpinning = false;
                return;
            }

            let counter = 0;
            const maxSpins = 22;
            let delay = 40;
            
            function stepReel() {
                // Vælg 3 tilfældige visuelle elementer til rouletten (venstre, midt, højre)
                const leftItem = itemKeys[Math.floor(Math.random() * itemKeys.length)];
                const midItem = (counter >= maxSpins) ? window.finalChosenItem : itemKeys[Math.floor(Math.random() * itemKeys.length)];
                const rightItem = itemKeys[Math.floor(Math.random() * itemKeys.length)];
                
                document.getElementById('reel-left-name').innerText = leftItem;
                setReelImage('reel-left-img', itemsObj[leftItem].img);
                
                document.getElementById('reel-mid-name').innerText = midItem;
                setReelImage('reel-mid-img', itemsObj[midItem].img);
                
                document.getElementById('reel-right-name').innerText = rightItem;
                setReelImage('reel-right-img', itemsObj[rightItem].img);

                playCaseTick();
                counter++;
                if (counter <= maxSpins) {
                    delay = 40 + Math.pow(counter / maxSpins, 2.5) * 350;
                    setTimeout(stepReel, delay);
                } else {
                    // Færdig! Send forespørgsel til serveren for at gemme det endelige valg
                    setTimeout(() => {
                        window.location.href = "/spin/" + slotIdx + "?item=" + encodeURIComponent(window.finalChosenItem);
                    }, 800);
                }
            }

            // Hent først det rigtige item fra serveren via et hurtigt API-kald, så rouletten lander præcist på det
            fetch('/api/roll_item?slot=' + encodeURIComponent(slotIdx))
                .then(res => {
                    if (!res.ok) throw new Error('Kunne ikke hente et item');
                    return res.json();
                })
                .then(data => {
                    if (!data.item_name || !itemsObj[data.item_name]) throw new Error('Ugyldigt item');
                    window.finalChosenItem = data.item_name;
                    stepReel();
                })
                .catch(() => {
                    alert('Kunne ikke hente et item. Prøv igen.');
                    overlay.style.display = 'none';
                    isSpinning = false;
                });
        }
    </script>
</head>
<body>
    <!-- ROULETTE REEL OVERLAY -->
    <div id="reel-overlay">
        <div class="reel-box">
            <h3 style="color: #e3a93b; margin-top:0;">🎲 TRUE RANDOM REEL // SHOWCASE</h3>
            
            <div class="reel-window">
                <div class="reel-slot">
                    <img id="reel-left-img" class="item-img" alt="Itemikon" onerror="failedImageUrls.add(this.src);this.style.display='none';" style="width:40px;height:40px;margin-bottom:6px;">
                    <span id="reel-left-name" style="font-size: 11px; color:#aaa;">-</span>
                </div>
                <div class="reel-slot highlight">
                    <span style="font-size: 9px; color: #6cc070; font-weight: bold; margin-bottom: 2px;">▼ VINDER ▼</span>
                    <img id="reel-mid-img" class="item-img" alt="Itemikon" onerror="failedImageUrls.add(this.src);this.style.display='none';" style="width:40px;height:40px;margin-bottom:4px;">
                    <span id="reel-mid-name" style="font-size: 12px; font-weight: bold; color:#fff;">-</span>
                </div>
                <div class="reel-slot">
                    <img id="reel-right-img" class="item-img" alt="Itemikon" onerror="failedImageUrls.add(this.src);this.style.display='none';" style="width:40px;height:40px;margin-bottom:6px;">
                    <span id="reel-right-name" style="font-size: 11px; color:#aaa;">-</span>
                </div>
            </div>
            
        </div>
    </div>

    <div class="layout">
        <!-- HOVEDOMRÅDE (GAMEBOARD & LOBBY) -->
        <div class="main-content">
            <h1>DEADLOCK ITEM RANDOMIZER</h1>
            
            {% if status_msg %}
                <div class="action-result" style="background: #2a2f40; border: 1px solid #e3a93b; color: #e3a93b; padding: 10px; border-radius: 6px; margin-bottom: 20px; font-weight: bold;">
                    🔔 {{ status_msg }}
                </div>
            {% endif %}

            {% if phase == 'lobby' %}
                <div class="card">
                    <h3>🎮 Spillere & Lobby</h3>
                    <p>Tilsluttede deltagere:</p>
                    <p style="font-size: 12px; color: #8c93a8; border-left: 3px solid #e3a93b; padding-left: 10px;">
                        <strong>Sådan spiller I sammen:</strong> Alle spillere skal åbne præcis den samme serveradresse.
                        Kun én computer skal starte appen. Hvis hver spiller starter sin egen kopi, får I separate lobbyer.
                    </p>
                    <ul>
                        {% for name, data in players.items() %}
                            <li><strong>👤 {{ name }}</strong> {% if data.ready %}<span style="color: #6cc070;">✔️ Klar</span>{% else %}<span style="color: #e3a93b;">⏳ Venter...</span>{% endif %}</li>
                        {% endfor %}
                    </ul>
                    <br>
                    {% if not current_player %}
                        <form method="POST" action="/join">
                            <input type="text" name="player_name" placeholder="Indtast dit spiller-navn..." required style="padding: 8px; width: 60%; background: #12141a; border: 1px solid #5d6478; color: #fff; border-radius: 4px;">
                            <button type="submit" class="btn">Deltag i spillet</button>
                        </form>
                    {% else %}
                        <p>Du er logget ind som: <strong style="color: #e3a93b;">👤 {{ current_player }}</strong></p>
                        {% if not player_data.ready %}
                            <form method="POST" action="/ready">
                                <button type="submit" class="btn btn-success" style="font-size: 15px; padding: 10px 20px;">✅ Bliv Klar (Ready)</button>
                            </form>
                        {% else %}
                            <p style="color: #6cc070; font-weight: bold;">Du er klar! Venter på modstanderen...</p>
                        {% endif %}
                    {% endif %}
                </div>

                <!-- BANNING & UPDATE MANAGER -->
                <div class="card">
                    <h3>🚫 Ban- og Opdateringsindstillinger</h3>
                    <p><strong>Fravælg Item-kategorier:</strong></p>
                    <form method="POST" action="/ban/category" style="display: flex; gap: 10px; flex-wrap: wrap;">
                        {% for cat in ['weapon', 'vitality', 'spirit'] %}
                            <button type="submit" name="category" value="{{ cat }}" class="btn {% if cat in banned_categories %}btn-danger{% else %}btn-sec{% endif %}">
                                {% if cat in banned_categories %}🚫 {{ cat.capitalize() }} (Banned){% else %}✅ Include {{ cat.capitalize() }}{% endif %}
                            </button>
                        {% endfor %}
                    </form>
                    
                    <br>
                    <p><strong>Aktive Bannede Helte/Items:</strong></p>
                    <div>
                        {% for h in banned_heroes %}
                            <span class="ban-chip">👤 {{ h }} <form method="POST" action="/unban/hero/{{ h }}" style="display:inline;"><button type="submit" aria-label="Unban {{ h }}" style="background:none;border:0;color:#ff4444;font-weight:bold;cursor:pointer;">✕</button></form></span>
                        {% endfor %}
                        {% for item in banned_items %}
                            <span class="ban-chip">🎒 {{ item }} <form method="POST" action="/unban/item/{{ item }}" style="display:inline;"><button type="submit" aria-label="Unban {{ item }}" style="background:none;border:0;color:#ff4444;font-weight:bold;cursor:pointer;">✕</button></form></span>
                        {% endfor %}
                        {% if not banned_heroes and not banned_items %}
                            <em style="color: #888; font-size: 13px;">Ingen specifikke bans aktive. Klik i sidebaren for at banne elementer.</em>
                        {% endif %}
                    </div>
                </div>

            {% elif phase == 'draft' %}
                <div class="card">
                    <h2>Velkommen, {{ current_player }}!</h2>
                    <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 20px; padding: 12px; background:#12141a; border:1px solid #3b4259; border-radius:10px;">
                        {% if player_data['hero_img'] or fallback_heroes.get(player_data['hero']) %}<img src="{{ player_data['hero_img'] or fallback_heroes.get(player_data['hero']) }}" data-fallback="{{ fallback_heroes.get(player_data['hero'], '') }}" class="hero-img" alt="Portræt af {{ player_data['hero'] }}" style="width:88px;height:88px;flex-shrink:0;" onerror="if(this.dataset.fallback && this.src !== this.dataset.fallback){this.src=this.dataset.fallback;this.dataset.fallback='';}else{this.onerror=null;this.style.display='none';}">{% endif %}
                        <div style="margin-left: 0;">
                            <span style="font-size: 12px; color: #888;">Din Tildelte Karakter:</span><br>
                            <strong style="color: #e3a93b; font-size: 22px;">{{ player_data['hero'] }}</strong>
                        </div>
                    </div>
                    
                    <h3>🎒 Dine Item-Slots (True Random Reels):</h3>
                    <div class="slot-grid">
                        {% for i in range(player_data['items']|length) %}
                            <div class="slot-card {% if i in highlight_slots %}result-flash{% endif %}">
                                <div style="font-size: 11px; color: #888; margin-bottom: 4px;">SLOT #{{ i+1 }}{% if i in highlight_slots %} · SENEST ÆNDRET ✨{% endif %}</div>
                                <div id="slot-content-{{ i }}" style="display: flex; align-items: center; margin: 8px 0; min-height: 36px;">
                                    {% if player_data['items'][i] %}
                                        <img src="{{ all_items[player_data['items'][i]].img }}" class="item-img" alt="Item" onerror="this.onerror=null; this.style.display='none';">
                                        <span style="font-size: 13px; font-weight: bold; margin-left: 6px; color: {% if all_items[player_data['items'][i]].tier == 5 %}#f39c12{% else %}#e3a93b{% endif %};">
                                            {{ player_data['items'][i] }} {% if has_legendary and all_items[player_data['items'][i]].tier == 5 %}★[Leg]{% endif %}
                                        </span>
                                    {% else %}
                                        <em style="color: #777;">Tom slot</em>
                                    {% endif %}
                                </div>
                                {% if not player_data['items'][i] %}
                                    <a href="#" onclick="startTrueRandomReel({{ i }}, event)" class="btn" style="width: 100%; text-align: center; box-sizing: border-box;">🎬 Spin Item (Reel)</a>
                                {% endif %}
                            </div>
                        {% endfor %}
                    </div>

                    <br>
                    {% if all_items_chosen %}
                        {% if not player_data.ready %}
                            <form method="POST" action="/finish_draft">
                                <button type="submit" class="btn btn-success" style="width: 100%; font-size: 15px; padding: 12px;">🚀 Færdig med Draft - Gå til Action-fase</button>
                            </form>
                        {% else %}
                            <p style="color: #6cc070; text-align: center; font-weight: bold;">Du er klar! Venter på modstanderen...</p>
                        {% endif %}
                    {% endif %}
                </div>

            {% elif phase == 'actions' %}
                <div class="card">
                    <h2>⚡ Action-fase (Lås, Reroll & Modstander-tyveri)</h2>
                    
                    <!-- TRIN 1: LÅS -->
                    <div style="background: #161821; padding: 12px; border-radius: 6px; margin-bottom: 12px;">
                        <h4 style="margin: 0 0 8px 0; color: #e3a93b;">Trin 1: Lås et item (Beskyt mod tyveri)</h4>
                        <div class="slot-grid">
                            {% for i in range(player_data['items']|length) %}
                                <div class="slot-card {% if i in player_data['locked_slots'] %}locked{% endif %}">
                                    <div style="font-size: 11px; color: #888;">SLOT #{{ i+1 }}</div>
                                    <div style="display: flex; align-items: center; margin: 6px 0;">
                                        {% if player_data['items'][i] %}
                                            <img src="{{ all_items[player_data['items'][i]].img }}" class="item-img" alt="Item">
                                            <span style="font-size: 12px; margin-left: 6px;">{{ player_data['items'][i] }}</span>
                                        {% else %}
                                            <em style="color: #777;">Tomt slot</em>
                                        {% endif %}
                                    </div>
                                    <form method="POST" action="/action/lock">
                                        <input type="hidden" name="slot_idx" value="{{ i }}">
                                        <button type="submit" class="btn {% if i in player_data['locked_slots'] %}btn-success{% else %}btn-sec{% endif %}" style="width: 100%;" {% if not player_data['items'][i] %}disabled{% endif %}>
                                            {% if i in player_data['locked_slots'] %}Lås op 🔓{% else %}Lås fast 🔒{% endif %}
                                        </button>
                                    </form>
                                </div>
                            {% endfor %}
                        </div>
                    </div>

                    <!-- TRIN 2: REROLL -->
                    <div style="background: #161821; padding: 12px; border-radius: 6px; margin-bottom: 12px;">
                        <h4 style="margin: 0 0 8px 0; color: #e3a93b;">Trin 2: Reroll et item (1/1 brugt)</h4>
                        <div class="slot-grid">
                            {% for i in range(player_data['items']|length) %}
                                <div class="slot-card">
                                    <div style="font-size: 11px; color: #888;">SLOT #{{ i+1 }}</div>
                                    <div style="display: flex; align-items: center; margin: 6px 0;">
                                        {% if player_data['items'][i] %}
                                            <img src="{{ all_items[player_data['items'][i]].img }}" class="item-img" alt="Item">
                                            <span style="font-size: 12px; margin-left: 6px;">{{ player_data['items'][i] }}</span>
                                        {% else %}
                                            <em style="color: #777;">Tomt slot</em>
                                        {% endif %}
                                    </div>
                                    <form method="POST" action="/action/reroll">
                                        <input type="hidden" name="slot_idx" value="{{ i }}">
                                        <button type="submit" class="btn btn-sec" style="width: 100%;" {% if not player_data['items'][i] or player_data.has_rerolled or (i in player_data['locked_slots']) %}disabled{% endif %}>
                                            ♻️ Reroll
                                        </button>
                                    </form>
                                </div>
                            {% endfor %}
                        </div>
                    </div>

                    <!-- TRIN 3: BLINDT STJÆL / BYT -->
                    <div style="background: #161821; padding: 12px; border-radius: 6px;">
                        <h4 style="margin: 0 0 8px 0; color: #e3a93b;">Trin 3: Blindtyveri — vælg hvad du giver væk</h4>
                        <p style="font-size: 12px; color: #aeb4c5;">Du kan ikke se modstanderens items eller låse. Vælg et af dine egne ulåste items at give væk. Appen trækker tilfældigt én af modstanderens slots. Rammer du en låst slot, mister du dit tyveriforsøg. Ellers bytter I items.</p>
                        {% if not player_data.has_stolen %}
                            {% set give_slots = [] %}
                            {% for own_idx in range(player_data['items']|length) %}
                                {% if player_data['items'][own_idx] and own_idx not in player_data['locked_slots'] %}
                                    {% set _ = give_slots.append(own_idx) %}
                                {% endif %}
                            {% endfor %}
                            {% if give_slots %}
                                {% for name, p in players.items() %}
                                    {% if name != current_player %}
                                        <form method="POST" action="/action/steal" style="margin-top: 12px; padding: 10px; background: #12141a; border-radius: 6px;">
                                            <strong>Modstander: {{ name }}</strong>
                                            <p style="font-size: 12px; color: #8c93a8; margin: 5px 0;">Modstanderens slot vælges tilfældigt blandt de seks slots.</p>
                                            <label for="give-slot-{{ loop.index }}" style="font-size: 12px;">Dit item, du giver væk:</label>
                                            <input type="hidden" name="target_name" value="{{ name }}">
                                            <select id="give-slot-{{ loop.index }}" name="give_slot" required style="padding: 7px; max-width: 100%; background: #222634; color: #fff; border: 1px solid #5d6478; border-radius: 4px;">
                                                {% for own_idx in give_slots %}
                                                    <option value="{{ own_idx }}">Slot #{{ own_idx + 1 }} — {{ player_data['items'][own_idx] }}</option>
                                                {% endfor %}
                                            </select>
                                            <button type="submit" class="btn btn-danger" style="margin-left: 6px;">🎲 Prøv blindtyveri</button>
                                        </form>
                                    {% endif %}
                                {% endfor %}
                            {% else %}
                                <p style="color: #e3a93b;">Du har ingen ulåste items at give væk. Lås et item op først.</p>
                            {% endif %}
                        {% else %}
                            <p style="color: #6cc070;">✔️ Dit tyveriforsøg er brugt.</p>
                        {% endif %}
                    </div>

                    <br>
                    <div style="text-align: center;">
                        {% if not player_data.ready %}
                            <form method="POST" action="/finish_actions">
                                <button type="submit" class="btn btn-success" style="font-size: 15px; padding: 10px 20px;">✅ Jeg er færdig (Ready)</button>
                            </form>
                        {% else %}
                            <p style="color: #6cc070; font-weight: bold;">Du er klar! Venter på modstanderen...</p>
                        {% endif %}
                    </div>
                </div>

            {% elif phase == 'finished' %}
                <div class="card" style="text-align: center;">
                    <h2>🏆 Slutresultat & Opsummering</h2>
                    <div style="display: flex; justify-content: space-around; flex-wrap: wrap; gap: 20px; margin-top: 20px;">
                        {% for name, p in players.items() %}
                            <div style="background: #12141a; padding: 15px; border-radius: 8px; width: 340px; text-align: left; border: 1px solid #5d6478;">
                                <div style="display: flex; align-items: center; margin-bottom: 12px;">
                                    <img src="{{ p['hero_img'] or fallback_heroes.get(p['hero']) }}" data-fallback="{{ fallback_heroes.get(p['hero'], '') }}" class="hero-img" alt="Portræt af {{ p['hero'] }}" onerror="if(this.dataset.fallback && this.src !== this.dataset.fallback){this.src=this.dataset.fallback;this.dataset.fallback='';}else{this.onerror=null;this.style.display='none';}">
                                    <div style="margin-left: 10px;">
                                        <h3 style="margin: 0; color: #e3a93b;">{{ name }}</h3>
                                        <span>Hero: <strong>{{ p['hero'] }}</strong></span>
                                    </div>
                                </div>
                                <h4>Endelige Items:</h4>
                                <ul style="padding-left: 0; list-style: none;">
                                    {% for item in p['items'] %}
                                        <li style="padding: 4px 0; display: flex; align-items: center;">
                                            {% if item %}
                                                <img src="{{ all_items[item].img }}" class="item-img" alt="Item" onerror="this.onerror=null; this.style.display='none';"> 
                                                <span style="margin-left: 6px; font-size: 13px; color: {% if all_items[item].tier == 5 %}#f39c12{% else %}#e8eaf0{% endif %};">
                                                    {{ item }} {% if has_legendary and all_items[item].tier == 5 %}★[Leg]{% endif %}
                                                </span>
                                            {% else %}
                                                <em style="color: #777;">Tom slot</em>
                                            {% endif %}
                                        </li>
                                    {% endfor %}
                                </ul>
                            </div>
                        {% endfor %}
                    </div>
                    <br><br>
                    <form method="POST" action="/reset" onsubmit="return confirm('Er du sikker på, at du vil nulstille spillet for alle spillere?');" style="display:inline-block;">
                        <button type="submit" class="btn btn-danger" style="font-size: 15px; padding: 10px 20px;">🔄 Start Nyt Spil</button>
                    </form>
                </div>
            {% endif %}
        </div>

        <!-- SIDEBAR: AVAILABLE HEROES & ITEM POOL OVERVIEW (BANNED MANAGEMENT) -->
        <div class="sidebar">
            <h3 style="margin-top: 0;">👥 Heroes ({{ active_heroes | length }})</h3>
            <div style="font-size: 11px; color: #8c93a8; margin: -8px 0 10px 0;">
                Datakilde: {{ data_source }} · {{ all_items | length }} items
            </div>
            <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 20px;">
                {% for h, img in heroes_dict.items() %}
                    {% set is_banned = h in banned_heroes %}
                    {% set is_unreleased = h in unreleased_heroes %}
                    <div class="item-chip {% if is_unreleased %}unreleased{% elif is_banned %}banned{% endif %}" {% if is_unreleased %}title="Ikke udgivet endnu"{% endif %}>
                        {% if img %}<img src="{{ img }}" class="hero-mini" alt="Hero-ikon" onerror="this.onerror=null; this.style.display='none';">{% else %}<span aria-label="Hero-ikon">🦸</span>{% endif %}
                        {% if is_unreleased %}
                            <span>{{ h }} (kommer snart)</span>
                        {% elif phase == 'lobby' %}
                            {% if is_banned %}
                                <form method="POST" action="/unban/hero/{{ h }}" style="display:inline;"><button type="submit" style="background:none;border:0;padding:0;color:#888;cursor:pointer;">{{ h }} (Unban)</button></form>
                            {% else %}
                                <form method="POST" action="/ban/hero/{{ h }}" style="display:inline;"><button type="submit" style="background:none;border:0;padding:0;color:#fff;cursor:pointer;">{{ h }}</button></form>
                            {% endif %}
                        {% else %}
                            <span>{{ h }}</span>
                        {% endif %}
                    </div>
                {% endfor %}
            </div>

            <hr style="border-color: #3b4259;">

            {% if phase == 'lobby' %}
            <div class="card" style="padding:12px;">
                <h3 style="margin-top:0;">Tilpas item-puljen</h3>
                <p style="font-size:12px;color:#aab1c4;margin-top:-4px;">Vælg globale tiers og tiers pr. slot nedenfor. Klik derefter på et item i item-puljen for at slå det fra eller til. Grå/overstreget betyder, at itemet er udelukket.</p>
                <form method="POST" action="/pool_settings">
                    <strong style="font-size:13px;">Antal item-slots per spiller</strong>
                    <div style="margin:8px 0 14px;">
                      <select name="items_per_player" class="form-control" style="max-width:180px;padding:8px;background:#12141a;color:#eee;border:1px solid #3b4259;border-radius:6px;">
                        {% for count in range(1,13) %}<option value="{{ count }}" {% if count == items_per_player %}selected{% endif %}>{{ count }} item{% if count != 1 %}s{% endif %} per spiller</option>{% endfor %}
                      </select>
                      <p style="font-size:11px;color:#8c93a8;margin:5px 0 0;">Vælg hvor mange items hver spiller skal trække i draften (1–12).</p>
                    </div>
                    <strong style="font-size:13px;">Aktive tiers</strong>
                    <div style="display:flex;gap:10px;flex-wrap:wrap;margin:8px 0 12px;">
                    {% for tier in [1,2,3,4,5] %}
                      <label style="font-size:12px;"><input type="checkbox" name="enabled_tiers" value="{{ tier }}" {% if tier in enabled_tiers %}checked{% endif %}> {% if tier == 5 %}★ Legendary{% else %}Tier {{ tier }}{% endif %}</label>
                    {% endfor %}
                    </div>
                    <strong style="font-size:13px;">Tier-filter per slot</strong>
                    {% for slot_num in range(1, items_per_player + 1) %}
                      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:7px 0;">
                        <span style="min-width:54px;font-size:12px;">Slot #{{ slot_num }}</span>
                        {% for tier in [1,2,3,4,5] %}
                          <label style="font-size:11px;"><input type="checkbox" name="slot_{{ slot_num-1 }}_tiers" value="{{ tier }}" {% if tier in slot_tiers.get((slot_num-1)|string, [1,2,3,4,5]) %}checked{% endif %}> {% if tier == 5 %}Leg.{% else %}T{{ tier }}{% endif %}</label>
                        {% endfor %}
                      </div>
                    {% endfor %}
                    <button class="btn" type="submit" style="margin-top:8px;">Gem item-puljer</button>
                    <p style="font-size:11px;color:#8c93a8;margin-bottom:0;">Legendary er Tier 5. En slot bruger kun tiers, der både er slået til globalt og valgt for slotten.</p>
                </form>
            </div>
            {% endif %}
            <h3>🎒 Item-pulje{% if all_items.values()|selectattr('tier', 'equalto', 5)|list %} (inkl. Legendary){% endif %}</h3>
            {% for cat_name, cat_items in item_categories.items() %}
                <div style="margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <strong style="font-size: 13px; text-transform: capitalize;">{{ cat_name }} Items</strong>
                        <span class="badge cat-{{ cat_name }}">{{ cat_name.capitalize() }}</span>
                    </div>
                    <div class="item-list-mini">
                        {% for item_name, data in cat_items.items() if data.tier != 5 %}
                            {% set is_banned = item_name in banned_items or cat_name in banned_categories %}
                            <div class="item-chip {% if is_banned %}banned{% endif %}">
                                <img src="{{ data.img }}" class="item-img" style="width: 18px; height: 18px;" alt="Item-ikon" onerror="this.onerror=null; this.style.display='none';">
                                {% if phase == 'lobby' %}
                                    {% if is_banned and item_name in banned_items %}
                                        <form method="POST" action="/unban/item/{{ item_name }}" style="display:inline;"><button type="submit" style="background:none;border:0;padding:0;color:#888;cursor:pointer;">{{ item_name }}</button></form>
                                    {% else %}
                                        <form method="POST" action="/ban/item/{{ item_name }}" style="display:inline;"><button type="submit" style="background:none;border:0;padding:0;color:#eee;cursor:pointer;">{{ item_name }} {% if has_legendary and data.tier == 5 %}★{% endif %}</button></form>
                                    {% endif %}
                                {% else %}
                                    <span>{{ item_name }} {% if has_legendary and data.tier == 5 %}★{% endif %}</span>
                                {% endif %}
                            </div>
                        {% endfor %}
                    </div>
                </div>
            {% endfor %}
            {% if has_legendary %}
              <div style="margin-top:14px;border:1px solid #f39c12;border-radius:8px;padding:10px;">
                <h3 style="margin:0 0 8px;color:#f39c12;">★ Legendary Item-pulje (Tier 5)</h3>
                <div class="item-list-mini">
                {% for item_name, data in all_items.items() if data.tier == 5 %}
                  {% set is_banned = item_name in banned_items or data.category in banned_categories %}
                  <div class="item-chip {% if is_banned %}banned{% endif %}" title="{{ data.category }} · Tier 5">
                    <img src="{{ data.img }}" class="item-img" style="width:22px;height:22px;" alt="{{ item_name }} ikon" onerror="this.onerror=null;this.style.display='none';">
                    {% if phase == 'lobby' %}
                      {% if item_name in banned_items %}
                        <form method="POST" action="/unban/item/{{ item_name }}" style="display:inline;"><button type="submit" style="background:none;border:0;padding:0;color:#f3c36a;cursor:pointer;">{{ item_name }}</button></form>
                      {% else %}
                        <form method="POST" action="/ban/item/{{ item_name }}" style="display:inline;"><button type="submit" style="background:none;border:0;padding:0;color:#f3c36a;cursor:pointer;">{{ item_name }} ★</button></form>
                      {% endif %}
                    {% else %}<span>{{ item_name }} ★</span>{% endif %}
                  </div>
                {% endfor %}
                </div>
              </div>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

@app.route("/api/state", methods=["GET"])
def get_state():
    return jsonify({"phase": GAME_STATE["phase"], "version": GAME_STATE["version"]})

@app.route("/api/roll_item", methods=["GET"])
def api_roll_item():
    try:
        slot_idx = int(request.args.get("slot", "-1"))
    except (TypeError, ValueError):
        slot_idx = -1
    slot_tiers = GAME_STATE["slot_tiers"].get(str(slot_idx), GAME_STATE["enabled_tiers"])
    allowed_tiers = set(GAME_STATE["enabled_tiers"]) & set(slot_tiers)
    active_items = [
        name for name, data in ALL_ITEMS.items()
        if name not in GAME_STATE["banned_items"]
        and data["category"] not in GAME_STATE["banned_categories"]
        and data.get("tier", 1) in allowed_tiers
    ]
    if not active_items:
        return jsonify({"error": "no_active_items"}), 409
    chosen = random.choice(active_items)
    return jsonify({"item_name": chosen})

@app.route("/", methods=["GET"])
def index():
    player_name = session.get("player_name")
    player_data = GAME_STATE["players"].get(player_name) if player_name else None
    # A reset can be triggered by another browser; discard stale browser sessions
    # so that those users can join the new lobby instead of being stuck as ghosts.
    if player_name and player_data is None:
        session.pop("player_name", None)
        player_name = None
    status_msg = session.pop("status_msg", None)
    highlight_slots = session.pop("highlight_slots", [])
    
    active_heroes = {
        h: img for h, img in HEROES.items()
        if h not in GAME_STATE["banned_heroes"] and h not in UNRELEASED_HEROES
    }
    active_items = {
        name: data for name, data in ALL_ITEMS.items()
        if name not in GAME_STATE["banned_items"] and data["category"] not in GAME_STATE["banned_categories"]
    }
    
    all_items_chosen = False
    if player_data and GAME_STATE["phase"] == "draft":
        all_items_chosen = all(item is not None for item in player_data["items"])

    return render_template_string(
        HTML_TEMPLATE,
        phase=GAME_STATE["phase"],
        players=GAME_STATE["players"],
        current_player=player_name,
        player_data=player_data,
        heroes_dict=HEROES,
        fallback_heroes=FALLBACK_HEROES,
        unreleased_heroes=UNRELEASED_HEROES,
        data_source=DATA_SOURCE["name"],
        active_heroes=active_heroes,
        item_categories=ITEM_CATEGORIES,
        all_items=ALL_ITEMS,
        has_legendary=any(data.get("tier") == 5 for data in ALL_ITEMS.values()),
        active_items_dict_json=json.dumps(active_items),
        banned_heroes=GAME_STATE["banned_heroes"],
        banned_items=GAME_STATE["banned_items"],
        banned_categories=GAME_STATE["banned_categories"],
        enabled_tiers=GAME_STATE["enabled_tiers"],
        slot_tiers=GAME_STATE["slot_tiers"],
        items_per_player=GAME_STATE["items_per_player"],
        all_items_chosen=all_items_chosen,
        status_msg=status_msg,
        highlight_slots=highlight_slots,
        state_version=GAME_STATE["version"]
    )

@app.route("/join", methods=["POST"])
def join():
    name = request.form.get("player_name", "").strip()
    if not name:
        session["status_msg"] = "Indtast et spillernavn for at deltage."
        return redirect(url_for("index"))
    if len(name) > 24:
        session["status_msg"] = "Spillernavnet må højst være 24 tegn."
        return redirect(url_for("index"))
    if GAME_STATE["phase"] != "lobby":
        session["status_msg"] = "Et spil er allerede i gang. Nye spillere kan først deltage efter reset."
        return redirect(url_for("index"))

    # Names are case-insensitive for uniqueness, preventing two browsers from
    # accidentally controlling the same player by entering e.g. Alice / alice.
    existing_name = next((n for n in GAME_STATE["players"] if n.casefold() == name.casefold()), None)
    current_name = session.get("player_name")
    if existing_name is not None and existing_name != current_name:
        session["status_msg"] = f"Navnet '{existing_name}' er allerede taget i lobbyen. Vælg et andet navn."
        return redirect(url_for("index"))

    session["player_name"] = name
    if name not in GAME_STATE["players"]:
        GAME_STATE["players"][name] = {
            "ready": False,
            "hero": "",
            "hero_img": "",
            "items": [None] * GAME_STATE["items_per_player"],
            "locked_slots": set(),
            "has_rerolled": False,
            "has_stolen": False
        }
        bump_state()
    return redirect(url_for("index"))

@app.route("/ready", methods=["POST"])
def ready():
    name = session.get("player_name")
    if name and name in GAME_STATE["players"] and GAME_STATE["phase"] == "lobby":
        active_heroes = [h for h in HEROES if h not in GAME_STATE["banned_heroes"] and h not in UNRELEASED_HEROES]
        active_tiers = set(GAME_STATE["enabled_tiers"])
        active_items = [n for n, d in ALL_ITEMS.items()
                        if n not in GAME_STATE["banned_items"]
                        and d["category"] not in GAME_STATE["banned_categories"]
                        and d.get("tier", 1) in active_tiers]
        if not active_heroes:
            session["status_msg"] = "Der er ingen aktive heroes. Fjern nogle hero-bans, før spillet startes."
            return redirect(url_for("index"))
        if not active_items:
            session["status_msg"] = "Item-puljen er tom. Aktivér mindst én item-kategori eller fjern nogle item-bans."
            return redirect(url_for("index"))

        GAME_STATE["players"][name]["ready"] = True
        bump_state()
        all_ready = bool(GAME_STATE["players"]) and all(p["ready"] for p in GAME_STATE["players"].values())
        if all_ready:
            GAME_STATE["phase"] = "draft"
            random.shuffle(active_heroes)
            for idx, p_data in enumerate(GAME_STATE["players"].values()):
                p_data["hero"] = active_heroes[idx % len(active_heroes)]
                p_data["hero_img"] = HEROES.get(p_data["hero"], "")
                p_data["items"] = [None] * GAME_STATE["items_per_player"]
                p_data["locked_slots"] = set()
                p_data["has_rerolled"] = False
                p_data["has_stolen"] = False
                p_data["ready"] = False
            bump_state()
    return redirect(url_for("index"))

@app.route("/update_data", methods=["GET"])
def update_data_web():
    source = load_game_data(force_refresh=True)
    if source == "api":
        session["status_msg"] = f"Data opdateret fra API: {len(HEROES)} heroes og {len(ALL_ITEMS)} items."
    else:
        failures = [line for line in LOAD_LOG if "failed" in line or "SSL" in line]
        reason = failures[-1] if failures else (LOAD_LOG[-1] if LOAD_LOG else "ukendt årsag")
        session["status_msg"] = (
            f"Kunne ikke hente fra API'et ({reason}) - bruger {source}-data "
            f"({len(HEROES)} heroes, {len(ALL_ITEMS)} items). Se /api/debug for detaljer."
        )
    bump_state()
    return redirect(url_for("index"))


@app.route("/api/debug", methods=["GET"])
def api_debug():
    return jsonify({
        "source": DATA_SOURCE["name"],
        "heroes": len(HEROES),
        "unreleased_heroes": sorted(UNRELEASED_HEROES),
        "items": len(ALL_ITEMS),
        "items_per_category": {c: len(i) for c, i in ITEM_CATEGORIES.items()},
        "log": LOAD_LOG,
    })

@app.route("/pool_settings", methods=["POST"])
def pool_settings():
    if GAME_STATE["phase"] != "lobby":
        return redirect(url_for("index"))
    try:
        enabled = sorted({int(v) for v in request.form.getlist("enabled_tiers") if int(v) in (1,2,3,4,5)})
    except (TypeError, ValueError):
        enabled = []
    if not enabled:
        session["status_msg"] = "Vælg mindst ét globalt tier, før puljen gemmes."
        return redirect(url_for("index"))
    try:
        item_count = int(request.form.get("items_per_player", GAME_STATE["items_per_player"]))
        if item_count < 1 or item_count > 12:
            raise ValueError
    except (TypeError, ValueError):
        session["status_msg"] = "Antal items skal være mellem 1 og 12."
        return redirect(url_for("index"))
    slot_config = {}
    for idx in range(item_count):
        values = []
        for raw in request.form.getlist(f"slot_{idx}_tiers"):
            try:
                tier = int(raw)
                if tier in (1,2,3,4,5): values.append(tier)
            except (TypeError, ValueError):
                pass
        # Nye slots får alle tiers som standard, hvis ingen blev sendt.
        slot_config[str(idx)] = sorted(set(values)) if values else [1,2,3,4,5]
    GAME_STATE["enabled_tiers"] = enabled
    GAME_STATE["items_per_player"] = item_count
    GAME_STATE["slot_tiers"] = slot_config
    # Lobbyspillere får deres tomme slots tilpasset med det samme.
    for player in GAME_STATE["players"].values():
        current_items = list(player.get("items", []))
        player["items"] = (current_items + [None] * item_count)[:item_count]
        player["locked_slots"] = {i for i in player.get("locked_slots", set()) if i < item_count}
    bump_state()
    session["status_msg"] = f"Item-puljer gemt. Hver spiller får nu {item_count} item(s); Tier 5 er Legendary."
    return redirect(url_for("index"))


@ app.route("/ban/category", methods=["POST"])
def ban_category():
    cat = request.form.get("category")
    if cat and GAME_STATE["phase"] == "lobby":
        if cat in GAME_STATE["banned_categories"]:
            GAME_STATE["banned_categories"].remove(cat)
        else:
            GAME_STATE["banned_categories"].append(cat)
        bump_state()
    return redirect(url_for("index"))

@app.route("/ban/hero/<hero_name>", methods=["POST"])
def ban_hero(hero_name):
    if GAME_STATE["phase"] == "lobby" and hero_name in HEROES and hero_name not in UNRELEASED_HEROES:
        if hero_name not in GAME_STATE["banned_heroes"]:
            GAME_STATE["banned_heroes"].append(hero_name)
            bump_state()
    return redirect(url_for("index"))

@app.route("/unban/hero/<hero_name>", methods=["POST"])
def unban_hero(hero_name):
    if GAME_STATE["phase"] == "lobby" and hero_name in GAME_STATE["banned_heroes"]:
        GAME_STATE["banned_heroes"].remove(hero_name)
        bump_state()
    return redirect(url_for("index"))

@app.route("/ban/item/<item_name>", methods=["POST"])
def ban_item(item_name):
    if GAME_STATE["phase"] == "lobby" and item_name in ALL_ITEMS:
        if item_name not in GAME_STATE["banned_items"]:
            GAME_STATE["banned_items"].append(item_name)
            bump_state()
    return redirect(url_for("index"))

@app.route("/unban/item/<item_name>", methods=["POST"])
def unban_item(item_name):
    if GAME_STATE["phase"] == "lobby" and item_name in GAME_STATE["banned_items"]:
        GAME_STATE["banned_items"].remove(item_name)
        bump_state()
    return redirect(url_for("index"))

@app.route("/spin/<int:slot_idx>")
def spin(slot_idx):
    name = session.get("player_name")
    if name and GAME_STATE["phase"] == "draft":
        player = GAME_STATE["players"].get(name)
        if player and 0 <= slot_idx < len(player["items"]):
            slot_tiers = GAME_STATE["slot_tiers"].get(str(slot_idx), GAME_STATE["enabled_tiers"])
            allowed_tiers = set(GAME_STATE["enabled_tiers"]) & set(slot_tiers)
            active_items = [n for n, d in ALL_ITEMS.items()
                            if n not in GAME_STATE["banned_items"]
                            and d["category"] not in GAME_STATE["banned_categories"]
                            and d.get("tier", 1) in allowed_tiers]
            if slot_idx not in player["locked_slots"] and player["items"][slot_idx] is None and active_items:
                # Brug samme item som rouletten viste, men accepter kun et aktuelt gyldigt valg.
                requested_item = request.args.get("item", "")
                chosen_item = requested_item if requested_item in active_items else random.choice(active_items)
                player["items"][slot_idx] = chosen_item
                bump_state()
    return redirect(url_for("index"))

@app.route("/finish_draft", methods=["POST"])
def finish_draft():
    name = session.get("player_name")
    if not name or GAME_STATE["phase"] != "draft":
        return redirect(url_for("index"))
    player = GAME_STATE["players"].get(name)
    if not player:
        return redirect(url_for("index"))
    if any(item is None for item in player["items"]):
        session["status_msg"] = "Du skal trække et item til alle slots, før du kan afslutte draften."
        return redirect(url_for("index"))
    if player["ready"]:
        return redirect(url_for("index"))

    player["ready"] = True
    bump_state()
    all_done = bool(GAME_STATE["players"]) and all(p["ready"] for p in GAME_STATE["players"].values())
    if all_done:
        GAME_STATE["phase"] = "actions"
        for p in GAME_STATE["players"].values():
            p["ready"] = False
        bump_state()
    return redirect(url_for("index"))

@app.route("/action/lock", methods=["POST"])
def action_lock():
    name = session.get("player_name")
    if name and GAME_STATE["phase"] == "actions":
        player = GAME_STATE["players"].get(name)
        if player:
            try:
                slot_idx = int(request.form.get("slot_idx", -1))
            except ValueError:
                slot_idx = -1
                
            if 0 <= slot_idx < len(player["items"]) and player["items"][slot_idx] is not None:
                if slot_idx in player["locked_slots"]:
                    player["locked_slots"].remove(slot_idx)
                    session["status_msg"] = f"🔓 Slot #{slot_idx+1} er nu låst op."
                    session["highlight_slots"] = [slot_idx]
                else:
                    player["locked_slots"].add(slot_idx)
                    session["status_msg"] = f"🔒 Slot #{slot_idx+1} er nu låst fast!"
                    session["highlight_slots"] = [slot_idx]
                bump_state()
    return redirect(url_for("index"))

@app.route("/action/reroll", methods=["POST"])
def action_reroll():
    name = session.get("player_name")
    if name and GAME_STATE["phase"] == "actions":
        player = GAME_STATE["players"].get(name)
        if player and not player["has_rerolled"]:
            try:
                slot_idx = int(request.form.get("slot_idx", -1))
            except ValueError:
                slot_idx = -1
                
            active_items = [
                n for n, d in ALL_ITEMS.items()
                if n not in GAME_STATE["banned_items"] and d["category"] not in GAME_STATE["banned_categories"]
            ]
            if 0 <= slot_idx < len(player["items"]) and player["items"][slot_idx] is not None and active_items:
                if slot_idx not in player["locked_slots"]:
                    old_item = player["items"][slot_idx]
                    already_owned = {item for i, item in enumerate(player["items"])
                                     if item is not None and i != slot_idx}
                    options = [item for item in active_items if item not in already_owned and item != old_item]
                    if not options:
                        options = active_items
                    new_item = random.choice(options)
                    player["items"][slot_idx] = new_item
                    player["has_rerolled"] = True
                    session["status_msg"] = f"♻️ Reroll udført på Slot #{slot_idx+1}: {old_item} ➔ {new_item}"
                    session["highlight_slots"] = [slot_idx]
                    bump_state()
    return redirect(url_for("index"))

@app.route("/action/steal", methods=["POST"])
def action_steal():
    name = session.get("player_name")
    if not name or GAME_STATE["phase"] != "actions":
        return redirect(url_for("index"))
    player = GAME_STATE["players"].get(name)
    if not player or player["has_stolen"]:
        return redirect(url_for("index"))

    target_name = request.form.get("target_name", "")
    target_player = GAME_STATE["players"].get(target_name)
    if not target_player or target_name == name or not any(item is not None for item in target_player["items"]):
        session["status_msg"] = "Vælg en gyldig modstander med items. Dit forsøg er ikke brugt."
        return redirect(url_for("index"))
    try:
        give_idx = int(request.form.get("give_slot", "-1"))
    except (TypeError, ValueError):
        give_idx = -1

    if not 0 <= give_idx < len(player["items"]):
        session["status_msg"] = "Vælg et gyldigt item, du vil give væk."
        return redirect(url_for("index"))
    if player["items"][give_idx] is None or give_idx in player["locked_slots"]:
        session["status_msg"] = "Du kan kun give et item fra en udfyldt, ulåst slot. Dit forsøg er ikke brugt."
        return redirect(url_for("index"))

    target_slots = [idx for idx, item in enumerate(target_player["items"]) if item is not None]
    if not target_slots:
        session["status_msg"] = "Modstanderen har ingen items at forsøge at stjæle."
        return redirect(url_for("index"))

    # Gamble: opponent's inventory and lock status are never shown to the attacker.
    # The draw includes locked slots; hitting one consumes the attempt without a swap.
    target_idx = random.choice(target_slots)
    if target_idx in target_player["locked_slots"]:
        player["has_stolen"] = True
        session["status_msg"] = "🎲 Du ramte en låst slot! Dit tyveriforsøg er brugt, og intet byttes."
        bump_state()
        return redirect(url_for("index"))

    offered_item = player["items"][give_idx]
    received_item = target_player["items"][target_idx]
    player["items"][give_idx] = received_item
    target_player["items"][target_idx] = offered_item
    player["has_stolen"] = True
    session["status_msg"] = f"🎉 BLINDBYTTE LYKKEDES! Slot #{give_idx+1}: {offered_item} ➜ {received_item}. Du fik itemet ved at stjæle/bytte med {target_name}."
    session["highlight_slots"] = [give_idx]
    bump_state()
    return redirect(url_for("index"))

@app.route("/finish_actions", methods=["POST"])
def finish_actions():
    name = session.get("player_name")
    if not name or GAME_STATE["phase"] != "actions" or name not in GAME_STATE["players"]:
        return redirect(url_for("index"))
    player = GAME_STATE["players"][name]
    if not player["ready"]:
        player["ready"] = True
        bump_state()
    all_ready = bool(GAME_STATE["players"]) and all(p["ready"] for p in GAME_STATE["players"].values())
    if all_ready:
        GAME_STATE["phase"] = "finished"
        bump_state()
    return redirect(url_for("index"))

@app.route("/reset", methods=["POST"])
def reset():
    GAME_STATE["phase"] = "lobby"
    GAME_STATE["players"] = {}
    GAME_STATE["banned_heroes"] = []
    GAME_STATE["banned_items"] = []
    GAME_STATE["banned_categories"] = []
    GAME_STATE["version"] = 0
    session.clear()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")),
            debug=os.environ.get("FLASK_DEBUG", "0").lower() in {"1", "true", "yes"})