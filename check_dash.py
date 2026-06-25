import re
from webapp.app import app

with app.test_client() as c:
    r = c.get('/dashboard')
    html = r.data.decode()

    # Find all IDs in HTML
    html_ids = set(re.findall(r'id="([^"]+)"', html))

    # Find all getElementById calls
    for m in re.findall(r"""getElementById\(['"]([^'"]+)['"]\)""", html):
        if m not in html_ids:
            print(f"MISSING ID: {m}")

    # Check for LightningCharts reference without LightweightCharts CDN
    if 'LightweightCharts' in html and 'lightweight-charts' not in html:
        print("WARNING: LightweightCharts used but CDN not loaded")

    print(f"HTML IDs found: {sorted(html_ids)}")
    print(f"Total lines: {html.count(chr(10))}")
