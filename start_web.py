import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from webapp.app import app
app.run(host="0.0.0.0", port=8765, debug=False)
