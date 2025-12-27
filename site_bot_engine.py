import streamlit as st
import sqlite3
import datetime
from google import genai
from google.genai import types
import os

# --- PAGE CONFIG ---
st.set_page_config(page_title="Intelligent Site Bot", layout="wide")
st.title("🤖 3-Brain Business Bot")

# --- PART 1: THE PERSISTENT DATABASE ---
# We use @st.cache_resource so the DB isn't wiped every time you click a button
@st.cache_resource
def get_db_connection():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    cursor = conn.cursor()
    
    # Init Tables
    cursor.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, stock INTEGER, price REAL)")
    cursor.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id TEXT, status TEXT, total REAL)")
    
    # Seed Data
    cursor.execute("INSERT INTO products VALUES (1, 'AI Widget Pro', 50, 99.00)")
    cursor.execute("INSERT INTO products VALUES (2, 'Neural Chip', 10, 499.00)")
    cursor.execute("INSERT INTO orders VALUES (101, 'client_alice', 'Shipped', 99.00)")
    cursor.execute("INSERT INTO orders VALUES (102, 'client_bob', 'Processing', 499.00)")
    cursor.execute("INSERT INTO orders VALUES (103, 'client_alice', 'Delivered', 198.00)")
    conn.commit()
    return conn

conn = get_db_connection()
cursor = conn.cursor()

# Knowledge Base
KNOWLEDGE_BASE = """
We are 'FutureTech Solutions'.
Open Mon-Fri, 9am-5pm.
Contact: support@futuretech.com.
We sell AI hardware for enthusiasts.
Returns are accepted within 30 days.
"""

# --- PART 2: THE TOOLS ---
def search_knowledge_base(query: str):
    return KNOWLEDGE_BASE

def get_my_orders(user_id: str):
    # Note: We use the cursor from the global scope/cached connection
    res = cursor.execute("SELECT id, status, total FROM orders WHERE user_id=?", (user_id,))
    rows = res.fetchall()
    if not rows:
        return "No orders found."
    return f"Found {len(rows)} orders: " + ", ".join([f"Order #{r[0]} ({r[1]}) - ${r[2]}" for r in rows])

def get_admin_sales_report():
    res = cursor.execute("SELECT SUM(total), COUNT(*) FROM orders")
    row = res.fetchone()
    return f"Total Revenue: ${row[0]}, Total Orders: {row[1]}"

def check_inventory():
    res = cursor.execute("SELECT name, stock FROM products")
    return str(res.fetchall())

# --- PART 3: THE ROUTER & UI ---

# Get API Key
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    api_key = os.environ.get("GOOGLE_API_KEY")

if not api_key:
    st.error("API Key missing.")
    st.stop()

client = genai.Client(api_key=api_key)

# Sidebar: Role Selection (The "Login" Simulation)
st.sidebar.header("Identity Simulation")
role = st.sidebar.radio("Who are you?", ["Visitor", "Client (Alice)", "Admin"])

# Map UI selection to internal role IDs
user_role = "visitor"
current_user_id = "guest"
input_placeholder = "Ask about opening hours, returns, or products..." # <--- Custom Text

if role == "Client (Alice)":
    user_role = "client"
    current_user_id = "client_alice"
    input_placeholder = "Ask 'Where is my order?' or about policies..." # <--- Custom Text
elif role == "Admin":
    user_role = "admin"
    current_user_id = "admin"
    input_placeholder = "Ask for sales reports, inventory, or revenue..." # <--- Custom Text

st.sidebar.info(f"Active Role: **{user_role.upper()}**")
if user_role == "client":
    st.sidebar.success(f"Logged in as: {current_user_id}")

# Chat Interface
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input(input_placeholder):
    # 1. User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

# 2. Router Logic
    tools = []
    sys_instruct = ""
    
    # Get current time string (e.g., "Monday, 14:30")
    now_str = datetime.datetime.now().strftime("%A, %H:%M")

    # Define the "Base Identity" that applies to everyone
    # We tell it: You do NOT know the hours. You MUST search.
    base_identity = f"""
    Current Day/Time: {now_str}. 
    You represent 'FutureTech Solutions'.
    CRITICAL: For questions about hours, policies, or contact info, you MUST use the 'search_knowledge_base' tool. 
    Do not guess.
    """

    if user_role == "visitor":
        tools = [search_knowledge_base]
        sys_instruct = base_identity + " You are a Receptionist. Answer general questions. Do not discuss specific orders."
        
    elif user_role == "client":
        def safe_get_orders(): 
            return get_my_orders(current_user_id)
        tools = [search_knowledge_base, safe_get_orders]
        sys_instruct = base_identity + f" You are a Support Agent helping {current_user_id}. You can check their orders."
        
    elif user_role == "admin":
        tools = [search_knowledge_base, get_admin_sales_report, check_inventory]
        sys_instruct = base_identity + " You are the General Manager. You have full access."
        
    # 3. Generate Response
    with st.chat_message("assistant"):
        with st.spinner(f"Thinking as {user_role}..."):
            try:
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        tools=tools,
                        system_instruction=sys_instruct,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False)
                    )
                )
                st.markdown(response.text)
                st.session_state.messages.append({"role": "model", "content": response.text})
            except Exception as e:
                st.error(f"Error: {e}")
