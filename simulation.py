import sqlite3
import random
import time
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "app_data.db")

# === NORMAL ESYALAR ===
ITEMS = {
    # === TAKI (JEWELRY) - +0 ile +8 arasi ===
    "Flame Ring":          {"base": 18000000,  "var": 0.10, "lvls": ["+0","+1","+2","+3","+4","+5","+6","+7","+8"]},
    "Ring of Courage":     {"base": 12000000,  "var": 0.12, "lvls": ["+0","+1","+2","+3","+4","+5","+6","+7","+8"]},
    "Agate Earring":       {"base": 8000000,   "var": 0.14, "lvls": ["+0","+1","+2","+3","+4","+5","+6","+7","+8"]},
    "Mage Earring":        {"base": 10000000,  "var": 0.12, "lvls": ["+0","+1","+2","+3","+4","+5","+6","+7","+8"]},
    "Amulet of Strength":  {"base": 15000000,  "var": 0.10, "lvls": ["+0","+1","+2","+3","+4","+5","+6","+7","+8"]},
    "Amulet of Curse":     {"base": 12000000,  "var": 0.11, "lvls": ["+0","+1","+2","+3","+4","+5","+6","+7","+8"]},
    "Amulet of Magic Power": {"base": 9000000, "var": 0.13, "lvls": ["+0","+1","+2","+3","+4","+5","+6","+7","+8"]},
    "Iron Necklace":       {"base": 25000000,  "var": 0.06, "lvls": ["+0","+1","+2","+3","+4","+5","+6","+7","+8"]},
    "Glass Belt":          {"base": 14000000,  "var": 0.08, "lvls": ["+0","+1","+2","+3","+4","+5","+6","+7","+8"]},
    "Light Belt of Life":  {"base": 11000000,  "var": 0.10, "lvls": ["+0","+1","+2","+3","+4","+5","+6","+7","+8"]},
    "Akaras Iron Belt":    {"base": 30000000,  "var": 0.05, "lvls": ["+0","+1","+2","+3","+4","+5","+6","+7","+8"]},

    # === KAĞIT / SCROLL - level YOK, sadece +0 ===
    "Blessed Upgrade Scroll":    {"base": 90000000,  "var": 0.08, "lvls": ["+0"]},
    "Upgrade Scroll":            {"base": 35000000,  "var": 0.10, "lvls": ["+0"]},
    "Blessed Talisman Enhancement Item": {"base": 50000000, "var": 0.06, "lvls": ["+0"]},

    # === KOSTÜM - level YOK, sadece +0 ===
    "Ruler of the Legend - White Tiger": {"base": 80000000, "var": 0.05, "lvls": ["+0"]},
    "Ruler of the Legend - Pegasus(Fire)": {"base": 45000000, "var": 0.06, "lvls": ["+0"]},

    # === SILAH - KILIC (+0 ile +7 arasi) ===
    "Dark Vane":           {"base": 30000000,  "var": 0.06, "lvls": ["+0","+1","+2","+3","+4","+5","+6","+7"]},
    "Avedon":              {"base": 45000000,  "var": 0.05, "lvls": ["+0","+1","+2","+3","+4","+5","+6","+7"]},
    "Heros Valor":         {"base": 55000000,  "var": 0.05, "lvls": ["+0","+1","+2","+3","+4","+5","+6","+7"]},

    # === SILAH - TOKAC (+1 ile +7 arasi, +0 YOK) ===
    "Iron Impact":         {"base": 22000000,  "var": 0.10, "lvls": ["+1","+2","+3","+4","+5","+6","+7"]},
    "Hepas Iron Impact":   {"base": 28000000,  "var": 0.08, "lvls": ["+1","+2","+3","+4","+5","+6","+7"]},

    # === SILAH - KAMA (+1 ile +7 arasi, +0 YOK) ===
    "Mirage Dagger":       {"base": 15000000,  "var": 0.15, "lvls": ["+1","+2","+3","+4","+5","+6","+7"]},
    "Cold-Hearted Dagger": {"base": 20000000,  "var": 0.08, "lvls": ["+1","+2","+3","+4","+5","+6","+7"]},

    # === SILAH - KALKAN (+0 ile +7 arasi) ===
    "Dread Shield":        {"base": 35000000,  "var": 0.06, "lvls": ["+0","+1","+2","+3","+4","+5","+6","+7"]},

    # === SILAH - YAY (+1 ile +7 arasi, +0 YOK) ===
    "Vortex Bow":          {"base": 18000000,  "var": 0.12, "lvls": ["+1","+2","+3","+4","+5","+6","+7"]},
    "Hepas Iron Bow":      {"base": 25000000,  "var": 0.10, "lvls": ["+1","+2","+3","+4","+5","+6","+7"]},
    "Raptor":              {"base": 32000000,  "var": 0.09, "lvls": ["+1","+2","+3","+4","+5","+6","+7"]},

    # === SILAH - SUZAK (+1 ile +7 arasi, +0 YOK) ===
    "Spear of Murky Waters": {"base": 24000000, "var": 0.08, "lvls": ["+1","+2","+3","+4","+5","+6","+7"]},
    "Abyss Jamadar":       {"base": 20000000,  "var": 0.10, "lvls": ["+1","+2","+3","+4","+5","+6","+7"]},

    # === SILAH - STAF (+0 ile +7 arasi) ===
    "Scorching Staff":     {"base": 26000000,  "var": 0.07, "lvls": ["+0","+1","+2","+3","+4","+5","+6","+7"]},
    "Foverin":             {"base": 22000000,  "var": 0.08, "lvls": ["+1","+2","+3","+4","+5","+6","+7"]},
    "Elysium":             {"base": 18000000,  "var": 0.10, "lvls": ["+1","+2","+3","+4","+5","+6","+7"]},

    # === ZIRH (+1 ile +7 arasi, +0 YOK) ===
    "Chitin Boots":        {"base": 5000000,   "var": 0.15, "lvls": ["+1","+2","+3","+4","+5","+6","+7"]},
    "Dragon Scale Boots":  {"base": 40000000,  "var": 0.06, "lvls": ["+1","+2","+3","+4","+5","+6","+7"]},
    "Rogue Chitin Armor Pauldron": {"base": 8000000, "var": 0.18, "lvls": ["+1","+2","+3","+4","+5","+6","+7"]},
    "Rogue Full Plate Armor Pads": {"base": 6000000, "var": 0.15, "lvls": ["+1","+2","+3","+4","+5","+6","+7"]},
    "Pauldron of Trial":   {"base": 12000000,  "var": 0.10, "lvls": ["+1","+2","+3","+4","+5","+6","+7"]},
    "Gauntlets of Trial":  {"base": 10000000,  "var": 0.12, "lvls": ["+1","+2","+3","+4","+5","+6","+7"]},

    # === TAS / GEM - level YOK, sadece +0 ===
    "black gem":           {"base": 35000000,  "var": 0.15, "lvls": ["+0"]},
    "green gem":           {"base": 28000000,  "var": 0.15, "lvls": ["+0"]},
    "blue gem":            {"base": 42000000,  "var": 0.12, "lvls": ["+0"]},
    "Jewel of Dexterity":  {"base": 50000000,  "var": 0.06, "lvls": ["+0"]},
    "Fortified Sterling Silver Gemstone": {"base": 7000000, "var": 0.10, "lvls": ["+0"]},

    # === KUTU / BOX - level YOK, sadece +0 ===
    "Old Draki Supply Box": {"base": 72000000, "var": 0.08, "lvls": ["+0"]},
    "Blue Treasure Chest": {"base": 55000000, "var": 0.10, "lvls": ["+0"]},

    # === FRAGMENT / MATERYAL - level YOK, sadece +0 ===
    "Fragment of Arrogance": {"base": 48000000, "var": 0.10, "lvls": ["+0"]},
    "Trinas Piece":        {"base": 100000000, "var": 0.10, "lvls": ["+0"]},
    "Weapon Breaker":      {"base": 85000000,  "var": 0.12, "lvls": ["+0"]},
    "Hepas Shard":         {"base": 45000000,  "var": 0.10, "lvls": ["+0"]},

    # === DRakis PENDANT - level YOK, sadece +0 ===
    "Drakis Pendant of Strength B.A.D":  {"base": 50000000, "var": 0.04, "lvls": ["+0"]},
    "Drakis Pendant of Philosopher D.S": {"base": 45000000, "var": 0.04, "lvls": ["+0"]},
    "Drakis Pendant of Magic A.A":       {"base": 42000000, "var": 0.04, "lvls": ["+0"]},
    "Drakis Pendant of Dexterity C.A":   {"base": 38000000, "var": 0.04, "lvls": ["+0"]},

    # === OZEL / MISC - level YOK, sadece +0 ===
    "Glave":              {"base": 9333000,   "var": 0.20, "lvls": ["+0"]},
    "Exceptional Blade Axe": {"base": 7985000, "var": 0.18, "lvls": ["+0"]},
    "Diamond Ring":        {"base": 430000000, "var": 0.05, "lvls": ["+0"]},

    # === OZEL TAKI - +0 ile +8 arasi ===
    "Cockatrices Earrings": {"base": 30000000, "var": 0.08, "lvls": ["+0","+1","+2","+3","+4","+5","+6","+7","+8"]},
    "Cypher Ring":         {"base": 80000000,  "var": 0.06, "lvls": ["+0","+1","+2","+3","+4","+5","+6","+7","+8"]},
}

# === REVERSE ESYALAR (ayri fiyat, +XR formati) ===
REVERSE_ITEMS = {
    # SILAH - Reverse
    "Iron Impact":         {"base": 8000000,   "var": 0.12, "lvls": ["+1R","+2R","+3R","+4R","+5R","+6R","+7R"]},
    "Hepas Iron Impact":   {"base": 10000000,  "var": 0.10, "lvls": ["+1R","+2R","+3R","+4R","+5R","+6R","+7R"]},
    "Raptor":              {"base": 12000000,  "var": 0.10, "lvls": ["+1R","+2R","+3R","+4R","+5R","+6R","+7R"]},
    "Vortex Bow":          {"base": 7000000,   "var": 0.14, "lvls": ["+1R","+2R","+3R","+4R","+5R","+6R","+7R"]},
    "Hepas Iron Bow":      {"base": 9000000,   "var": 0.12, "lvls": ["+1R","+2R","+3R","+4R","+5R","+6R","+7R"]},
    "Mirage Dagger":       {"base": 6000000,   "var": 0.15, "lvls": ["+1R","+2R","+3R","+4R","+5R","+6R","+7R"]},
    "Cold-Hearted Dagger": {"base": 8000000,   "var": 0.10, "lvls": ["+1R","+2R","+3R","+4R","+5R","+6R","+7R"]},
    "Spear of Murky Waters": {"base": 9000000, "var": 0.10, "lvls": ["+1R","+2R","+3R","+4R","+5R","+6R","+7R"]},
    "Abyss Jamadar":       {"base": 7500000,   "var": 0.12, "lvls": ["+1R","+2R","+3R","+4R","+5R","+6R","+7R"]},
    "Scorching Staff":     {"base": 10000000,  "var": 0.08, "lvls": ["+1R","+2R","+3R","+4R","+5R","+6R","+7R"]},
    "Foverin":             {"base": 8500000,   "var": 0.10, "lvls": ["+1R","+2R","+3R","+4R","+5R","+6R","+7R"]},
    "Elysium":             {"base": 7000000,   "var": 0.12, "lvls": ["+1R","+2R","+3R","+4R","+5R","+6R","+7R"]},

    # ZIRH - Reverse
    "Chitin Boots":        {"base": 2500000,   "var": 0.18, "lvls": ["+1R","+2R","+3R","+4R","+5R","+6R","+7R"]},
    "Dragon Scale Boots":  {"base": 15000000,  "var": 0.08, "lvls": ["+1R","+2R","+3R","+4R","+5R","+6R","+7R"]},
    "Rogue Chitin Armor Pauldron": {"base": 3500000, "var": 0.20, "lvls": ["+1R","+2R","+3R","+4R","+5R","+6R","+7R"]},
    "Rogue Full Plate Armor Pads": {"base": 2800000, "var": 0.18, "lvls": ["+1R","+2R","+3R","+4R","+5R","+6R","+7R"]},

    # KILIC - Reverse
    "Dark Vane":           {"base": 12000000,  "var": 0.08, "lvls": ["+1R","+2R","+3R","+4R","+5R","+6R","+7R"]},
    "Avedon":              {"base": 18000000,  "var": 0.06, "lvls": ["+1R","+2R","+3R","+4R","+5R","+6R","+7R"]},
    "Heros Valor":         {"base": 22000000,  "var": 0.06, "lvls": ["+1R","+2R","+3R","+4R","+5R","+6R","+7R"]},

    # TAKI - Reverse
    "Flame Ring":          {"base": 7000000,   "var": 0.12, "lvls": ["+1R","+2R","+3R","+4R","+5R","+6R","+7R"]},
    "Ring of Courage":     {"base": 5000000,   "var": 0.14, "lvls": ["+1R","+2R","+3R","+4R","+5R","+6R","+7R"]},
    "Cockatrices Earrings": {"base": 12000000, "var": 0.10, "lvls": ["+1R","+2R","+3R","+4R","+5R","+6R","+7R"]},
}

SERVERS = ["Tum Zero", "Tum Pandora", "Tum Agartha", "Tum Felis", "Tum Destan"]

SELLERS = [
    "Kn1ght_Farmer", "PvP_Pro", "MarketKing", "TradeMaster",
    "ZeroTrader", "AgarthaBot", "FelisGold", "DestanProfit",
    "SilentSeller", "QuickDeal", "PandoraSniper", ""
]

# Normal level carpanlari
LVLMULTI = {
    "+0": 1.0, "+1": 1.3, "+2": 1.7, "+3": 2.2,
    "+4": 3.0, "+5": 4.0, "+6": 5.5, "+7": 7.5, "+8": 10.0,
    "+9": 13.0, "+10": 17.0,
    # Reverse level carpanlari (dusuk)
    "+1R": 0.5, "+2R": 0.65, "+3R": 0.8, "+4R": 1.0,
    "+5R": 1.3, "+6R": 1.6, "+7R": 2.0, "+8R": 2.5,
    "+9R": 3.0, "+10R": 3.5, "+11R": 4.0, "+12R": 4.5,
    "+13R": 5.0, "+14R": 5.5, "+15R": 6.0, "+16R": 6.5,
    "+17R": 7.0, "+18R": 7.5, "+19R": 8.0, "+20R": 8.5, "+21R": 9.0,
}


def get_db_prices(item_name, item_lvl):
    """DB'den gercek fiyat araligini oku (varsa)."""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=15)
        rows = conn.execute(
            "SELECT MIN(price), MAX(price), AVG(price) FROM prices WHERE item_name=? AND item_lvl=?",
            (item_name, item_lvl)
        ).fetchone()
        conn.close()
        if rows and rows[0] is not None:
            return rows[0], rows[1], int(rows[2])
    except Exception:
        pass
    return None, None, None


def get_price(base, variance, lvl, item_name=None):
    """Fiyat hesapla - DB'den okumaya calis, yoksa hardcoded kullan."""
    if item_name:
        db_min, db_max, db_avg = get_db_prices(item_name, lvl)
        if db_avg is not None:
            # DB'den fiyat araligi var, medyan etrafinda dagil
            drift = random.uniform(-variance, variance)
            return max(1, int(db_avg * (1 + drift)))

    # Fallback: hardcoded base + level carpani
    mult = LVLMULTI.get(lvl, 1.0)
    drift = random.uniform(-variance, variance)
    return max(1, int(base * mult * (1 + drift)))


def insert_batch(conn, batch):
    conn.executemany(
        "INSERT INTO prices (server, type, item_name, item_lvl, price, timestamp, seller, last_seen) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        batch
    )
    conn.commit()


def run_simulation(interval=2, batch_min=3, batch_max=8):
    conn = sqlite3.connect(DB_PATH)
    tick = 0

    # Normal + Reverse esyalari birlestir
    all_items = {}
    all_items.update(ITEMS)
    for name, info in REVERSE_ITEMS.items():
        if name in all_items:
            # Normal esya varsa, reverse lvls'leri ekle
            combined_lvls = list(all_items[name]["lvls"]) + info["lvls"]
            all_items[name] = {**all_items[name], "lvls": combined_lvls}
        else:
            all_items[name] = info

    total_items = sum(len(v["lvls"]) for v in all_items.values())
    print(f"[SIM] Basladi! DB: {DB_PATH}")
    print(f"[SIM] Her {interval}s'de {batch_min}-{batch_max} kayit")
    print(f"[SIM] {len(all_items)} item ({len(ITEMS)} normal + {len(REVERSE_ITEMS)} reverse), {total_items} varyant, {len(SERVERS)} sunucu")
    print("[SIM] Durdurmak icin Ctrl+C")
    print("-" * 60)

    try:
        while True:
            tick += 1
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            count = random.randint(batch_min, batch_max)
            batch = []

            for _ in range(count):
                item_name = random.choice(list(all_items.keys()))
                info = all_items[item_name]
                lvl = random.choice(info["lvls"])
                server = random.choice(SELLERS)
                ptype = random.choice(["sell", "sell", "sell", "sell", "buy"])
                price = get_price(info["base"], info["var"], lvl, item_name)
                seller = random.choice(SELLERS)

                batch.append((server, ptype, item_name, lvl, price, now, seller, now))

            insert_batch(conn, batch)

            items_in_batch = set(b[2] + " " + b[3] for b in batch)
            sells = sum(1 for b in batch if b[1] == "sell")
            buys = sum(1 for b in batch if b[1] == "buy")

            total = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
            print(f"[{tick:04d}] {now} | +{count} (S:{sells} B:{buys}) | Toplam: {total} | {', '.join(list(items_in_batch)[:3])}")

            time.sleep(interval)

    except KeyboardInterrupt:
        total = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        print(f"\n[SIM] Durduruldu. Toplam: {total} kayit")
    finally:
        conn.close()


if __name__ == "__main__":
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    run_simulation(interval=interval)
