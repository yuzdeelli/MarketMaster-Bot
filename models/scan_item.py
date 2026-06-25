from dataclasses import dataclass, field
from typing import List


@dataclass
class ScanItem:
    item: str
    lvls: List[str] = field(default_factory=list)

    def to_line(self) -> str:
        return f"{self.item}:{','.join(self.lvls)}"

    @staticmethod
    def from_line(line: str):
        if ":" in line:
            it, l_str = line.strip().split(":", 1)
            lvls = l_str.split(",")
            return ScanItem(item=it, lvls=lvls)
        return None
