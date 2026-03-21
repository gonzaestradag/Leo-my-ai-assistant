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

# Import calendar and gmail helper functions
from calendar_helper import get_todays_events, create_event
from gmail_helper import get_recent_unread_emails, get_urgent_emails, send_email
from finance_helper import set_salary, get_balance, add_fixed_expense, add_position, remove_position, get_portfolio_summary, add_expense, get_expenses_summary

import datetime

# System Prompt defining Jarvis's persona
def get_system_prompt():
    # Set reference time to GMT-6 (Mexico City) 
    now_mx = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-6)))
    date_str = now_mx.strftime("%A, %Y-%m-%d %H:%M:%S GMT-6")
    
    return f"""You are a personal life assistant named "Jarvis" that helps with everything in the user's life.
You are concise, highly intelligent, and helpful. You receive messages via WhatsApp.

Today's exact current date and time in GMT-6 (Mexico timezone) is: {date_str}

You have access to tools that can check the user's Google Calendar, schedule new events, and check their Gmail inbox.
If the user asks "qué tengo hoy" or "agenda", check their calendar using the get_todays_events tool.
If the user asks "agendar [evento] [fecha] [hora]" or "crea evento [descripción]", use the create_event tool to schedule it.
IMPORTANT: The create_event tool requires the summary, start_time, and end_time. 
If the user ONLY provides a start time (e.g. "mañana a las 3"), assume the event lasts for 1 hour by default to calculate the end_time.
If they don't provide a date or time at all, ask them for those details before calling the tool.
Always format start_time and end_time in proper ISO 8601 format with the correct timezone offset (e.g. 2024-05-20T15:00:00-06:00).
If the user asks "emails" or "correos", check their recent unread emails using the get_recent_unread_emails tool.
If the user asks "email urgente", check their important emails using the get_urgent_emails tool.
Si el usuario dice "envía un email a [email] con asunto [asunto] diciéndole que: [mensaje]", usa el tool send_email
If user says 'guarda contacto: [nombre], email: [email]', use save_contact tool.
If user says 'manda email a [nombre]', use send_email_to_contact tool.
If user asks about a contact, use get_contact tool.
If user says 'agrega tarea: [tarea]' or 'agregar pendiente: [tarea]', use add_task.
If user says 'mis tareas' or 'pendientes de hoy', use get_tasks.
If user says 'listo #[id]' or 'cumplí #[id]', use complete_task with completed=True.
If user says 'no cumplí #[id]', use complete_task with completed=False.
If user says 'esta semana recibí $X' or 'mi sueldo es $X', use set_salary tool.
If user says 'cuánto me queda' or 'mi balance', use get_balance tool.
If user says 'agrega gasto fijo: [nombre] $[monto] [frecuencia]', use add_fixed_expense tool.
If user says 'gasté $X en [categoria]' or 'agrega gasto', use add_expense tool.
If user says 'mis gastos', use get_expenses tool.
If user says 'compré X acciones de TICKER a $PRECIO', use buy_stock.
If user says 'vendí X acciones de TICKER a $PRECIO', use sell_stock.
If user says 'mi portafolio' or 'mis acciones', use get_portfolio.
Leo earns $2,500 MXN per week by default. This resets every Monday automatically.

When the user sends an image, analyze it intelligently:
- If it's an investment portfolio, extract tickers, shares and prices and use buy_stock tool to register them
- If it's a receipt or expense, extract the amount and category and use add_expense tool
- If it's a document, summarize its content
- If it's food, estimate calories and nutritional info
- If it's anything else, explain what you see in a helpful way
Always respond in Spanish.

When you see an image with multiple stocks/investments, you MUST call buy_stock tool for EACH stock you see. Do not skip any. Register all positions visible in the image in a single response using multiple tool calls.

When the user asks for the weekly stock report, call get_portfolio tool and present the weekly performance directly in WhatsApp. Never ask for an email to send the report — always respond directly in the chat.
"""

# Define the tools Claude can use
JARVIS_TOOLS = [
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
    },
    {
        "name": "get_recent_unread_emails",
        "description": "Obtiene los 5 correos electrónicos más recientes que no han sido leídos en Gmail.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_urgent_emails",
        "description": "Obtiene los correos electrónicos más recientes marcados como importantes o destacados en Gmail.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "send_email",
        "description": "Envía un correo electrónico a través de Gmail.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Dirección de correo electrónico del destinatario."
                },
                "subject": {
                    "type": "string",
                    "description": "El asunto del correo electrónico."
                },
                "body": {
                    "type": "string",
                    "description": "El cuerpo o contenido del correo electrónico."
                }
            },
            "required": ["to", "subject", "body"]
        }
    },
    {
        "name": "save_contact",
        "description": "Guarda un contacto con nombre y email en la agenda de Jarvis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nombre o descripción del contacto (ej. 'maestra de matemáticas')"},
                "email": {"type": "string", "description": "Email del contacto"},
                "notes": {"type": "string", "description": "Notas adicionales (opcional)"}
            },
            "required": ["name", "email"]
        }
    },
    {
        "name": "get_contact",
        "description": "Busca un contacto en la agenda por nombre.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nombre del contacto a buscar"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "send_email_to_contact",
        "description": "Busca un contacto en la agenda y le envía un email.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_name": {"type": "string", "description": "Nombre del contacto"},
                "subject": {"type": "string", "description": "Asunto del email"},
                "body": {"type": "string", "description": "Cuerpo del mensaje"}
            },
            "required": ["contact_name", "subject", "body"]
        }
    },
    {
        "name": "add_task",
        "description": "Agrega una tarea a la lista de pendientes del día.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Descripción de la tarea"}
            },
            "required": ["task"]
        }
    },
    {
        "name": "get_tasks",
        "description": "Muestra todas las tareas pendientes del día.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "complete_task",
        "description": "Marca una tarea como completada o no completada.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "ID de la tarea"},
                "completed": {"type": "boolean", "description": "True si cumplida, False si no"}
            },
            "required": ["task_id", "completed"]
        }
    },
    {
        "name": "set_salary",
        "description": "Registra el sueldo semanal del usuario.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "Monto del sueldo semanal"}
            },
            "required": ["amount"]
        }
    },
    {
        "name": "get_balance",
        "description": "Muestra el balance semanal: sueldo, gastos y disponible.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "add_fixed_expense",
        "description": "Agrega un gasto fijo recurrente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nombre del gasto fijo"},
                "amount": {"type": "number", "description": "Monto"},
                "frequency": {"type": "string", "description": "Frecuencia: semanal, quincenal, mensual"}
            },
            "required": ["name", "amount", "frequency"]
        }
    },
    {"name": "buy_stock", "description": "Registra compra de acciones.", "input_schema": {"type": "object", "properties": {"ticker": {"type": "string"}, "shares": {"type": "number"}, "price": {"type": "number"}}, "required": ["ticker", "shares", "price"]}},
    {"name": "sell_stock", "description": "Registra venta de acciones.", "input_schema": {"type": "object", "properties": {"ticker": {"type": "string"}, "shares": {"type": "number"}, "price": {"type": "number"}}, "required": ["ticker", "shares", "price"]}},
    {"name": "get_portfolio", "description": "Muestra portafolio con precios actuales y ganancias/pérdidas.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "add_expense", "description": "Registra un gasto.", "input_schema": {"type": "object", "properties": {"amount": {"type": "number"}, "category": {"type": "string"}, "description": {"type": "string"}}, "required": ["amount", "category"]}},
    {"name": "get_expenses", "description": "Muestra gastos del día.", "input_schema": {"type": "object", "properties": {}}}
]

def get_conversation_history(phone_number, limit=3):
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

def save_contact(phone_number, name, email, notes=""):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO contacts (phone_number, name, email, notes) VALUES (%s, %s, %s, %s)",
            (phone_number, name.lower(), email, notes)
        )
        conn.commit()
        cur.close()
        conn.close()
        return f"✅ Contacto guardado: {name} — {email}"
    except Exception as e:
        return f"Error guardando contacto: {str(e)}"

def get_contact(phone_number, name):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM contacts WHERE phone_number = %s AND name ILIKE %s",
            (phone_number, f"%{name}%")
        )
        contact = cur.fetchone()
        cur.close()
        conn.close()
        if contact:
            return f"Contacto encontrado: {contact['name']} — {contact['email']}"
        return "No encontré ningún contacto con ese nombre."
    except Exception as e:
        return f"Error buscando contacto: {str(e)}"

def send_email_to_contact(phone_number, contact_name, subject, body):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM contacts WHERE phone_number = %s AND name ILIKE %s",
            (phone_number, f"%{contact_name}%")
        )
        contact = cur.fetchone()
        cur.close()
        conn.close()
        if not contact:
            return f"No encontré '{contact_name}' en tu agenda. Agrégalo con: 'Jarvis, guarda contacto: [nombre], email: [email]'"
        from gmail_helper import send_email
        return send_email(to=contact['email'], subject=subject, body=body)
    except Exception as e:
        return f"Error: {str(e)}"

def add_task(phone_number, task):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tasks (phone_number, task, task_date) VALUES (%s, %s, CURRENT_DATE) RETURNING id",
            (phone_number, task)
        )
        # Assuming RealDictCursor is active, it returns dict-like objects
        task_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
        conn.close()
        return f"✅ Tarea #{task_id} agregada: {task}"
    except Exception as e:
        return f"Error: {str(e)}"

def get_tasks(phone_number):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM tasks WHERE phone_number = %s AND task_date = CURRENT_DATE ORDER BY created_at ASC",
            (phone_number,)
        )
        tasks = cur.fetchall()
        cur.close()
        conn.close()
        if not tasks:
            return "No tienes tareas para hoy. ¡Agrega algo!"
        task_list = ["📋 *Tus tareas de hoy:*"]
        for t in tasks:
            status = "✅" if t['completed'] else "⏳"
            task_list.append(f"{status} #{t['id']} — {t['task']}")
        return "\n".join(task_list)
    except Exception as e:
        return f"Error: {str(e)}"

def complete_task(phone_number, task_id, completed=True):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE tasks SET completed = %s WHERE id = %s AND phone_number = %s RETURNING task",
            (completed, task_id, phone_number)
        )
        task = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        if task:
            emoji = "✅" if completed else "❌"
            return f"{emoji} Tarea actualizada: {task['task']}"
        return "No encontré esa tarea."
    except Exception as e:
        return f"Error: {str(e)}"

def download_image(media_url):
    try:
        import requests
        import base64
        import os
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        response = requests.get(media_url, auth=(account_sid, auth_token))
        image_data = base64.standard_b64encode(response.content).decode("utf-8")
        return image_data
    except Exception as e:
        print(f"Error descargando imagen: {e}")
        return None

def transcribe_audio(media_url):
    try:
        import requests
        import tempfile
        import os
        from openai import OpenAI
        
        # Descargar el audio de Twilio
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        
        response = requests.get(media_url, auth=(account_sid, auth_token))
        
        # Guardar en archivo temporal
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name
        
        # Transcribir con Whisper
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        with open(tmp_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="es"
            )
        
        os.unlink(tmp_path)
        print(f"Audio transcrito: {transcript.text}")
        return transcript.text
        
    except Exception as e:
        print(f"Error transcribiendo audio: {e}")
        return None

def get_text_from_response(response):
    for block in response.content:
        if hasattr(block, 'text'):
            return block.text
    return "Lo siento, no pude procesar esa solicitud."

@app.route("/webhook", methods=["POST"])
def webhook():
    """
    1. Receive incoming WhatsApp messages via Twilio webhook (POST /webhook).
    """
    incoming_msg = request.values.get("Body", "").strip()
    sender_number = request.values.get("From", "")
    
    media_url = request.values.get("MediaUrl0", "")
    media_type = request.values.get("MediaContentType0", "")
    
    # Clean the sender number (Twilio usually sends it in the format: whatsapp:+1234567890)
    if sender_number.startswith("whatsapp:"):
        sender_number = sender_number.replace("whatsapp:", "")

    # The assistant should remember context of the last 10 messages
    history = get_conversation_history(sender_number, limit=5)
    
    if media_url and "image" in media_type:
        image_data = download_image(media_url)
        if image_data:
            user_text = incoming_msg if incoming_msg else "Analiza esta imagen y responde de forma útil. Si es un portafolio de inversiones extrae los datos. Si es un recibo registra el gasto. Si es cualquier otra cosa explícala."
            history.append({
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data
                        }
                    },
                    {"type": "text", "text": user_text}
                ]
            })
            if not incoming_msg:
                incoming_msg = "[Imagen procesada automáticamene]"
        else:
            history.append({"role": "user", "content": "No pude procesar la imagen."})
            if not incoming_msg:
                incoming_msg = "[Error al procesar imagen]"
            
    elif media_url and "audio" in media_type:
        incoming_msg = transcribe_audio(media_url)
        if not incoming_msg:
            incoming_msg = "No pude transcribir el audio."
        history.append({
            "role": "user",
            "content": incoming_msg
        })
        
    else:
        # Petición estándar de texto
        if not incoming_msg:
            return "No message body", 200
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
            tools=JARVIS_TOOLS
        )
        
        # Check if Claude decided to use a tool
        if response.stop_reason == "tool_use":
            bot_reply = process_tool_use(response, history, sender_number)
        else:
            bot_reply = get_text_from_response(response)
            
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

def process_tool_use(response, history, sender_number):
    # Agregar respuesta completa de Claude al historial
    history.append({
        "role": "assistant",
        "content": response.content
    })
    
    # Recopilar resultados de TODAS las herramientas en un solo mensaje
    tool_results = []
    for block in response.content:
        if block.type == "tool_use":
            tool_result = execute_tool(block.name, block.input, sender_number)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": str(tool_result)
            })
    
    # Agregar TODOS los resultados en UN SOLO mensaje de usuario
    history.append({
        "role": "user",
        "content": tool_results
    })
    
    # Obtener respuesta final
    try:
        final_response = anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=get_system_prompt(),
            messages=history,
            tools=JARVIS_TOOLS,
            timeout=25.0
        )
        # Si Claude quiere usar más herramientas, procesarlas recursivamente
        if final_response.stop_reason == "tool_use":
            return process_tool_use(final_response, history, sender_number)
        return get_text_from_response(final_response)
    except Exception as e:
        print(f"Error getting final response: {e}")
        results_text = "\n".join([r['content'] for r in tool_results])
        return results_text

def execute_tool(tool_name, tool_input, sender_number):
    if tool_name == "get_todays_events":
        return get_todays_events()
    elif tool_name == "create_event":
        return create_event(summary=tool_input.get("summary"), start_time=tool_input.get("start_time"), end_time=tool_input.get("end_time"))
    elif tool_name == "get_recent_unread_emails":
        return get_recent_unread_emails()
    elif tool_name == "get_urgent_emails":
        return get_urgent_emails()
    elif tool_name == "send_email":
        return send_email(to=tool_input.get("to"), subject=tool_input.get("subject"), body=tool_input.get("body"))
    elif tool_name == "save_contact":
        return save_contact(phone_number=sender_number, name=tool_input.get("name"), email=tool_input.get("email"), notes=tool_input.get("notes", ""))
    elif tool_name == "get_contact":
        return get_contact(phone_number=sender_number, name=tool_input.get("name"))
    elif tool_name == "send_email_to_contact":
        return send_email_to_contact(phone_number=sender_number, contact_name=tool_input.get("contact_name"), subject=tool_input.get("subject"), body=tool_input.get("body"))
    elif tool_name == "add_task":
        return add_task(phone_number=sender_number, task=tool_input.get("task"))
    elif tool_name == "get_tasks":
        return get_tasks(phone_number=sender_number)
    elif tool_name == "complete_task":
        return complete_task(phone_number=sender_number, task_id=tool_input.get("task_id"), completed=tool_input.get("completed", True))
    elif tool_name == "buy_stock":
        return add_position(phone_number=sender_number, ticker=tool_input.get("ticker"), shares=tool_input.get("shares"), price=tool_input.get("price"))
    elif tool_name == "sell_stock":
        return remove_position(phone_number=sender_number, ticker=tool_input.get("ticker"), shares=tool_input.get("shares"), price=tool_input.get("price"))
    elif tool_name == "get_portfolio":
        return get_portfolio_summary(phone_number=sender_number)
    elif tool_name == "add_expense":
        return add_expense(phone_number=sender_number, amount=tool_input.get("amount"), category=tool_input.get("category"), description=tool_input.get("description", ""))
    elif tool_name == "get_expenses":
        return get_expenses_summary(phone_number=sender_number)
    elif tool_name == "set_salary":
        return set_salary(phone_number=sender_number, amount=tool_input.get("amount"))
    elif tool_name == "get_balance":
        return get_balance(phone_number=sender_number)
    elif tool_name == "add_fixed_expense":
        return add_fixed_expense(phone_number=sender_number, name=tool_input.get("name"), amount=tool_input.get("amount"), frequency=tool_input.get("frequency"))
    else:
        return f"Herramienta {tool_name} no reconocida."

# Healthcheck route useful for Render
@app.route("/", methods=["GET"])
def index():
    return "Jarvis AI WhatsApp Assistant is running!", 200

if __name__ == "__main__":
    # Bind to 0.0.0.0 to work on Render, read port from environment (Render sets PORT)
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
# updated
