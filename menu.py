import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Menu:
    data: dict[str, Any]

    @property
    def pizzas(self) -> list[dict[str, Any]]:
        return list(self.data.get("pizzas", []))

    @property
    def extras(self) -> list[dict[str, Any]]:
        return list(self.data.get("extras", []))

    @property
    def delivery_fee(self) -> int:
        return int(self.data.get("delivery_fee", 0))

    @property
    def tax_percent(self) -> float:
        return float(self.data.get("tax_percent", 0))


def load_menu(menu_path: str) -> Menu:
    raw = json.loads(Path(menu_path).read_text(encoding="utf-8"))
    return Menu(data=raw)


def format_menu_for_chat(menu: Menu) -> str:
    lines: list[str] = []
    lines.append("Menu (prices in PKR):")
    lines.append("\nPizzas:")
    for p in menu.pizzas:
        sizes = p.get("sizes", {})
        lines.append(
            f"- {p['name']} ({p['id']}): {p.get('description','')} | "
            f"S {sizes.get('small')} / M {sizes.get('medium')} / L {sizes.get('large')}"
        )
    lines.append("\nExtras:")
    for e in menu.extras:
        lines.append(f"- {e['name']} ({e['id']}): {e['price']}")
    lines.append(f"\nDelivery fee: {menu.delivery_fee}")
    return "\n".join(lines)


def find_pizza(menu: Menu, pizza_id: str) -> dict[str, Any] | None:
    pid = pizza_id.strip().lower()
    for p in menu.pizzas:
        if str(p.get("id", "")).lower() == pid:
            return p
    return None


def find_extra(menu: Menu, extra_id: str) -> dict[str, Any] | None:
    eid = extra_id.strip().lower()
    for e in menu.extras:
        if str(e.get("id", "")).lower() == eid:
            return e
    return None
