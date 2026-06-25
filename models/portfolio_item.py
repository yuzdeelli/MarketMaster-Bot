from dataclasses import dataclass, field
from typing import List


@dataclass
class PortfolioItem:
    name: str
    lvl: str
    buy_price: float = 0.0
    buy_strategy: str = "Auto"
    count: int = 1
    sell_strategy: str = "Auto"

    def to_line(self) -> str:
        return f"{self.name}|{self.lvl}|{self.buy_price}|{self.buy_strategy}|{self.count}|{self.sell_strategy}"

    @staticmethod
    def from_line(line: str):
        parts = line.strip().split("|")
        if len(parts) >= 3:
            name = parts[0]
            lvl = parts[1]
            buy_price = float(parts[2])
            buy_strat = parts[3] if len(parts) > 3 else "Auto"
            count = int(parts[4]) if len(parts) > 4 else 1
            sell_strat = parts[5] if len(parts) > 5 else "Auto"
            return PortfolioItem(name, lvl, buy_price, buy_strat, count, sell_strat)
        return None
