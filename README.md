# PizzaBot – AI-Powered Pizza Ordering System

A comprehensive pizza ordering chatbot built with **OpenAI Agents SDK** (Gemini 2.5 Flash), **SQLite**, and **Streamlit**. The agent autonomously handles menu discussions, order placement, and status tracking using tools connected to a persistent database.

---

## Features

✅ **Agentic Chat Interface**
- AI-powered conversation using Gemini 2.5 Flash via OpenAI-compatible API
- Multi-turn dialogue with context awareness
- Tool-calling for real-time order/menu operations

✅ **Order Management**
- Create & manage pizza orders (draft → placed → preparing → delivered/pickup)
- Add pizzas with size selection & quantity
- Add extras (toppings, dips, etc.)
- Remove items
- Auto-calculate totals (subtotal, delivery fee, tax)

✅ **Menu System**
- 4 pre-loaded pizzas (Margherita, Pepperoni, BBQ Chicken, Veggie)
- Configurable extras & pricing (PKR)
- JSON-based menu for easy customization

✅ **Dual-Tab UI (Streamlit)**
- **Customer Chat Tab**: Chat with the bot, place orders, track status
- **Admin Tab**: View all orders, update status (placed → baking → out_for_delivery → delivered), view order details

✅ **Database**
- SQLite for customers, orders, items, and status updates
- Full CRUD operations via agent tools
- Foreign key constraints & automatic cleanup

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **LLM** | Gemini 2.5 Flash (via OpenAI-compatible endpoint) |
| **Agent Framework** | OpenAI Agents SDK (Python) |
| **UI** | Streamlit |
| **Database** | SQLite3 |
| **Config** | python-dotenv |
| **Runtime** | Conda (Python 3.13) |

---

## Quick Start

### 1. Clone & Setup Environment

```bash
cd smit-agentic-ai

# Create Conda environment
conda create -y -n smit-chatbot-project python=3.13

# Activate it
conda activate smit-chatbot-project

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Gemini API Key

Copy the example env file and add your key:

```bash
cp .env.example .env
# Edit .env and set GEMINI_API_KEY=<your_key_from_google_ai_studio>
```

**Get a free Gemini API key:** https://aistudio.google.com/apikey

### 3. Run the App

```bash
streamlit run app.py
```

Open **http://localhost:8501** in your browser.

---

## Project Structure

```
smit-agentic-ai/
├── app.py                 # Streamlit UI (Customer chat + Admin panel)
├── agent.py              # OpenAI Agents SDK agent + tools
├── db.py                 # SQLite CRUD + schema
├── menu.py               # Menu loader & helpers
├── menu.json             # Pizza & extras catalog
├── pizza.db              # SQLite database (auto-created)
├── requirements.txt      # Python dependencies
├── .env.example           # Template for env vars
├── .env                  # (Create this) Your API key
└── README.md             # This file
```

---

## Architecture

### Agent Wiring

```python
# OpenAI Agents SDK pattern (from agent.py)
external_client = AsyncOpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

llm_model = OpenAIChatCompletionsModel(
    model="gemini-2.5-flash",
    openai_client=external_client,
)

agent = Agent(
    name="PizzaBot",
    instructions="Help customers order pizza...",
    model=llm_model,
    tools=[get_menu, start_order, add_pizza, add_extra, checkout, get_order_status, ...],
)

result = Runner.run_sync(starting_agent=agent, input=user_message)
```

### Database Schema

```sql
-- Customers
CREATE TABLE customers (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  phone TEXT,
  created_at TEXT
);

-- Orders
CREATE TABLE orders (
  id INTEGER PRIMARY KEY,
  customer_id INTEGER,
  status TEXT,           -- draft | placed | preparing | baking | out_for_delivery | delivered | ready_for_pickup
  delivery_type TEXT,    -- delivery | pickup
  address TEXT,
  notes TEXT,
  created_at TEXT,
  updated_at TEXT,
  FOREIGN KEY(customer_id) REFERENCES customers(id)
);

-- Order Items
CREATE TABLE order_items (
  id INTEGER PRIMARY KEY,
  order_id INTEGER NOT NULL,
  item_type TEXT,        -- pizza | extra
  item_id TEXT,
  item_name TEXT,
  size TEXT,             -- small | medium | large
  qty INTEGER,
  unit_price INTEGER,    -- in PKR
  created_at TEXT,
  FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
);

-- Status Updates
CREATE TABLE order_updates (
  id INTEGER PRIMARY KEY,
  order_id INTEGER,
  status TEXT,
  message TEXT,
  created_at TEXT,
  FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
);
```

---

## Agent Tools

The Gemini agent has access to these tools:

| Tool | Parameters | Returns |
|------|-----------|---------|
| `get_menu()` | — | Menu items, prices, delivery fee |
| `start_order(delivery_type, customer_name?, phone?, address?)` | delivery_type: "delivery" \| "pickup" | order_id |
| `add_pizza(order_id, pizza_id, size, qty)` | — | Updated order with items |
| `add_extra(order_id, extra_id, qty)` | — | Updated order with items |
| `remove_item(order_item_id)` | — | {ok: true} |
| `checkout(order_id)` | — | {order, totals} – finalizes to "placed" |
| `get_order_status(order_id)` | — | Full order + items + updates |
| `admin_update_status(order_id, status, message?)` | status: placed \| preparing \| ... | Updated order |

---

## Usage Examples

### Customer Interaction

**User:** "Hi, I want to order pizza for delivery"

**Bot:** "Great! I'd be happy to help you order pizza for delivery. Let me get the menu... Here's what we have: [shows pizzas & extras]. What would you like to order?"

**User:** "2 large Margheritas and 1 medium Pepperoni, plus extra cheese"

**Bot:** [Uses `start_order()`, `add_pizza()`, `add_extra()`, calculates totals]  
"Perfect! Here's your order summary:  
- 2 × Margherita (Large) @ 1,399 each  
- 1 × Pepperoni (Medium) @ 1,199  
- 1 × Extra cheese @ 150  
**Subtotal:** 4,147 | **Delivery:** 200 | **Total:** 4,347 PKR  
Please confirm to place?"

**User:** "Yes, confirm it"

**Bot:** [Calls `checkout()`, sets status to "placed"]  
"Order #42 placed! You'll receive updates as we prepare your pizza. Expected delivery: 30 mins."

### Admin Action

In the **Admin Tab**, select order #42 and change status to "baking" with message "Your pizza is now in the oven!" – customer can query status anytime.

---

## Customization

### Change Menu

Edit `menu.json`:

```json
{
  "pizzas": [
    {
      "id": "custom_pizza",
      "name": "My Pizza",
      "description": "Custom toppings",
      "sizes": {"small": 500, "medium": 750, "large": 1000}
    }
  ],
  "extras": [...],
  "delivery_fee": 200,
  "tax_percent": 0
}
```

### Modify Agent Behavior

Edit the `instructions` in `agent.py`:

```python
system = """
You are MyBot, ...
[Customize tone, behavior, etc.]
"""
```

### Add More Tools

Define new `@function_tool` in `build_agent()`:

```python
@function_tool
def my_custom_tool(param: str) -> dict:
    """Tool description for the agent."""
    return {"result": ...}

agent = Agent(..., tools=[..., my_custom_tool])
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | (required) | Your Google Gemini API key |
| `GEMINI_MODEL` | gemini-2.5-flash | LLM model name |
| `GEMINI_OPENAI_BASE_URL` | https://generativelanguage.googleapis.com/v1beta/openai/ | OpenAI-compatible endpoint |
| `PIZZA_DB_PATH` | pizza.db | SQLite database file path |
| `PIZZA_MENU_PATH` | menu.json | Menu JSON file path |

---

## Troubleshooting

### "GEMINI_API_KEY not found"
- Ensure `.env` exists in the project root
- Check the key is valid (from https://aistudio.google.com/apikey)
- Restart the Streamlit app after adding the key

### "Order not found in DB"
- Verify `pizza.db` was created (check file system)
- Check DB permissions in the project folder
- Try deleting `pizza.db` to auto-reinit on next run

### Streamlit "module not found"
- Ensure Conda env is activated: `conda activate smit-chatbot-project`
- Reinstall deps: `pip install -r requirements.txt`

### Agent hangs or slow responses
- Check Gemini API quota/limits
- Increase `max_turns` in `app.py` if needed
- Check network connectivity to `generativelanguage.googleapis.com`

---

## Future Enhancements

- [ ] Payment integration (Stripe, JazzCash)
- [ ] SMS/WhatsApp notifications for order updates
- [ ] Loyalty program (points, discounts)
- [ ] Delivery tracking map
- [ ] Multi-language support
- [ ] Inventory management tool (stock levels)

---

## License

MIT License – feel free to use & modify for your pizza shop!

---

## Support

For issues or questions:
1. Check this README
2. Review the OpenAI Agents SDK docs: https://github.com/openai/openai-agents-python
3. Check Gemini API docs: https://ai.google.dev/

**Happy pizza ordering! 🍕**
