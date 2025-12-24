import os
from pathlib import Path

import streamlit as st

import db
from agent import build_runtime, run_turn


st.set_page_config(page_title="PizzaBot", page_icon="🍕", layout="wide")


def money(pkr: int) -> str:
    return f"PKR {int(pkr):,}"


def ensure_state() -> None:
    if "chat" not in st.session_state:
        st.session_state.chat = []  # list[dict(role, content)]
    if "order_id" not in st.session_state:
        st.session_state.order_id = None


def main() -> None:
    ensure_state()

    st.title("PizzaBot – Order & Tracking")

    db_path = os.getenv("PIZZA_DB_PATH", "pizza.db")
    menu_path = os.getenv("PIZZA_MENU_PATH", "menu.json")

    # Build runtime once per session
    if "runtime" not in st.session_state:
        conn, menu, agent = build_runtime(db_path=db_path, menu_path=menu_path)
        st.session_state.runtime = {"conn": conn, "menu": menu, "agent": agent}

    conn = st.session_state.runtime["conn"]
    menu = st.session_state.runtime["menu"]
    agent = st.session_state.runtime["agent"]

    tab_chat, tab_admin = st.tabs(["Customer Chat", "Admin / Kitchen"])

    with tab_chat:
        left, right = st.columns([2, 1], gap="large")

        with left:
            st.subheader("Chat")

            for msg in st.session_state.chat:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            user_text = st.chat_input("Ask about menu, place an order, or check status...")
            if user_text:
                st.session_state.chat.append({"role": "user", "content": user_text})

                # Hint the agent about an existing order_id if present
                order_id = st.session_state.order_id
                if order_id:
                    user_text = f"(context: current order_id is {order_id})\n" + user_text

                result = run_turn(agent, user_text, chat_history=st.session_state.chat[:-1])
                assistant_text = result["output"]
                st.session_state.chat.append({"role": "assistant", "content": assistant_text})

                # Try to detect an order_id from tool usage (fallback: parse digits in response)
                # We keep this simple; user can also ask the bot: "what's my order id?"
                for token in assistant_text.split():
                    if token.isdigit():
                        st.session_state.order_id = int(token)
                        break

                st.rerun()

        with right:
            st.subheader("Menu")
            st.caption("Quick reference")
            for p in menu.pizzas:
                st.markdown(
                    f"**{p['name']}** ({p['id']})\n\n{p.get('description','')}\n\n"
                    f"S {money(p['sizes']['small'])} • M {money(p['sizes']['medium'])} • L {money(p['sizes']['large'])}"
                )
                st.divider()

            st.subheader("Current Order")
            if st.session_state.order_id:
                payload = db.get_order(conn, st.session_state.order_id)
                if payload:
                    order = payload["order"]
                    items = payload["items"]
                    delivery_fee = menu.delivery_fee if order["delivery_type"] == "delivery" else 0
                    totals = db.compute_totals(items, delivery_fee=delivery_fee, tax_percent=menu.tax_percent)

                    st.write(f"Order ID: {order['id']}")
                    st.write(f"Status: {order['status']}")
                    st.write(f"Type: {order['delivery_type']}")

                    st.markdown("**Items**")
                    if not items:
                        st.write("(No items yet)")
                    for it in items:
                        label = it["item_name"]
                        if it["size"]:
                            label += f" ({it['size']})"
                        st.write(f"- {it['qty']} × {label} @ {money(it['unit_price'])}")

                    st.markdown("**Totals**")
                    st.write(f"Subtotal: {money(totals.subtotal)}")
                    st.write(f"Delivery: {money(totals.delivery_fee)}")
                    st.write(f"Tax: {money(totals.tax)}")
                    st.write(f"Total: {money(totals.total)}")
                else:
                    st.warning("Order not found in DB")
            else:
                st.info("No active order yet. Start by telling the bot: 'I want delivery' or 'I want pickup'.")

    with tab_admin:
        st.subheader("Orders")
        orders = db.list_orders(conn, limit=50)
        st.dataframe(orders, use_container_width=True)

        st.subheader("Update status")
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            order_id = st.number_input("Order ID", min_value=1, step=1, value=1)
        with col2:
            status = st.selectbox(
                "Status",
                [
                    "placed",
                    "preparing",
                    "baking",
                    "out_for_delivery",
                    "delivered",
                    "ready_for_pickup",
                    "cancelled",
                ],
            )
        with col3:
            message = st.text_input("Message (optional)")

        if st.button("Apply update"):
            db.set_order_status(conn, int(order_id), status, message=message or None)
            st.success("Updated")

        st.subheader("View order")
        view_id = st.number_input("View Order ID", min_value=1, step=1, value=1, key="view_id")
        payload = db.get_order(conn, int(view_id))
        if payload:
            st.json(payload)
        else:
            st.info("No such order")


if __name__ == "__main__":
    main()
