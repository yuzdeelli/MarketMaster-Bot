import sys
sys.path.insert(0, r'C:\Users\hort\Desktop\Market Master V - 1')
from core.engine import should_allow_zero

tests = [
    ("Spear of Murky Waters", False),
    ("Water of Bless", True),
    ("Water of Favors", True),
    ("Water of Ibexs", True),
    ("Blessed Upgrade Scroll", True),
    ("Iron Impact", False),
    ("Dark Vane", True),
]

for item, expected in tests:
    result = should_allow_zero(item)
    status = "OK" if result == expected else "HATA"
    print(f"{item:<30} {'YAZILIR' if result else 'ATLANIR':>10} | {status}")
