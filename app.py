import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from anthropic import Anthropic
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
load_dotenv()

app = Flask(__name__)

# Initialize AI Brain (Claude API)
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
# Anthropic client will automatically pick up ANTHROPIC_API_KEY from environment,
# but passing it explicitly is a good practice.
anthropic_client = Anthropic(api_key=anthropic_api_key)

# Initialize Database Connection
database_url = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)

# System Prompt defining Jarvis's persona
SYSTEM_PROMPT = """You are a personal life assistant named "Jarvis" that helps with everything in the user's life.
You are concise, highly intelligent, and helpful. You receive messages via WhatsApp.
"""

def get_conversation_history(phone_number, limit=5):
    """
    Fetches the context of the conversation from Supabase.
    We fetch the last `limit` rows (which equals 10 messages: 5 user + 5 bot responses).
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Fetch the most recent rows for this phone_number
        cur.execute(
            "SELECT * FROM messages WHERE phone_number = %s ORDER BY timestamp DESC LIMIT %s",
            (phone_number, limit)
        )
        messages = cur.fetchall()
        
        # Reverse the list so the oldest messages come first, newest last (chronological order)
        messages = messages[::-1]
        
        history = []
        for msg in messages:
            history.append({"role": "user", "content": msg["user_message"]})
            history.append({"role": "assistant", "content": msg["bot_response"]})
            
        cur.close()
        conn.close()
        return history
    except Exception as e:
        print(f"Error fetching history from Database: {e}")
        return []

def save_message(phone_number, user_message, bot_response):
    """
    Saves the user's message and the bot's response to the Supabase database.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Insert row into the DB; timestamp is automatically set by Postgres
        cur.execute(
            "INSERT INTO messages (phone_number, user_message, bot_response) VALUES (%s, %s, %s)",
            (phone_number, user_message, bot_response)
        )
        conn.commit()
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error saving message to Database: {e}")

@app.route("/webhook", methods=["POST"])
def webhook():
    """
    1. Receive incoming WhatsApp messages via Twilio webhook (POST /webhook).
    """
    incoming_msg = request.values.get("Body", "").strip()
    sender_number = request.values.get("From", "")
    
    # Clean the sender number (Twilio usually sends it in the format: whatsapp:+1234567890)
    if sender_number.startswith("whatsapp:"):
        sender_number = sender_number.replace("whatsapp:", "")

    # If message is empty for some reason, ignore it
    if not incoming_msg:
        return "No message body", 200

    # 5. The assistant should remember context of the last 10 messages
    # Get the last 5 conversation pairs (equals 10 messages)
    history = get_conversation_history(sender_number, limit=5)
    
    # 2. Add the new incoming message to the conversation history
    history.append({
        "role": "user",
        "content": incoming_msg
    })
    
    # Send the context to Claude API using claude-sonnet-4-6 model
    try:
        claude_response = anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=history
        )
        bot_reply = claude_response.content[0].text
    except Exception as e:
        print(f"Error generating response from Claude: {e}")
        bot_reply = "I'm sorry, my brain is having trouble processing that right now. Please try again soon!"
    
    # 4. Save to Database (table: messages)
    save_message(sender_number, incoming_msg, bot_reply)
    
    # 3. Response gets sent back to the user via WhatsApp through Twilio
    resp = MessagingResponse()
    msg = resp.message()
    msg.body(bot_reply)
    
    return str(resp)

# Healthcheck route useful for Render
@app.route("/", methods=["GET"])
def index():
    return "Jarvis AI WhatsApp Assistant is running!", 200

if __name__ == "__main__":
    # Bind to 0.0.0.0 to work on Render, read port from environment (Render sets PORT)
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
# updated
