import os
import json
import math
import pandas as pd
from webapp.database import get_item_stats_for_server, get_item_stats, get_unique_servers


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(BASE_DIR, "portfolio_data.json")
TXT_PATH = os.path.join(BASE_DIR, "excel_export_item_list.txt")

def load_items():
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except Exception as e:
            print(f"JSON portfoy yuklenirken hata: {e}")

    if os.path.exists(TXT_PATH):
        try:
            items = []
            with open(TXT_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if "|" in line:
                        parts = line.split("|")
                        try:
                            bp = float(parts[2]) if len(parts) > 2 and parts[2] and parts[2] != "nan" else 0
                        except (ValueError, TypeError):
                            bp = 0
                        if math.isnan(bp):
                            bp = 0
                        try:
                            sp = float(parts[6]) if len(parts) > 6 and parts[6] and parts[6] != "nan" else 0
                        except (ValueError, TypeError):
                            sp = 0
                        if math.isnan(sp):
                            sp = 0
                        items.append({
                            "name": parts[0].strip(),
                            "lvl": parts[1].strip() if len(parts) > 1 else "",
                            "buy_price": int(bp),
                            "buy_strategy": parts[3].strip() if len(parts) > 3 else "Auto",
                            "count": int(parts[4]) if len(parts) > 4 and parts[4] else 1,
                            "sell_strategy": parts[5].strip() if len(parts) > 5 else "Auto",
                            "sell_price": int(sp),
                        })
                    elif ":" in line and not line.startswith("http"):
                        parts = line.rsplit(":", 1)
                        items.append({
                            "name": parts[0].strip(), "lvl": parts[1].strip() if len(parts) > 1 else "",
                            "buy_price": 0, "buy_strategy": "Auto", "count": 1, "sell_strategy": "Auto",
                        })
                    else:
                        items.append({
                            "name": line.strip(), "lvl": "",
                            "buy_price": 0, "buy_strategy": "Auto", "count": 1, "sell_strategy": "Auto",
                        })
            return items
        except Exception as e:
            print(f"TXT portfoy yuklenirken hata: {e}")

    return []


def _sell_stats(item_name, db_lvl):
    from webapp.database import get_db
    with get_db() as db:
        rows = db.execute(
            "SELECT price FROM prices WHERE item_name=? AND item_lvl=? AND LOWER(type)='sell' ORDER BY price",
            (item_name, db_lvl),
        ).fetchall()
    if not rows:
        return {}
    vals = [r["price"] for r in rows]
    v = sorted(vals)
    n = len(v)
    def pct(p):
        return v[max(0, min(n - 1, int(n * p / 100)))]
    return {
        "min": int(v[0]), "max": int(v[-1]),
        "median": int(v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) // 2),
        "ci_high": int(pct(95)),
        "avg": int(round(sum(v) / n)),
    }


def compute_row(item):
    db_lvl = "" if item["lvl"] in ("+0", "0", "") else item["lvl"]
    servers = get_unique_servers()

    market = {}
    for srv in servers:
        stats = get_item_stats_for_server(item["name"], db_lvl, srv)
        if stats and stats.get("sell"):
            market[srv] = stats["sell"]["median"]

    all_stats = _sell_stats(item["name"], db_lvl)

    buy_price = item.get("buy_price", 0)
    count = item.get("count", 1)
    total_cost = buy_price * count

    strat = item.get("sell_strategy", "Auto")
    sell_price = item.get("sell_price", 0)
    if not sell_price and all_stats:
        LABEL_MAP = {"Medyan": "median", "Min": "min", "Max": "max", "%95 Ust": "ci_high", "Ortalama": "avg", "Auto": "median"}
        key = LABEL_MAP.get(strat, "median")
        sell_price = all_stats.get(key, 0)

    unit_profit = int(sell_price * 0.97) - buy_price if sell_price > 0 and buy_price > 0 else 0
    total_profit = unit_profit * count
    roi = round(unit_profit / buy_price * 100, 1) if buy_price > 0 else 0

    return {
        "name": item["name"],
        "lvl": item["lvl"],
        "count": count,
        "buy_price": buy_price,
        "buy_strategy": item.get("buy_strategy", "Auto"),
        "total_cost": total_cost,
        "sell_price": sell_price,
        "sell_strategy": strat,
        "unit_profit": unit_profit,
        "total_profit": total_profit,
        "roi": roi,
        "market": {k: int(v) for k, v in market.items()},
        "has_data": bool(all_stats),
        "status": "Kar" if total_profit > 0 else ("Zarar" if total_profit < 0 else ""),
    }


def to_dataframe(rows):
    servers = get_unique_servers()
    flat = []
    for r in rows:
        row = {
            "Item": r["name"],
            "Level": r["lvl"],
            "Adet": r["count"],
            "Alis Fiyati": r["buy_price"],
            "Alis Stratejisi": r["buy_strategy"],
            "Toplam Maliyet": r["total_cost"],
            "Satis Fiyati": r["sell_price"],
            "Satis Stratejisi": r["sell_strategy"],
            "Birim Kar": r["unit_profit"],
            "Toplam Kar": r["total_profit"],
            "ROI (%)": r["roi"],
            "Durum": r["status"],
        }
        for srv in servers:
            row[srv] = r.get("market", {}).get(srv, "")
        flat.append(row)
    return pd.DataFrame(flat)

