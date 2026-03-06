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

# Start Morning Briefing Scheduler
from scheduler_helper import start_scheduler
# Avoid running multiple times if using standard Flask reloader locally
if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
    start_scheduler()
# Initialize AI Brain (Claude API)
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
# Anthropic client will automatically pick up ANTHROPIC_API_KEY from environment,
# but passing it explicitly is a good practice.
anthropic_client = Anthropic(api_key=anthropic_api_key)

# Initialize Database Connection
database_url = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)

# Import calendar helper functions
from calendar_helper import get_todays_events, create_event

import datetime

# System Prompt defining Jarvis's persona
def get_system_prompt():
    # Set reference time to GMT-6 (Mexico City) 
    now_mx = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-6)))
    date_str = now_mx.strftime("%A, %Y-%m-%d %H:%M:%S GMT-6")
    
    return f"""You are a personal life assistant named "Jarvis" that helps with everything in the user's life.
You are concise, highly intelligent, and helpful. You receive messages via WhatsApp.

Today's exact current date and time in GMT-6 (Mexico timezone) is: {date_str}

You have access to tools that can check the user's Google Calendar and schedule new events.
If the user asks "qué tengo hoy" or "agenda", check their calendar using the get_todays_events tool.
If the user asks "agendar [evento] [fecha] [hora]" or "crea evento [descripción]", use the create_event tool to schedule it.
IMPORTANT: The create_event tool requires the summary, start_time, and end_time. 
If the user ONLY provides a start time (e.g. "mañana a las 3"), assume the event lasts for 1 hour by default to calculate the end_time.
If they don't provide a date or time at all, ask them for those details before calling the tool.
Always format start_time and end_time in proper ISO 8601 format with the correct timezone offset (e.g. 2024-05-20T15:00:00-06:00).
"""

# Define the tools Claude can use
CALENDAR_TOOLS = [
    {
        "name": "get_todays_events",
        "description": "Obtiene los eventos programados en el calendario para el día de hoy.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "create_event",
        "description": "Crea un nuevo evento en el calendario de Google en una fecha y hora específicas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "El título o resumen del evento (ej. 'Cita Médica')"
                },
                "start_time": {
                    "type": "string",
                    "description": "Fecha y hora de inicio en formato ISO 8601 (ej. '2024-05-20T10:00:00-06:00')"
                },
                "end_time": {
                    "type": "string",
                    "description": "Fecha y hora de fin en formato ISO 8601 (ej. '2024-05-20T11:00:00-06:00')"
                }
            },
            "required": ["summary", "start_time", "end_time"]
        }
    }
]

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
    history = get_conversation_history(sender_number, limit=5)
    
    # 2. Add the new incoming message to the conversation history
    history.append({
        "role": "user",
        "content": incoming_msg
    })
    
    try:
        # Step 1: Send the context to Claude API using claude-sonnet-4-6 model, providing the tools
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=get_system_prompt(),
            messages=history,
            tools=CALENDAR_TOOLS
        )
        
        # Check if Claude decided to use a tool
        if response.stop_reason == "tool_use":
            bot_reply = process_tool_use(response, history)
        else:
            bot_reply = response.content[0].text
            
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

def process_tool_use(response, history):
    """
    Handles executing the local tool and sending the result back to Claude
    to get the final natural language response.
    """
    tool_use_block = next((block for block in response.content if block.type == "tool_use"), None)
    
    if not tool_use_block:
        return "Hubo un error al procesar la herramienta del calendario."
        
    tool_name = tool_use_block.name
    tool_input = tool_use_block.input
    tool_id = tool_use_block.id
    
    # Append Claude's partial response (the tool_use request) to history
    history.append({
        "role": "assistant",
        "content": response.content
    })
    
    # Execute the actual function
    tool_result = None
    if tool_name == "get_todays_events":
        tool_result = get_todays_events()
    elif tool_name == "create_event":
        tool_result = create_event(
            summary=tool_input.get("summary"),
            start_time=tool_input.get("start_time"),
            end_time=tool_input.get("end_time")
        )
        
    # Append the result of the tool execution back to history
    history.append({
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": str(tool_result),
            }
        ]
    })
    
    # Get the final natural language response from Claude
    try:
        final_response = anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=get_system_prompt(),
            messages=history,
            tools=CALENDAR_TOOLS
        )
        
        return final_response.content[0].text
    except Exception as e:
        print(f"Error getting final response after tool use: {e}")
        return str(tool_result) # Fallback to just returning the raw tool output if NLP fails

# Healthcheck route useful for Render
@app.route("/", methods=["GET"])
def index():
    return "Jarvis AI WhatsApp Assistant is running!", 200

if __name__ == "__main__":
    # Bind to 0.0.0.0 to work on Render, read port from environment (Render sets PORT)
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
# updated
