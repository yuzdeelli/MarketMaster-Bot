import sqlite3
import pandas as pd


class DataFrameAnalytics:
    def __init__(self, db_path):
        self.db_path = db_path

    def _read(self, query, params=None):
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.execute("PRAGMA busy_timeout=15000")
        try:
            df = pd.read_sql_query(query, conn, params=params)
            return df
        finally:
            conn.close()

    def _server_filter(self, server):
        if server:
            return "WHERE server = ?", (server,)
        return "", ()

    @staticmethod
    def _iqr_filter(series):
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        return series[(series >= lower) & (series <= upper)]

    def server_distribution(self, server=None):
        where, params = self._server_filter(server)
        df = self._read(f"SELECT server, COUNT(*) as adet FROM prices {where} GROUP BY server ORDER BY adet DESC", params)
        return {"labels": df["server"].tolist(), "values": df["adet"].tolist()}

    def type_distribution(self, server=None):
        where, params = self._server_filter(server)
        df = self._read(f"SELECT type, COUNT(*) as adet FROM prices {where} GROUP BY type", params)
        return {"labels": df["type"].tolist(), "values": df["adet"].tolist()}

    def level_distribution(self, server=None):
        where, params = self._server_filter(server)
        df = self._read(f"SELECT item_lvl, COUNT(*) as adet FROM prices {where} GROUP BY item_lvl ORDER BY adet DESC", params)
        return {"labels": df["item_lvl"].tolist(), "values": df["adet"].tolist()}

    def top_items(self, limit=20, server=None):
        where, params = self._server_filter(server)
        if where:
            where = " " + where
        df = self._read(
            f"SELECT item_name, COUNT(*) as adet, ROUND(AVG(price)) as ortalama, MIN(price) as min_fiyat, MAX(price) as max_fiyat "
            f"FROM prices {where} GROUP BY item_name ORDER BY adet DESC LIMIT ?",
            params=params + (limit,)
        )
        return {
            "labels": df["item_name"].tolist(),
            "adet": df["adet"].tolist(),
            "ortalama": df["ortalama"].astype(int).tolist(),
            "min_fiyat": df["min_fiyat"].tolist(),
            "max_fiyat": df["max_fiyat"].tolist(),
        }

    def price_by_server(self, item_name=None):
        where = ""
        params = ()
        if item_name:
            where = "WHERE item_name = ?"
            params = (item_name,)
        df = self._read(
            f"SELECT server, ROUND(AVG(price)) as ortalama, COUNT(*) as adet "
            f"FROM prices {where} GROUP BY server ORDER BY ortalama DESC",
            params=params
        )
        return {"labels": df["server"].tolist(), "ortalama": df["ortalama"].astype(int).tolist(), "adet": df["adet"].tolist()}

    def item_prices_by_level(self, server=None):
        where, params = self._server_filter(server)
        df = self._read(
            f"SELECT item_name, item_lvl, ROUND(AVG(price)) as ortalama, COUNT(*) as adet "
            f"FROM prices {where} GROUP BY item_name, item_lvl HAVING adet >= 2 ORDER BY item_name, item_lvl",
            params
        )
        if df.empty:
            return {"rows": []}
        rows = []
        for _, r in df.iterrows():
            rows.append({
                "item": r["item_name"], "lvl": r["item_lvl"],
                "ortalama": int(r["ortalama"]), "adet": int(r["adet"]),
            })
        return {"rows": rows}

    def price_stats(self, item_name=None, server=None):
        conditions = []
        params = []
        if item_name:
            conditions.append("item_name = ?")
            params.append(item_name)
        if server:
            conditions.append("server = ?")
            params.append(server)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        df = self._read(f"SELECT price FROM prices {where}", params=tuple(params))
        if df.empty:
            return {}
        p = df["price"]
        return {
            "count": int(len(p)),
            "min": int(p.min()),
            "max": int(p.max()),
            "mean": int(p.mean()),
            "median": int(p.median()),
            "q1": int(p.quantile(0.25)),
            "q3": int(p.quantile(0.75)),
            "p95": int(p.quantile(0.95)),
            "std": round(float(p.std()), 2),
        }

    def arbitrage(self, server=None, server2=None):
        if server and server2:
            df = self._read(
                "SELECT item_name, item_lvl, server, MIN(price) as min_fiyat "
                "FROM prices WHERE server IN (?, ?) GROUP BY item_name, item_lvl, server",
                params=(server, server2)
            )
        elif server:
            df = self._read(
                "SELECT item_name, item_lvl, server, MIN(price) as min_fiyat "
                "FROM prices WHERE server = ? GROUP BY item_name, item_lvl, server",
                params=(server,)
            )
        else:
            df = self._read(
                "SELECT item_name, item_lvl, server, MIN(price) as min_fiyat "
                "FROM prices GROUP BY item_name, item_lvl, server"
            )
        if df.empty:
            return {"items": [], "columns": []}

        pivot = df.pivot_table(index=["item_name", "item_lvl"], columns="server", values="min_fiyat", aggfunc="min")
        pivot = pivot.dropna(thresh=2)

        result = []
        for (name, lvl), row in pivot.iterrows():
            servers = row.dropna()
            if len(servers) < 2:
                continue
            min_s = servers.idxmin()
            max_s = servers.idxmax()
            min_p = int(servers.min())
            max_p = int(servers.max())
            fark = max_p - min_p
            yuzde = round(fark / min_p * 100, 1) if min_p > 0 else 0
            result.append({
                "item": name, "lvl": lvl,
                "en_ucuz": min_s, "en_ucuz_fiyat": min_p,
                "en_pahali": max_s, "en_pahali_fiyat": max_p,
                "fark": fark, "fark_yuzde": yuzde,
            })

        result.sort(key=lambda x: x["fark_yuzde"], reverse=True)
        return {"items": result[:50], "columns": ["item", "lvl", "en_ucuz", "en_ucuz_fiyat", "en_pahali", "en_pahali_fiyat", "fark", "fark_yuzde"]}

    def all_stats_table(self, server=None):
        where, params = self._server_filter(server)
        df = self._read(f"SELECT item_name, item_lvl, type, server, price FROM prices {where}", params)
        if df.empty:
            return {"rows": [], "columns": []}

        grouped = df.groupby(["item_name", "item_lvl", "type"])
        rows = []
        for (name, lvl, typ), g in grouped:
            p = g["price"]
            sunucular = ", ".join(g["server"].unique())
            rows.append({
                "item": name, "lvl": lvl, "type": typ,
                "adet": int(len(p)),
                "min": int(p.min()), "max": int(p.max()),
                "ortalama": int(p.mean()), "medyan": int(p.median()),
                "Q1": int(p.quantile(0.25)), "Q3": int(p.quantile(0.75)),
                "P95": int(p.quantile(0.95)),
                "sunucular": sunucular,
            })

        rows.sort(key=lambda x: x["adet"], reverse=True)
        return {
            "rows": rows,
            "columns": ["item", "lvl", "type", "adet", "min", "max", "ortalama", "medyan", "Q1", "Q3", "P95", "sunucular"],
        }

    def all(self, server=None):
        return {
            "server_distribution": self.server_distribution(server),
            "type_distribution": self.type_distribution(server),
            "level_distribution": self.level_distribution(server),
            "top_items": self.top_items(20, server),
            "price_by_server": self.price_by_server(),
            "item_prices": self.item_prices_by_level(server),
            "arbitrage": self.arbitrage(server),
            "all_stats": self.all_stats_table(server),
            "volatility": self.volatility(server),
            "demand": self.demand(server),
            "distribution": self.distribution(server),
            "trend": self.trend(server),
            "liquidity": self.liquidity(server),
        }

    def volatility(self, server=None, limit=20):
        where, params = self._server_filter(server)
        df = self._read(
            f"SELECT item_name, item_lvl, price FROM prices {where} GROUP BY item_name, item_lvl, id",
            params
        )
        if df.empty:
            return {"rows": []}
        grouped = df.groupby(["item_name", "item_lvl"])["price"]
        rows = []
        for (name, lvl), prices in grouped:
            if len(prices) < 2:
                continue
            filtered = self._iqr_filter(prices)
            if len(filtered) < 2:
                filtered = prices
            mean_p = filtered.mean()
            std_p = filtered.std()
            cv = round(std_p / mean_p * 100, 1) if mean_p > 0 else 0
            rows.append({
                "item": name, "lvl": lvl,
                "ortalama": int(mean_p), "std": round(float(std_p), 0),
                "cv": cv, "min": int(filtered.min()), "max": int(filtered.max()),
                "adet": int(len(filtered)),
            })
        rows.sort(key=lambda x: x["cv"], reverse=True)
        return {"rows": rows[:limit]}

    def demand(self, server=None, limit=20):
        where, params = self._server_filter(server)
        df = self._read(
            f"SELECT item_name, COUNT(DISTINCT seller) as seller_count, COUNT(*) as listing_count "
            f"FROM prices {where} GROUP BY item_name ORDER BY listing_count DESC LIMIT ?",
            params + (limit,) if params else (limit,)
        )
        if df.empty:
            return {"rows": []}
        rows = []
        for _, r in df.iterrows():
            rows.append({
                "item": r["item_name"],
                "satici": int(r["seller_count"]),
                "ilan": int(r["listing_count"]),
            })
        return {"rows": rows}

    def distribution(self, server=None, bins=15):
        where, params = self._server_filter(server)
        df = self._read(f"SELECT price FROM prices {where}", params)
        if df.empty or len(df["price"]) < 2:
            return {"bins": [], "counts": []}
        prices = df["price"]
        counts, edges = pd.cut(prices, bins=bins, retbins=True)
        bin_counts = counts.value_counts().sort_index()
        labels = []
        values = []
        for interval, count in bin_counts.items():
            lo = int(interval.left)
            hi = int(interval.right)
            labels.append(f"{lo:,.0f}-{hi:,.0f}".replace(",", "."))
            values.append(int(count))
        return {"bins": labels, "counts": values}

    def trend(self, server=None, days=30):
        where, params = self._server_filter(server)
        df = self._read(
            f"SELECT item_name, item_lvl, price, timestamp FROM prices {where} "
            f"ORDER BY timestamp DESC",
            params
        )
        if df.empty:
            return {"rows": []}
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", format="mixed")
        df = df.dropna(subset=["timestamp"])
        if df.empty:
            return {"rows": []}

        grouped = df.groupby(["item_name", "item_lvl"])
        rows = []
        for (name, lvl), g in grouped:
            g = g.sort_values("timestamp")
            if len(g) < 2:
                continue
            filtered = self._iqr_filter(g["price"])
            if len(filtered) < 2:
                filtered = g["price"]
            first_price = filtered.iloc[0]
            last_price = filtered.iloc[-1]
            if first_price <= 0:
                continue
            degisim = round((last_price - first_price) / first_price * 100, 1)
            rows.append({
                "item": name, "lvl": lvl,
                "ilk_fiyat": int(first_price), "son_fiyat": int(last_price),
                "degisim": degisim, "adet": int(len(filtered)),
            })
        rows.sort(key=lambda x: abs(x["degisim"]), reverse=True)
        return {"rows": rows[:20]}

    def liquidity(self, server=None, limit=20):
        where, params = self._server_filter(server)
        df = self._read(
            f"SELECT item_name, COUNT(*) as ilan_sayisi, "
            f"COUNT(DISTINCT seller) as satici_sayisi, "
            f"MIN(timestamp) as ilk_tarih, MAX(timestamp) as son_tarih "
            f"FROM prices {where} GROUP BY item_name HAVING ilan_sayisi >= 2 ORDER BY ilan_sayisi DESC LIMIT ?",
            params + (limit,) if params else (limit,)
        )
        if df.empty:
            return {"rows": []}
        rows = []
        for _, r in df.iterrows():
            rows.append({
                "item": r["item_name"],
                "ilan": int(r["ilan_sayisi"]),
                "satici": int(r["satici_sayisi"]),
                "ilk": str(r["ilk_tarih"])[:10] if r["ilk_tarih"] else "",
                "son": str(r["son_tarih"])[:10] if r["son_tarih"] else "",
            })
        return {"rows": rows}
