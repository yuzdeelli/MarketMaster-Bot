import os
import sys
import json

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, BASE_DIR)

from flask import Flask, render_template, jsonify

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "webapp", "templates"), static_folder=os.path.join(BASE_DIR, "webapp", "static"))
app.config['TEMPLATES_AUTO_RELOAD'] = True


@app.route("/")
def index():
    return render_template("portfoy.html", items=[], servers=[], slogan_lines=["", ""])


@app.route("/portfoy")
def portfoy_page():
    from webapp.portfolio import load_items, compute_row
    from webapp.database import get_unique_servers

    all_raw = load_items()
    items = [compute_row(it) for it in all_raw]
    servers = get_unique_servers()

    slogan_lines = ["Buy ", "Buy "]
    for i, it in enumerate(all_raw[:9]):
        line_idx = 0 if i < 4 else 1
        bp = int(it.get('buy_price', 0))
        name = it['name']
        if name == 'Blue Treasure Chest':
            name = 'blue box'
        elif name == 'Green Treasure Chest':
            name = 'green box'
        else:
            for suffix in [' Supply Box', ' Gemstone', ' Treasure Chest', ' gem']:
                name = name.replace(suffix, '')
        part = f"{name} {bp:,}"
        if slogan_lines[line_idx] != "Buy ":
            slogan_lines[line_idx] += " / " + part
        else:
            slogan_lines[line_idx] += part

    return render_template("portfoy.html", items=items, servers=servers, slogan_lines=slogan_lines)


@app.route("/api/portfoy/export-csv")
def portfoy_export_csv():
    from webapp.portfolio import load_items
    from webapp.database import get_unique_servers, get_item_stats_for_server

    items = load_items()
    servers = get_unique_servers()

    import csv, io
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    header = ["Item", "Level", "Alis", "Strateji", "Adet", "Satis Stratejisi"] + [f"Fiyat ({s})" for s in servers]
    writer.writerow(header)

    for it in items:
        markets = {}
        for srv in servers:
            stats = get_item_stats_for_server(it["name"], it["lvl"], srv)
            markets[srv] = stats["sell"]["median"] if stats and stats.get("sell") else 0
        row = [it["name"], it["lvl"], it.get("buy_price", 0), it.get("buy_strategy", "Auto"),
               it.get("count", 1), it.get("sell_strategy", "Auto")]
        row += [markets[s] for s in servers]
        writer.writerow(row)

    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=portfoy_export.csv"}
    )


if __name__ == "__main__":
    config_path = os.path.join(BASE_DIR, "analyzer_config.json")
    port = 9000
    try:
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                cfg = json.load(f)
            port = cfg.get("portfolio_port", 9000)
    except:
        pass
    print(f"Portfolio sunucusu baslatiliyor... http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
