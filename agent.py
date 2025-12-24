import os
from typing import Any

from dotenv import find_dotenv, load_dotenv

from agents import Agent, AsyncOpenAI, OpenAIChatCompletionsModel, Runner, function_tool

import db
from menu import Menu, find_extra, find_pizza, format_menu_for_chat, load_menu


def build_model() -> OpenAIChatCompletionsModel:
    # Gemini OpenAI-compatible endpoint
    # Docs: https://ai.google.dev/ (OpenAI compatibility)
    base_url = os.getenv(
        "GEMINI_OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing. Put it in .env or your environment.")

    external_client: AsyncOpenAI = AsyncOpenAI(api_key=api_key, base_url=base_url)
    llm_model: OpenAIChatCompletionsModel = OpenAIChatCompletionsModel(
        model=model,
        openai_client=external_client,
    )
    return llm_model


def build_agent(conn, menu: Menu) -> Agent:
    system = """
You are PizzaBot, a friendly and efficient pizza ordering assistant.

You must:
- Help the user explore the menu, answer questions, and recommend items.
- Take an order end-to-end: delivery/pickup, address if delivery, items, quantities, sizes, extras, notes.
- Confirm the order summary and total before placing.
- Provide order status updates when asked.

Tooling rules:
- Use tools to read menu, create/update orders, and fetch status.
- Never invent prices; always use the menu/tool results.
- Ask short clarifying questions when required (size/qty/address).

Status flow suggestion:
- draft -> placed -> preparing -> baking -> out_for_delivery -> delivered (or ready_for_pickup)
""".strip()

    @function_tool
    def get_menu() -> dict[str, Any]:
        """Return the current menu and fees."""
        return {
            "menu_text": format_menu_for_chat(menu),
            "delivery_fee": menu.delivery_fee,
            "tax_percent": menu.tax_percent,
            "pizzas": menu.pizzas,
            "extras": menu.extras,
        }

    @function_tool
    def start_order(delivery_type: str, customer_name: str | None = None, phone: str | None = None, address: str | None = None, notes: str | None = None) -> dict[str, Any]:
        """Create a new draft order and return order_id."""
        delivery_type = delivery_type.strip().lower()
        if delivery_type not in {"delivery", "pickup"}:
            raise ValueError("delivery_type must be 'delivery' or 'pickup'")

        customer_id = None
        if customer_name and customer_name.strip():
            customer_id = db.create_customer(conn, customer_name, phone)

        order_id = db.create_order(conn, customer_id, delivery_type, address=address, notes=notes)
        return {"order_id": order_id}

    @function_tool
    def add_pizza(order_id: int, pizza_id: str, size: str, qty: int = 1) -> dict[str, Any]:
        """Add a pizza item to an order."""
        size = size.strip().lower()
        if size not in {"small", "medium", "large"}:
            raise ValueError("size must be one of: small, medium, large")
        pizza = find_pizza(menu, pizza_id)
        if not pizza:
            raise ValueError(f"Unknown pizza_id: {pizza_id}")
        unit_price = int(pizza["sizes"][size])
        db.add_order_item(
            conn,
            order_id=int(order_id),
            item_type="pizza",
            item_id=str(pizza["id"]),
            item_name=str(pizza["name"]),
            size=size,
            qty=int(qty),
            unit_price=unit_price,
        )
        return db.get_order(conn, int(order_id)) or {"error": "order not found"}

    @function_tool
    def add_extra(order_id: int, extra_id: str, qty: int = 1) -> dict[str, Any]:
        """Add an extra item to an order."""
        extra = find_extra(menu, extra_id)
        if not extra:
            raise ValueError(f"Unknown extra_id: {extra_id}")
        db.add_order_item(
            conn,
            order_id=int(order_id),
            item_type="extra",
            item_id=str(extra["id"]),
            item_name=str(extra["name"]),
            size=None,
            qty=int(qty),
            unit_price=int(extra["price"]),
        )
        return db.get_order(conn, int(order_id)) or {"error": "order not found"}

    @function_tool
    def remove_item(order_item_id: int) -> dict[str, Any]:
        """Remove an order item by its order_item_id."""
        db.remove_order_item(conn, int(order_item_id))
        return {"ok": True}

    @function_tool
    def checkout(order_id: int) -> dict[str, Any]:
        """Finalize the order: set status to placed and return totals."""
        payload = db.get_order(conn, int(order_id))
        if not payload:
            raise ValueError("Order not found")

        order = payload["order"]
        if not payload["items"]:
            raise ValueError("Order has no items")

        delivery_fee = menu.delivery_fee if order["delivery_type"] == "delivery" else 0
        totals = db.compute_totals(payload["items"], delivery_fee=delivery_fee, tax_percent=menu.tax_percent)

        db.set_order_status(conn, int(order_id), "placed", message="Order placed")
        return {"order": db.get_order(conn, int(order_id)), "totals": totals.__dict__}

    @function_tool
    def get_order_status(order_id: int) -> dict[str, Any]:
        """Get an order along with status updates."""
        payload = db.get_order(conn, int(order_id))
        if not payload:
            raise ValueError("Order not found")
        return payload

    @function_tool
    def admin_update_status(order_id: int, status: str, message: str | None = None) -> dict[str, Any]:
        """Admin tool: update order status."""
        db.set_order_status(conn, int(order_id), status.strip().lower(), message=message)
        return db.get_order(conn, int(order_id)) or {"error": "order not found"}

    model = build_model()
    return Agent(
        name="PizzaBot",
        instructions=system,
        model=model,
        tools=[
            get_menu,
            start_order,
            add_pizza,
            add_extra,
            remove_item,
            checkout,
            get_order_status,
            admin_update_status,
        ],
    )


def run_turn(agent: Agent, user_message: str, chat_history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    # Runner.run_sync supports either a plain string input or a list of message items.
    # We pass a list so the agent can maintain conversation.
    messages: list[dict[str, str]] = []
    if chat_history:
        messages.extend(chat_history)
    messages.append({"role": "user", "content": user_message})

    result = Runner.run_sync(starting_agent=agent, input=messages)
    return {
        "output": getattr(result, "final_output", None) or str(result),
        "raw": result,
    }


def load_env() -> None:
    load_dotenv(find_dotenv(), override=True)


def build_runtime(db_path: str, menu_path: str) -> tuple[Any, Menu, Agent]:
    load_env()
    conn = db.connect(db_path)
    db.init_db(conn)
    menu = load_menu(menu_path)
    agent = build_agent(conn, menu)
    return conn, menu, agent
