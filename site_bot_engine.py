import sqlite3
from google import genai
from google.genai import types
import os

# --- PART 1: THE FAKE BACKEND (Database & Knowledge) ---

# We create a temporary database in RAM
conn = sqlite3.connect(":memory:", check_same_thread=False)
cursor = conn.cursor()

def init_db():
    """Sets up fake tables for our simulation."""
    # Create Tables
    cursor.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, stock INTEGER, price REAL)")
    cursor.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id TEXT, status TEXT, total REAL)")
    
    # Seed Data
    cursor.execute("INSERT INTO products VALUES (1, 'AI Widget Pro', 50, 99.00)")
    cursor.execute("INSERT INTO products VALUES (2, 'Neural Chip', 10, 499.00)")
    cursor.execute("INSERT INTO orders VALUES (101, 'client_alice', 'Shipped', 99.00)")
    cursor.execute("INSERT INTO orders VALUES (102, 'client_bob', 'Processing', 499.00)")
    cursor.execute("INSERT INTO orders VALUES (103, 'client_alice', 'Delivered', 198.00)")
    conn.commit()
    print("✅ System: Database initialized with fake products and orders.")

# The Static Knowledge Base (for Visitors)
KNOWLEDGE_BASE = """
We are 'FutureTech Solutions'.
Open Mon-Fri, 9am-5pm.
Contact: support@futuretech.com.
We sell AI hardware for enthusiasts.
Returns are accepted within 30 days.
"""

# --- PART 2: THE TOOLS (The Hands) ---

def search_knowledge_base(query: str):
    """Searches general company info (Hours, policies, contact)."""
    print(f"\n[TOOL] Reading Knowledge Base for: {query}")
    # In a real app, this would be a Vector Search. For now, we return the whole text.
    return KNOWLEDGE_BASE

def get_my_orders(user_id: str):
    """Returns order status for a specific logged-in user."""
    print(f"\n[TOOL] Querying SQL for User: {user_id}")
    res = cursor.execute("SELECT id, status, total FROM orders WHERE user_id=?", (user_id,))
    rows = res.fetchall()
    if not rows:
        return "No orders found."
    return f"Found {len(rows)} orders: " + ", ".join([f"Order #{r[0]} ({r[1]}) - ${r[2]}" for r in rows])

def get_admin_sales_report():
    """Returns total sales revenue (ADMIN ONLY)."""
    print(f"\n[TOOL] 🔒 EXECUTING ADMIN SQL REPORT...")
    res = cursor.execute("SELECT SUM(total), COUNT(*) FROM orders")
    row = res.fetchone()
    return f"Total Revenue: ${row[0]}, Total Orders: {row[1]}"

def check_inventory():
    """Checks current product stock levels (ADMIN ONLY)."""
    print(f"\n[TOOL] 🔒 Checking Inventory...")
    res = cursor.execute("SELECT name, stock FROM products")
    return str(res.fetchall())

# --- PART 3: THE ROUTER (The Brain Switcher) ---

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

def get_bot_response(user_role: str, user_id: str, message: str):
    """
    Decides WHICH brain and WHICH tools to use based on the user's role.
    This is the core architectural innovation.
    """
    
    tools = []
    system_instruction = ""
    
    # BRAIN 1: The Receptionist (Visitor)
    if user_role == "visitor":
        tools = [search_knowledge_base]
        system_instruction = "You are a polite Receptionist. Answer general questions. If asked about orders, ask them to log in."
        
    # BRAIN 2: The Account Manager (Client)
    elif user_role == "client":
        # We wrap the tool to inject the user_id automatically (Security Best Practice)
        # This prevents Alice from asking for Bob's orders.
        def safe_get_orders():
            """Gets orders for the current user."""
            return get_my_orders(user_id)
            
        tools = [search_knowledge_base, safe_get_orders]
        system_instruction = f"You are a Support Agent helping {user_id}. You can check their specific orders."
        
    # BRAIN 3: The General Manager (Admin)
    elif user_role == "admin":
        tools = [search_knowledge_base, get_admin_sales_report, check_inventory]
        system_instruction = "You are the General Manager. You have full access to sales data and inventory. Be concise."

    # Generate Response
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=message,
        config=types.GenerateContentConfig(
            tools=tools,
            system_instruction=system_instruction,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False)
        )
    )
    return response.text

# --- PART 4: THE SIMULATION LOOP ---

if __name__ == "__main__":
    init_db()
    print("-" * 50)
    print("🤖 INTELLIGENT SITE BOT ENGINE LOADED")
    print("Roles: 'visitor', 'client', 'admin'")
    print("-" * 50)

    while True:
        print("\n--- NEW SESSION ---")
        role = input("Who are you? (visitor/client/admin): ").lower().strip()
        if role not in ['visitor', 'client', 'admin']:
            print("Invalid role. Try again.")
            continue
            
        current_user = "guest"
        if role == "client":
            current_user = "client_alice" # Simulate Alice logging in
            print(f"(Logged in as {current_user})")
        
        while True:
            msg = input(f"\n{role.upper()} > ")
            if msg.lower() in ["quit", "switch"]:
                break
                
            try:
                answer = get_bot_response(role, current_user, msg)
                print(f"Bot: {answer}")
            except Exception as e:
                print(f"Error: {e}")
