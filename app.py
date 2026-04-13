import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from twilio.twiml.messaging_response import MessagingResponse
from anthropic import Anthropic
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from cryptography.fernet import Fernet
import json
from datetime import datetime, timedelta
import jwt as pyjwt
import bcrypt

# Load environment variables from .env file (for local development)
load_dotenv()

# ─── AUTH: JWT and bcrypt configuration ────────────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET", "jarvis-dev-secret")
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "")

app = Flask(__name__)
CORS(app, resources={r"/chat": {"origins": "*"}, r"/api/*": {"origins": "*"}})

# ─── DEDUPLICACIÓN: evita procesar el mismo mensaje dos veces ────────────────
# Twilio a veces reenvía el mismo webhook si no responde suficientemente rápido
import threading
_processed_sids = set()
_processed_sids_lock = threading.Lock()

def is_duplicate(message_sid):
    """Retorna True si este MessageSid ya fue procesado."""
    with _processed_sids_lock:
        if message_sid in _processed_sids:
            return True
        _processed_sids.add(message_sid)
        # Limpiar el set si crece mucho (guardar solo los últimos 200)
        if len(_processed_sids) > 200:
            oldest = list(_processed_sids)[:100]
            for sid in oldest:
                _processed_sids.discard(sid)
        return False

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

# ─── TRADING: Fernet Encryption Helpers ───────────────────────────────────────
FERNET_KEY = os.getenv("FERNET_KEY")

def _get_fernet():
    if not FERNET_KEY:
        raise ValueError("FERNET_KEY environment variable not set")
    return Fernet(FERNET_KEY.encode())

def _encrypt(text):
    return _get_fernet().encrypt(text.encode()).decode()

def _decrypt(token):
    return _get_fernet().decrypt(token.encode()).decode()

# Import calendar and gmail helper functions
from calendar_helper import get_todays_events, create_event
from gmail_helper import get_recent_unread_emails, get_urgent_emails, send_email


def add_expense(phone_number, amount, category, description=""):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO expenses (phone_number, amount, category, description) VALUES (%s, %s, %s, %s)",
            (phone_number, amount, category, description)
        )
        conn.commit()
        cur.close()
        conn.close()
        return f"✅ ¡Gasto registrado!\n\n💵 Monto: ${amount}\n🏷️ Categoría: {category}\n📝 Descripción: {description if description else 'N/A'}"
    except Exception as e:
        return f"Error: {str(e)}"

def get_expenses_summary(phone_number, period="day"):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if period == "week":
            cur.execute(
                "SELECT category, SUM(amount) as total FROM expenses WHERE phone_number = %s AND expense_date >= date_trunc('week', CURRENT_DATE) GROUP BY category ORDER BY total DESC",
                (phone_number,)
            )
            title = "esta semana"
        else:
            cur.execute(
                "SELECT category, SUM(amount) as total FROM expenses WHERE phone_number = %s AND expense_date = CURRENT_DATE GROUP BY category ORDER BY total DESC",
                (phone_number,)
            )
            title = "hoy"
        expenses = cur.fetchall()
        cur.close()
        conn.close()
        if not expenses:
            return f"No has registrado gastos {title}."
        lines = [f"💸 Gastos de {title}:\n"]
        total = 0
        for e in expenses:
            lines.append(f"  • {e['category']}: ${e['total']:.2f}")
            total += float(e['total'])
        lines.append(f"\n💰 Total: ${total:.2f}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"

def add_debt(phone_number, person, amount, debt_type, description=""):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO debts (phone_number, person, amount, debt_type, description) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (phone_number, person, amount, debt_type, description)
        )
        debt_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
        conn.close()
        if debt_type == 'owe':
            return f"✅ ¡Deuda registrada!\n\n👤 Persona: {person}\n🔴 Tipo: Yo debo\n💵 Monto: ${amount}\n📝 Descripción: {description if description else 'N/A'}\n🆔 ID: #{debt_id}"
        else:
            return f"✅ ¡Deuda registrada!\n\n👤 Persona: {person}\n🟢 Tipo: Me deben\n💵 Monto: ${amount}\n📝 Descripción: {description if description else 'N/A'}\n🆔 ID: #{debt_id}"
    except Exception as e:
        return f"Error: {str(e)}"

def get_debts(phone_number):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM debts WHERE phone_number = %s AND paid = FALSE ORDER BY created_at DESC",
            (phone_number,)
        )
        debts = cur.fetchall()
        cur.close()
        conn.close()
        if not debts:
            return "No tienes deudas pendientes ✅\n¡Estás al corriente!"
        owe = [d for d in debts if d['debt_type'] == 'owe']
        owed = [d for d in debts if d['debt_type'] == 'owed']
        lines = ["💸 Tus deudas pendientes:\n"]
        if owe:
            lines.append("🔴 Tú debes:")
            for d in owe:
                lines.append(f"  • #{d['id']} {d['person']}: ${d['amount']}")
                if d['description']:
                    lines.append(f"    📝 {d['description']}")
        if owed:
            lines.append("\n🟢 Te deben:")
            for d in owed:
                lines.append(f"  • #{d['id']} {d['person']}: ${d['amount']}")
                if d['description']:
                    lines.append(f"    📝 {d['description']}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"

def pay_debt(phone_number, debt_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE debts SET paid = TRUE WHERE id = %s AND phone_number = %s RETURNING person, amount",
            (debt_id, phone_number)
        )
        debt = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        if debt:
            return f"✅ ¡Deuda pagada!\n\n👤 Persona: {debt['person']}\n💵 Monto: ${debt['amount']}\n🆔 ID: #{debt_id}"
        return "No encontré esa deuda."
    except Exception as e:
        return f"Error: {str(e)}"

def add_reminder(phone_number, title, reminder_date, description=""):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO reminders (phone_number, title, reminder_date, description) VALUES (%s, %s, %s, %s) RETURNING id",
            (phone_number, title, reminder_date, description)
        )
        reminder_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
        conn.close()
        return f"✅ ¡Recordatorio guardado!\n\n📌 Título: {title}\n📅 Fecha: {reminder_date}\n📝 Descripción: {description if description else 'N/A'}\n🆔 ID: #{reminder_id}"
    except Exception as e:
        return f"Error: {str(e)}"

def get_reminders(phone_number):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM reminders WHERE phone_number = %s AND sent = FALSE AND reminder_date >= CURRENT_DATE ORDER BY reminder_date ASC LIMIT 10",
            (phone_number,)
        )
        reminders = cur.fetchall()
        cur.close()
        conn.close()
        if not reminders:
            return "No tienes recordatorios próximos."
        lines = ["🔔 Próximos recordatorios:\n"]
        for r in reminders:
            lines.append(f"  • #{r['id']} {r['title']} ({r['reminder_date']})")
            if r['description']:
                lines.append(f"    📝 {r['description']}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"

def add_goal(phone_number, title, description="", target_date=None):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO goals (phone_number, title, description, target_date) VALUES (%s, %s, %s, %s) RETURNING id",
            (phone_number, title, description, target_date)
        )
        goal_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
        conn.close()
        return f"✅ ¡Meta registrada! 🏃\n\n🎯 Meta: {title}\n📝 Descripción: {description if description else 'N/A'}\n📅 Fecha límite: {target_date if target_date else 'Sin límite'}\n📊 Progreso: 0%\n🆔 ID: #{goal_id}"
    except Exception as e:
        return f"Error: {str(e)}"

def get_goals(phone_number):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM goals WHERE phone_number = %s AND completed = FALSE ORDER BY created_at DESC",
            (phone_number,)
        )
        goals = cur.fetchall()
        cur.close()
        conn.close()
        if not goals:
            return "No tienes metas activas. ¡Agrega una!"
        lines = ["🎯 Tus metas activas:\n"]
        for g in goals:
            bar = "█" * (g['progress'] // 10) + "░" * (10 - g['progress'] // 10)
            lines.append(f"  • #{g['id']} {g['title']}")
            lines.append(f"    📊 [{bar}] {g['progress']}%")
            if g['target_date']:
                lines.append(f"    📅 Límite: {g['target_date']}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"

def update_goal_progress(phone_number, goal_id, progress):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        completed = progress >= 100
        cur.execute(
            "UPDATE goals SET progress = %s, completed = %s WHERE id = %s AND phone_number = %s RETURNING title",
            (progress, completed, goal_id, phone_number)
        )
        goal = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        conn.close()
        if goal:
            if completed:
                return f"🎉 ¡Meta '{goal['title']}' completada al 100%!"
            return f"✅ ¡Progreso actualizado!\n\n🎯 Meta: {goal['title']}\n📊 Nuevo Progreso: {progress}%\n🆔 ID: #{goal_id}"
        return "No encontré esa meta."
    except Exception as e:
        return f"Error: {str(e)}"

def log_mood(phone_number, mood, notes=""):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO health_logs (phone_number, log_type, value, notes) VALUES (%s, 'mood', %s, %s)",
            (phone_number, mood, notes)
        )
        conn.commit()
        cur.close()
        conn.close()
        mood_tips = {
            'ansioso': '💡 Tip: 5 minutos de respiración profunda antes de entrenar mejora el rendimiento en Hyrox.',
            'cansado': '💡 Tip: Si estás muy cansado, considera un entrenamiento de recuperación activa hoy.',
            'motivado': '💡 Tip: ¡Perfecto para un entrenamiento intenso! Aprovecha la energía.',
            'estresado': '💡 Tip: El ejercicio reduce el cortisol. Un run de 20 min te ayudará.',
            'triste': '💡 Tip: El ejercicio libera endorfinas. Aunque sea una caminata corta ayuda.'
        }
        tip = mood_tips.get(mood.lower(), '💡 Tip: Mantén consistencia en tu entrenamiento para Hyrox.')
        return f"✅ Estado de ánimo registrado: {mood}\n\n{tip}"
    except Exception as e:
        return f"Error: {str(e)}"

def log_calories(phone_number, meal_description, calories, protein=0, carbs=0, fat=0):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO calorie_logs (phone_number, meal_description, calories, protein, carbs, fat) VALUES (%s, %s, %s, %s, %s, %s)",
            (phone_number, meal_description, calories, protein, carbs, fat)
        )
        # Total del día
        cur.execute(
            "SELECT SUM(calories) as total, SUM(protein) as protein FROM calorie_logs WHERE phone_number = %s AND log_date = CURRENT_DATE",
            (phone_number,)
        )
        totals = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        total_cals = totals['total'] or 0
        # Meta calórica para Hyrox: déficit moderado para cuadritos
        meta = 2200
        remaining = meta - total_cals
        return f"✅ Comida registrada\n\n🍽️ {meal_description}\n🔥 {calories} kcal | 🥩 {protein}g proteína\n\n📊 Hoy llevas: {total_cals} kcal\n🎯 Meta: {meta} kcal\n{'✅' if remaining > 0 else '⚠️'} {'Te quedan' if remaining > 0 else 'Excediste por'} {abs(remaining)} kcal"
    except Exception as e:
        return f"Error: {str(e)}"

def get_calories_today(phone_number):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT meal_description, calories, protein, carbs, fat FROM calorie_logs WHERE phone_number = %s AND log_date = CURRENT_DATE ORDER BY created_at ASC",
            (phone_number,)
        )
        meals = cur.fetchall()
        cur.execute(
            "SELECT SUM(calories) as cal, SUM(protein) as prot, SUM(carbs) as carbs, SUM(fat) as fat FROM calorie_logs WHERE phone_number = %s AND log_date = CURRENT_DATE",
            (phone_number,)
        )
        totals = cur.fetchone()
        cur.close()
        conn.close()
        if not meals:
            return "No has registrado comidas hoy 🍽️\nEmpieza diciéndome qué desayunaste."
        meta = 2200
        total = totals['cal'] or 0
        lines = ["🔥 Calorías de hoy:\n"]
        for m in meals:
            lines.append(f"• {m['meal_description']}: {m['calories']} kcal")
        lines.append(f"\n📊 Total: {total} kcal / {meta} kcal meta")
        lines.append(f"🥩 Proteína: {totals['prot'] or 0}g")
        remaining = meta - total
        if remaining > 0:
            lines.append(f"✅ Te quedan {remaining} kcal")
        else:
            lines.append(f"⚠️ Excediste la meta por {abs(remaining)} kcal")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"

def log_sleep(phone_number, hours, quality="regular"):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO health_logs (phone_number, log_type, value, notes) VALUES (%s, 'sleep', %s, %s)",
            (phone_number, str(hours), quality)
        )
        conn.commit()
        cur.close()
        conn.close()
        if hours >= 8:
            tip = "💪 Excelente descanso. Tu cuerpo está listo para entrenar fuerte hoy."
        elif hours >= 6:
            tip = "👍 Sueño aceptable. Considera una siesta de 20 min si puedes."
        else:
            tip = "⚠️ Poco sueño. Para Hyrox el descanso es crucial. Prioriza dormir esta noche."
        return f"✅ Sueño registrado: {hours} horas ({quality})\n\n{tip}"
    except Exception as e:
        return f"Error: {str(e)}"

def add_medication(phone_number, name, dosage, frequency, reminder_time=None):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO medications (phone_number, name, dosage, frequency, reminder_time) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (phone_number, name, dosage, frequency, reminder_time)
        )
        med_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
        conn.close()
        return f"✅ Medicamento registrado\n\n💊 {name} - {dosage}\n🔁 {frequency}\n⏰ Recordatorio: {reminder_time or 'sin hora específica'}\n🆔 #{med_id}"
    except Exception as e:
        return f"Error: {str(e)}"

def get_health_summary(phone_number):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Sueño de anoche
        cur.execute(
            "SELECT value, notes FROM health_logs WHERE phone_number = %s AND log_type = 'sleep' AND log_date = CURRENT_DATE ORDER BY created_at DESC LIMIT 1",
            (phone_number,)
        )
        sleep = cur.fetchone()
        # Estado de ánimo
        cur.execute(
            "SELECT value FROM health_logs WHERE phone_number = %s AND log_type = 'mood' AND log_date = CURRENT_DATE ORDER BY created_at DESC LIMIT 1",
            (phone_number,)
        )
        mood = cur.fetchone()
        # Calorías
        cur.execute(
            "SELECT SUM(calories) as total FROM calorie_logs WHERE phone_number = %s AND log_date = CURRENT_DATE",
            (phone_number,)
        )
        cals = cur.fetchone()
        cur.close()
        conn.close()
        lines = ["🏋️ Resumen de salud hoy:\n"]
        lines.append(f"😴 Sueño: {sleep['value'] + ' hrs (' + sleep['notes'] + ')' if sleep else 'No registrado'}")
        lines.append(f"🧘 Ánimo: {mood['value'] if mood else 'No registrado'}")
        lines.append(f"🔥 Calorías: {cals['total'] or 0} / 2200 kcal")
        lines.append("\n💪 Recomendación Hyrox:")
        if sleep and float(sleep['value']) >= 7:
            lines.append("• Buen descanso — día ideal para entrenamiento de alta intensidad")
        else:
            lines.append("• Poco sueño — enfócate en movilidad y recuperación hoy")
        lines.append("• Asegura 2g de proteína por kg de peso corporal")
        lines.append("• Hidratación: mínimo 3L de agua para Hyrox training")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"

import datetime

# System Prompt defining Jarvis's persona
def get_system_prompt():
    # Set reference time to GMT-6 (Mexico City) 
    now_mx = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-6)))
    date_str = now_mx.strftime("%A, %Y-%m-%d %H:%M:%S GMT-6")
    
    return f"""You are a personal life assistant named "Jarvis" that helps with everything in the user's life.
You are concise, highly intelligent, and helpful. You receive messages via WhatsApp.
CRITICAL FORMATTING RULE FOR WHATSAPP:
- Never use markdown tables (no | characters)
- Never use --- dividers
- Never use ** for bold (WhatsApp uses * not **)
- Never use quotes or " characters to wrap text
- Never start responses with quotes
- Keep responses simple and clean
- Use single * for bold if needed (e.g. *Texto*)
- Use emojis and line breaks only

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
If user says 'manda WhatsApp a [contacto] diciéndole que: [mensaje]', use send_whatsapp_to_contact tool.
If user says 'llama a [contacto] y dile que: [mensaje]', use call_contact tool.
If user says 'agrega el teléfono de [contacto]: [número]', update the contact phone number.
When saving a new contact, also ask for their phone number if not provided.
If user says 'agrega tarea: [tarea]' or 'agregar pendiente: [tarea]', use add_task.
If user says 'mis tareas' or 'pendientes de hoy', use get_tasks.
If user says 'listo #[id]' or 'cumplí #[id]', use complete_task with completed=True.
If user says 'no cumplí #[id]', use complete_task with completed=False.

If user says 'gasté $X en CATEGORIA', use add_expense tool.
If user says 'mis gastos de hoy' or 'mis gastos de la semana', use get_expenses tool.

If user says 'le debo $X a [persona]', use add_debt with debt_type='owe'.
If user says '[persona] me debe $X', use add_debt with debt_type='owed'.
If user says 'mis deudas', use get_debts.
If user says 'ya pagué la deuda #X', use pay_debt.
If user says 'recuérdame [cosa] el [fecha]', use add_reminder.
If user says 'mis recordatorios', use get_reminders.
If user says 'agrega meta: [meta]', use add_goal.
If user says 'mis metas', use get_goals.
If user says 'actualiza meta #X al Y%', use update_goal_progress.

Leo's fitness goal is to get six-pack abs and train for Hyrox competition. His daily calorie target is 2200 kcal with high protein.
If user says 'me siento [estado]' or 'estoy [estado]', use log_mood tool.
If user sends a photo of food, analyze calories and use log_calories tool automatically.
If user says 'dormí X horas', use log_sleep tool.
If user says 'qué comí hoy' or 'mis calorías', use get_calories_today tool.
If user says 'agrega medicamento [nombre]', use add_medication tool.
If user says 'resumen de salud' or 'cómo voy hoy', use get_health_summary tool.

If user says 'mis tareas' or 'tareas de blackboard', use get_bb_assignments tool.
If user says 'mis calificaciones' or 'mis notas', use get_bb_grades tool.

If user says 'tengo tarea de [materia] el [fecha]' or 'entrega de [materia] el [fecha]', use add_reminder tool with the title as 'Tarea: [materia]' and set the reminder_date to one day before the due date so Leo gets reminded in advance.
If user says 'mis tareas escolares' or 'qué entregas tengo', use get_reminders tool and filter by titles that start with 'Tarea:'.

When the user sends an image, analyze it intelligently:

- If it's a document, summarize its content
- If it's food, estimate calories and nutritional info
- If it's anything else, explain what you see in a helpful way
Always respond in Spanish.


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
        "description": "Guarda un contacto en la agenda de Jarvis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nombre o descripción del contacto (ej. 'maestra de matemáticas')"},
                "email": {"type": "string", "description": "Email del contacto (opcional)"},
                "phone": {"type": "string", "description": "Teléfono del contacto (opcional)"},
                "notes": {"type": "string", "description": "Notas adicionales (opcional)"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "send_whatsapp_to_contact",
        "description": "Envía un mensaje de WhatsApp a un contacto guardado en la agenda.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_name": {"type": "string", "description": "Nombre del contacto"},
                "message": {"type": "string", "description": "Mensaje a enviar"}
            },
            "required": ["contact_name", "message"]
        }
    },
    {
        "name": "call_contact",
        "description": "Hace una llamada telefónica a un contacto y reproduce un mensaje de voz.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_name": {"type": "string", "description": "Nombre del contacto"},
                "message": {"type": "string", "description": "Mensaje que se reproducirá en la llamada"}
            },
            "required": ["contact_name", "message"]
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
        "name": "add_expense",
        "description": "Registra un gasto del usuario.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "Monto del gasto"},
                "category": {"type": "string", "description": "Categoría (comida, transporte, entretenimiento, ropa, etc.)"},
                "description": {"type": "string", "description": "Descripción del gasto (opcional)"}
            },
            "required": ["amount", "category"]
        }
    },
    {
        "name": "get_expenses",
        "description": "Muestra resumen de gastos del día o de la semana.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "description": "day o week"}
            }
        }
    },
    {
        "name": "add_debt",
        "description": "Registra una deuda. Puede ser 'owe' (yo le debo a alguien) o 'owed' (alguien me debe a mí).",
        "input_schema": {
            "type": "object",
            "properties": {
                "person": {"type": "string", "description": "Nombre de la persona"},
                "amount": {"type": "number", "description": "Monto de la deuda"},
                "description": {"type": "string", "description": "Descripción de la deuda"},
                "debt_type": {"type": "string", "description": "'owe' si yo le debo, 'owed' si me deben a mí"}
            },
            "required": ["person", "amount", "debt_type"]
        }
    },
    {
        "name": "get_debts",
        "description": "Muestra todas las deudas pendientes.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "pay_debt",
        "description": "Marca una deuda como pagada.",
        "input_schema": {
            "type": "object",
            "properties": {
                "debt_id": {"type": "integer", "description": "ID de la deuda"}
            },
            "required": ["debt_id"]
        }
    },
    {
        "name": "add_reminder",
        "description": "Agrega un recordatorio para una fecha específica.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Título del recordatorio"},
                "reminder_date": {"type": "string", "description": "Fecha del recordatorio en formato YYYY-MM-DD"},
                "description": {"type": "string", "description": "Descripción adicional (opcional)"}
            },
            "required": ["title", "reminder_date"]
        }
    },
    {
        "name": "get_reminders",
        "description": "Muestra los recordatorios próximos.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "add_goal",
        "description": "Agrega una meta personal con fecha límite.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Título de la meta"},
                "description": {"type": "string", "description": "Descripción de la meta"},
                "target_date": {"type": "string", "description": "Fecha límite en formato YYYY-MM-DD"}
            },
            "required": ["title"]
        }
    },
    {
        "name": "get_goals",
        "description": "Muestra las metas personales activas.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "update_goal_progress",
        "description": "Actualiza el progreso de una meta del 0 al 100%.",
        "input_schema": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "integer", "description": "ID de la meta"},
                "progress": {"type": "integer", "description": "Progreso del 0 al 100"}
            },
            "required": ["goal_id", "progress"]
        }
    },
    {
        "name": "log_mood",
        "description": "Registra el estado de ánimo del usuario.",
        "input_schema": {
            "type": "object",
            "properties": {
                "mood": {"type": "string", "description": "Estado de ánimo: feliz, triste, ansioso, motivado, cansado, estresado, etc."},
                "notes": {"type": "string", "description": "Notas adicionales (opcional)"}
            },
            "required": ["mood"]
        }
    },
    {
        "name": "log_calories",
        "description": "Registra las calorías de una comida.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meal_description": {"type": "string", "description": "Descripción de la comida"},
                "calories": {"type": "integer", "description": "Calorías estimadas"},
                "protein": {"type": "integer", "description": "Proteína en gramos"},
                "carbs": {"type": "integer", "description": "Carbohidratos en gramos"},
                "fat": {"type": "integer", "description": "Grasa en gramos"}
            },
            "required": ["meal_description", "calories"]
        }
    },
    {
        "name": "get_calories_today",
        "description": "Muestra el resumen de calorías del día.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "add_medication",
        "description": "Agrega un medicamento con recordatorio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nombre del medicamento"},
                "dosage": {"type": "string", "description": "Dosis (ej. 500mg)"},
                "frequency": {"type": "string", "description": "Frecuencia (ej. cada 8 horas, una vez al día)"},
                "reminder_time": {"type": "string", "description": "Hora del recordatorio en formato HH:MM"}
            },
            "required": ["name", "dosage", "frequency"]
        }
    },
    {
        "name": "log_sleep",
        "description": "Registra las horas de sueño.",
        "input_schema": {
            "type": "object",
            "properties": {
                "hours": {"type": "number", "description": "Horas de sueño"},
                "quality": {"type": "string", "description": "Calidad: bueno, regular, malo"}
            },
            "required": ["hours"]
        }
    },
    {
        "name": "get_health_summary",
        "description": "Muestra resumen de salud del día con recomendaciones para Hyrox.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_bb_assignments",
        "description": "Obtiene las tareas pendientes de Blackboard UDEM.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_bb_grades",
        "description": "Obtiene las calificaciones de Blackboard UDEM.",
        "input_schema": {"type": "object", "properties": {}}
    }
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

def save_contact(phone_number, name, email, notes="", phone=None):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO contacts (phone_number, name, email, notes, phone) VALUES (%s, %s, %s, %s, %s)",
            (phone_number, name.lower(), email, notes, phone)
        )
        conn.commit()
        cur.close()
        conn.close()
        return f"✅ Contacto guardado: {name} — {email}{' — ' + phone if phone else ''}"
    except Exception as e:
        return f"Error: {str(e)}"

def send_whatsapp_to_contact(phone_number, contact_name, message):
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
            return f"No encontré '{contact_name}' en tu agenda. Agrégalo con: 'Jarvis, guarda contacto: [nombre], email: [email], teléfono: [número]'"
        if not contact.get('phone'):
            return f"El contacto {contact['name']} no tiene número de teléfono. Agrégalo con: 'Jarvis, agrega el teléfono de {contact['name']}: +521XXXXXXXXXX'"
        from twilio.rest import Client
        client = Client(os.getenv('TWILIO_ACCOUNT_SID'), os.getenv('TWILIO_AUTH_TOKEN'))
        msg = client.messages.create(
            body=message,
            from_=f"whatsapp:{os.getenv('TWILIO_WHATSAPP_NUMBER')}",
            to=f"whatsapp:{contact['phone'].replace('whatsapp:', '')}"
        )
        return f"✅ Mensaje enviado a {contact['name']} ({contact['phone']})\n\n💬 {message}"
    except Exception as e:
        return f"Error enviando mensaje: {str(e)}"

def call_contact(phone_number, contact_name, message):
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
            return f"No encontré '{contact_name}' en tu agenda."
        if not contact.get('phone'):
            return f"El contacto {contact['name']} no tiene número de teléfono registrado."
        from twilio.rest import Client
        from twilio.twiml.voice_response import VoiceResponse
        client = Client(os.getenv('TWILIO_ACCOUNT_SID'), os.getenv('TWILIO_AUTH_TOKEN'))
        twiml = VoiceResponse()
        twiml.say(message, voice='Polly.Mia', language='es-MX')
        
        # Determine from_ number
        from_number = os.getenv('TWILIO_WHATSAPP_NUMBER')
        if from_number and 'whatsapp:' in from_number:
            from_number = from_number.replace('whatsapp:', '')
        else:
            from_number = os.getenv('TWILIO_PHONE_NUMBER', from_number)
            
        to_number = contact['phone'].replace('whatsapp:', '')
            
        call = client.calls.create(
            twiml=str(twiml),
            to=to_number,
            from_=from_number
        )
        return f"📞 Llamada iniciada a {contact['name']} ({contact['phone']})\n\n🎙️ Mensaje: {message}"
    except Exception as e:
        return f"Error realizando llamada: {str(e)}"

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
    message_sid = request.values.get("MessageSid", "")

    # ── Protección anti-duplicados ──────────────────────────────────────────
    # Twilio reenvía el webhook si no responde a tiempo → evita eventos dobles
    if message_sid and is_duplicate(message_sid):
        print(f"[DEDUP] MessageSid {message_sid} ya procesado, ignorando.")
        resp = MessagingResponse()
        return str(resp)  # respuesta vacía, Twilio no reintenta

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
    
    # Limpiar formato para WhatsApp
    import re
    bot_reply = re.sub(r'\|.*\|', '', bot_reply)  # eliminar tablas
    bot_reply = re.sub(r'---+', '', bot_reply)  # eliminar divisores
    bot_reply = re.sub(r'\*\*', '', bot_reply)  # eliminar bold markdown
    bot_reply = re.sub(r'^"(.*)"$', r'\1', bot_reply, flags=re.DOTALL)  # eliminar comillas al inicio/fin
    bot_reply = re.sub(r'\n\s*\n\s*\n', '\n\n', bot_reply)  # máximo 2 saltos de línea
    bot_reply = bot_reply.strip()
    
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
        return save_contact(phone_number=sender_number, name=tool_input.get("name"), email=tool_input.get("email"), notes=tool_input.get("notes", ""), phone=tool_input.get("phone"))
    elif tool_name == "send_whatsapp_to_contact":
        return send_whatsapp_to_contact(phone_number=sender_number, contact_name=tool_input.get("contact_name"), message=tool_input.get("message"))
    elif tool_name == "call_contact":
        return call_contact(phone_number=sender_number, contact_name=tool_input.get("contact_name"), message=tool_input.get("message"))
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
    elif tool_name == "add_expense":
        return add_expense(phone_number=sender_number, amount=tool_input.get("amount"), category=tool_input.get("category"), description=tool_input.get("description", ""))
    elif tool_name == "get_expenses":
        return get_expenses_summary(phone_number=sender_number, period=tool_input.get("period", "day"))
    elif tool_name == "add_debt":
        return add_debt(phone_number=sender_number, person=tool_input.get("person"), amount=tool_input.get("amount"), debt_type=tool_input.get("debt_type"), description=tool_input.get("description", ""))
    elif tool_name == "get_debts":
        return get_debts(phone_number=sender_number)
    elif tool_name == "pay_debt":
        return pay_debt(phone_number=sender_number, debt_id=tool_input.get("debt_id"))
    elif tool_name == "add_reminder":
        return add_reminder(phone_number=sender_number, title=tool_input.get("title"), reminder_date=tool_input.get("reminder_date"), description=tool_input.get("description", ""))
    elif tool_name == "get_reminders":
        return get_reminders(phone_number=sender_number)
    elif tool_name == "add_goal":
        return add_goal(phone_number=sender_number, title=tool_input.get("title"), description=tool_input.get("description", ""), target_date=tool_input.get("target_date"))
    elif tool_name == "get_goals":
        return get_goals(phone_number=sender_number)
    elif tool_name == "update_goal_progress":
        return update_goal_progress(phone_number=sender_number, goal_id=tool_input.get("goal_id"), progress=tool_input.get("progress"))
    elif tool_name == "log_mood":
        return log_mood(phone_number=sender_number, mood=tool_input.get("mood"), notes=tool_input.get("notes", ""))
    elif tool_name == "log_calories":
        return log_calories(phone_number=sender_number, meal_description=tool_input.get("meal_description"), calories=tool_input.get("calories"), protein=tool_input.get("protein", 0), carbs=tool_input.get("carbs", 0), fat=tool_input.get("fat", 0))
    elif tool_name == "get_calories_today":
        return get_calories_today(phone_number=sender_number)
    elif tool_name == "log_sleep":
        return log_sleep(phone_number=sender_number, hours=tool_input.get("hours"), quality=tool_input.get("quality", "regular"))
    elif tool_name == "add_medication":
        return add_medication(phone_number=sender_number, name=tool_input.get("name"), dosage=tool_input.get("dosage"), frequency=tool_input.get("frequency"), reminder_time=tool_input.get("reminder_time"))
    elif tool_name == "get_health_summary":
        return get_health_summary(phone_number=sender_number)
    elif tool_name == "get_bb_assignments":
        from blackboard_helper import get_bb_assignments
        return get_bb_assignments()
    elif tool_name == "get_bb_grades":
        from blackboard_helper import get_bb_grades
        return get_bb_grades()
    else:
        return f"Herramienta {tool_name} no reconocida."

@app.route("/chat", methods=["POST"])
def chat():
    """
    Web dashboard chat endpoint.
    Expects JSON: { "message": "...", "session_id": "..." }
    Returns JSON: { "reply": "..." }
    """
    data = request.get_json(force=True, silent=True) or {}
    user_message = (data.get("message") or "").strip()
    session_id = (data.get("session_id") or "web_dashboard").strip()
    custom_system = (data.get("system_prompt") or "").strip()

    if not user_message:
        return jsonify({"error": "message is required"}), 400

    # Re-use the same conversation history stored in DB, keyed by session_id
    web_phone = f"web:{session_id}"
    history = get_conversation_history(web_phone, limit=5)
    history.append({"role": "user", "content": user_message})

    active_system = custom_system if custom_system else get_system_prompt()
    active_tools  = [] if custom_system else JARVIS_TOOLS

    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=active_system,
            messages=history,
            tools=active_tools,
        )

        if response.stop_reason == "tool_use":
            bot_reply = process_tool_use(response, history, web_phone)
        else:
            bot_reply = get_text_from_response(response)

    except Exception as e:
        print(f"Error in /chat endpoint: {e}")
        return jsonify({"error": "Error procesando la solicitud"}), 500

    save_message(web_phone, user_message, bot_reply)
    return jsonify({"reply": bot_reply})


# Healthcheck route useful for Render
@app.route("/", methods=["GET"])
def index():
    return "Jarvis AI WhatsApp Assistant is running!", 200

# ─── Dashboard REST API ───────────────────────────────────────────────────────

DASHBOARD_PHONE = "5218129354808"
_CATEGORY_COLORS = ["#2563EB", "#7C3AED", "#059669", "#D97706", "#6B7280", "#EF4444", "#10B981"]

@app.route("/api/calendar", methods=["GET"])
def api_calendar():
    try:
        from calendar_helper import get_calendar_service
        import datetime
        service = get_calendar_service()
        if not service:
            return jsonify([])
        now = datetime.datetime.now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
        end   = now.replace(hour=23, minute=59, second=59, microsecond=0).isoformat() + "Z"
        result = service.events().list(
            calendarId=os.getenv("GOOGLE_CALENDAR_ID", "primary"),
            timeMin=start, timeMax=end,
            singleEvents=True, orderBy="startTime"
        ).execute()
        events = []
        for ev in result.get("items", []):
            start_dt = ev["start"].get("dateTime", ev["start"].get("date", ""))
            events.append({
                "id":    ev.get("id"),
                "title": ev.get("summary", "Sin título"),
                "time":  start_dt[11:16] if "T" in start_dt else start_dt,
                "date":  start_dt,
            })
        return jsonify(events)
    except Exception as e:
        print(f"Error in /api/calendar: {e}")
        return jsonify([])

@app.route("/api/tasks", methods=["GET"])
def api_tasks():
    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute(
            "SELECT id, task, completed FROM tasks WHERE phone_number = %s AND task_date = CURRENT_DATE ORDER BY id",
            (DASHBOARD_PHONE,)
        )
        rows = cur.fetchall()
        cur.close(); conn.close()
        return jsonify([{"id": r["id"], "text": r["task"], "done": r["completed"], "priority": "media"} for r in rows])
    except Exception as e:
        print(f"Error in /api/tasks: {e}")
        return jsonify([])

@app.route("/api/gmail", methods=["GET"])
def api_gmail():
    try:
        from gmail_helper import get_gmail_service
        service = get_gmail_service()
        if not service:
            return jsonify([])
        results = service.users().messages().list(userId="me", maxResults=5, labelIds=["INBOX"]).execute()
        emails = []
        for msg in results.get("messages", []):
            data = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()
            headers = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}
            emails.append({
                "id":      msg["id"],
                "from":    headers.get("From", "Desconocido"),
                "subject": headers.get("Subject", "Sin asunto"),
                "unread":  "UNREAD" in data.get("labelIds", []),
                "time":    headers.get("Date", ""),
            })
        return jsonify(emails)
    except Exception as e:
        print(f"Error in /api/gmail: {e}")
        return jsonify([])

@app.route("/api/expenses", methods=["GET"])
def api_expenses():
    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute(
            """SELECT category, SUM(amount) AS total FROM expenses
               WHERE phone_number = %s
                 AND DATE_TRUNC('month', expense_date) = DATE_TRUNC('month', CURRENT_DATE)
               GROUP BY category ORDER BY total DESC""",
            (DASHBOARD_PHONE,)
        )
        rows = cur.fetchall()
        cur.execute(
            """SELECT COALESCE(SUM(amount), 0) AS grand_total FROM expenses
               WHERE phone_number = %s
                 AND DATE_TRUNC('month', expense_date) = DATE_TRUNC('month', CURRENT_DATE)""",
            (DASHBOARD_PHONE,)
        )
        grand = cur.fetchone()
        cur.close(); conn.close()
        categories = [
            {"name": r["category"], "amount": float(r["total"]), "color": _CATEGORY_COLORS[i % len(_CATEGORY_COLORS)]}
            for i, r in enumerate(rows)
        ]
        return jsonify({"total": float(grand["grand_total"]), "budget": 12000, "categories": categories})
    except Exception as e:
        print(f"Error in /api/expenses: {e}")
        return jsonify({"total": 0, "budget": 12000, "categories": []})

@app.route("/api/goals", methods=["GET"])
def api_goals():
    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute(
            "SELECT id, title, progress FROM goals WHERE phone_number = %s AND completed = FALSE ORDER BY id",
            (DASHBOARD_PHONE,)
        )
        rows = cur.fetchall()
        cur.close(); conn.close()
        COLORS = ["#2563EB", "#059669", "#7C3AED", "#D97706", "#EF4444"]
        return jsonify([
            {"id": r["id"], "title": r["title"], "current": r["progress"], "target": 100, "unit": "%", "color": COLORS[i % len(COLORS)]}
            for i, r in enumerate(rows)
        ])
    except Exception as e:
        print(f"Error in /api/goals: {e}")
        return jsonify([])

@app.route("/api/health", methods=["GET"])
def api_health():
    try:
        conn = get_db_connection()
        cur  = conn.cursor()

        # Sueño hoy
        cur.execute(
            "SELECT value FROM health_logs WHERE phone_number = %s AND log_type = 'sleep' AND log_date = CURRENT_DATE ORDER BY created_at DESC LIMIT 1",
            (DASHBOARD_PHONE,)
        )
        row = cur.fetchone()
        sleep_today = float(row["value"]) if row else None

        # Sueño últimos 7 días
        cur.execute(
            """SELECT log_date, value FROM health_logs
               WHERE phone_number = %s AND log_type = 'sleep'
                 AND log_date >= CURRENT_DATE - INTERVAL '6 days'
               ORDER BY log_date ASC""",
            (DASHBOARD_PHONE,)
        )
        sleep_week = [{"date": str(r["log_date"]), "hours": float(r["value"])} for r in cur.fetchall()]

        # Mood hoy
        cur.execute(
            "SELECT value FROM health_logs WHERE phone_number = %s AND log_type = 'mood' AND log_date = CURRENT_DATE ORDER BY created_at DESC LIMIT 1",
            (DASHBOARD_PHONE,)
        )
        row = cur.fetchone()
        mood_today = int(row["value"]) if row else None

        # Calorías y proteína hoy
        cur.execute(
            "SELECT COALESCE(SUM(calories),0) AS cal, COALESCE(SUM(protein),0) AS prot FROM calorie_logs WHERE phone_number = %s AND log_date = CURRENT_DATE",
            (DASHBOARD_PHONE,)
        )
        row = cur.fetchone()
        calories_today = float(row["cal"]) if row else 0
        protein_today  = float(row["prot"]) if row else 0

        # Medicamentos activos
        cur.execute(
            "SELECT name, dosage, reminder_time FROM medications WHERE phone_number = %s ORDER BY reminder_time ASC NULLS LAST",
            (DASHBOARD_PHONE,)
        )
        meds_rows = cur.fetchall()

        # Determinar cuáles ya fueron tomados hoy (log_type='medication' en health_logs)
        cur.execute(
            "SELECT notes FROM health_logs WHERE phone_number = %s AND log_type = 'medication' AND log_date = CURRENT_DATE",
            (DASHBOARD_PHONE,)
        )
        taken_set = {r["notes"].lower() for r in cur.fetchall()}

        medications = [
            {
                "name": r["name"],
                "dosage": r["dosage"],
                "time": str(r["reminder_time"]) if r["reminder_time"] else None,
                "taken": r["name"].lower() in taken_set,
            }
            for r in meds_rows
        ]

        cur.close(); conn.close()
        return jsonify({
            "sleep_today":    sleep_today,
            "sleep_week":     sleep_week,
            "calories_today": calories_today,
            "protein_today":  protein_today,
            "mood_today":     mood_today,
            "medications":    medications,
        })
    except Exception as e:
        print(f"Error in /api/health: {e}")
        return jsonify({
            "sleep_today": None, "sleep_week": [], "calories_today": 0,
            "protein_today": 0, "mood_today": None, "medications": [],
        })

@app.route("/api/investments", methods=["GET"])
def api_investments():
    import urllib.request as _ur
    import json as _json

    def _yahoo_price(ticker):
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
        try:
            req = _ur.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with _ur.urlopen(req, timeout=6) as r:
                data = _json.loads(r.read())
            return float(data["chart"]["result"][0]["meta"]["regularMarketPrice"])
        except Exception:
            return None

    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute("SELECT ticker, shares, avg_cost FROM investments ORDER BY ticker")
        rows = cur.fetchall()
        cur.close(); conn.close()

        holdings = []
        total_value = 0.0
        total_cost  = 0.0

        for r in rows:
            ticker    = r["ticker"]
            shares    = float(r["shares"])
            avg_cost  = float(r["avg_cost"])
            price     = _yahoo_price(ticker)
            cost_base = shares * avg_cost
            if price is not None:
                value  = shares * price
                gain   = value - cost_base
                gain_pct = (gain / cost_base * 100) if cost_base else 0
            else:
                value = cost_base
                gain  = 0.0
                gain_pct = 0.0
            total_value += value
            total_cost  += cost_base
            holdings.append({
                "ticker":    ticker,
                "shares":    shares,
                "avg_cost":  avg_cost,
                "price":     price,
                "value":     round(value, 2),
                "cost_base": round(cost_base, 2),
                "gain":      round(gain, 2),
                "gain_pct":  round(gain_pct, 2),
            })

        total_gain     = total_value - total_cost
        total_gain_pct = (total_gain / total_cost * 100) if total_cost else 0

        return jsonify({
            "holdings":       holdings,
            "total_value":    round(total_value, 2),
            "total_cost":     round(total_cost, 2),
            "total_gain":     round(total_gain, 2),
            "total_gain_pct": round(total_gain_pct, 2),
        })
    except Exception as e:
        print(f"Error in /api/investments: {e}")
        return jsonify({
            "holdings": [], "total_value": 0, "total_cost": 0,
            "total_gain": 0, "total_gain_pct": 0,
        })

@app.route("/api/investments/<ticker>", methods=["DELETE"])
def api_investments_delete(ticker):
    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute(
            "DELETE FROM investments WHERE ticker = %s RETURNING ticker",
            (ticker.upper(),)
        )
        deleted = cur.fetchone()
        conn.commit()
        cur.close(); conn.close()
        if deleted:
            return jsonify({"ok": True, "ticker": deleted["ticker"]}), 200
        return jsonify({"ok": False, "error": "ticker not found"}), 404
    except Exception as e:
        print(f"Error in DELETE /api/investments/{ticker}: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

# ─── PORTFOLIO SNAPSHOT HELPERS ──────────────────────────────────────────────

def _yahoo_price_simple(ticker):
    import urllib.request as _ur, json as _json
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
        req = _ur.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with _ur.urlopen(req, timeout=6) as r:
            data = _json.loads(r.read())
        return float(data["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except Exception:
        return None

def _take_portfolio_snapshot():
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute("SELECT ticker, shares, avg_cost FROM investments ORDER BY ticker")
    rows = cur.fetchall()
    total_value = 0.0
    total_cost  = 0.0
    for r in rows:
        shares   = float(r["shares"])
        avg_cost = float(r["avg_cost"])
        price    = _yahoo_price_simple(r["ticker"])
        cost_base = shares * avg_cost
        total_value += shares * price if price else cost_base
        total_cost  += cost_base
    cur.execute("""
        INSERT INTO portfolio_snapshots (snapshot_date, total_value, total_cost)
        VALUES (CURRENT_DATE, %s, %s)
        ON CONFLICT (snapshot_date) DO UPDATE
        SET total_value = EXCLUDED.total_value, total_cost = EXCLUDED.total_cost
    """, (round(total_value, 2), round(total_cost, 2)))
    conn.commit()
    cur.close(); conn.close()
    return {"total_value": round(total_value, 2), "total_cost": round(total_cost, 2)}

@app.route("/api/investments/snapshot", methods=["POST"])
def api_investments_snapshot():
    try:
        result = _take_portfolio_snapshot()
        return jsonify({"ok": True, **result})
    except Exception as e:
        print(f"Error in POST /api/investments/snapshot: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/investments/performance", methods=["GET"])
def api_investments_performance():
    try:
        from datetime import date, timedelta
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute("""
            SELECT snapshot_date, total_value FROM portfolio_snapshots
            WHERE snapshot_date IN (
                CURRENT_DATE,
                CURRENT_DATE - INTERVAL '1 day',
                CURRENT_DATE - INTERVAL '7 days',
                CURRENT_DATE - INTERVAL '30 days',
                CURRENT_DATE - INTERVAL '365 days'
            )
        """)
        snap = {str(r["snapshot_date"]): float(r["total_value"]) for r in cur.fetchall()}
        cur.close(); conn.close()

        today     = date.today()
        today_val = snap.get(str(today))

        def _gain(prev_key):
            prev = snap.get(str(today - timedelta(days=prev_key)))
            if today_val is None or prev is None:
                return {"usd": None, "pct": None}
            usd = round(today_val - prev, 2)
            pct = round((usd / prev) * 100, 2) if prev else 0
            return {"usd": usd, "pct": pct}

        return jsonify({
            "today_value": today_val,
            "day_gain":   _gain(1),
            "week_gain":  _gain(7),
            "month_gain": _gain(30),
            "year_gain":  _gain(365),
        })
    except Exception as e:
        print(f"Error in /api/investments/performance: {e}")
        return jsonify({"today_value": None, "day_gain": {}, "week_gain": {}, "month_gain": {}, "year_gain": {}})

@app.route("/api/investments/history", methods=["GET"])
def api_investments_history():
    try:
        year  = request.args.get("year",  type=int)
        month = request.args.get("month", type=int)
        if not year or not month:
            from datetime import date
            today = date.today()
            year, month = today.year, today.month

        conn = get_db_connection()
        cur  = conn.cursor()

        # Fetch the month's snapshots plus the last day of prev month (for day-over-day calc)
        cur.execute("""
            SELECT snapshot_date, total_value, total_cost
            FROM portfolio_snapshots
            WHERE (EXTRACT(YEAR  FROM snapshot_date) = %s
                   AND EXTRACT(MONTH FROM snapshot_date) = %s)
               OR snapshot_date = (
                   SELECT MAX(snapshot_date) FROM portfolio_snapshots
                   WHERE snapshot_date < make_date(%s, %s, 1)
               )
            ORDER BY snapshot_date ASC
        """, (year, month, year, month))
        rows = cur.fetchall()
        cur.close(); conn.close()

        results = []
        prev_value = None
        for r in rows:
            d     = r["snapshot_date"]
            val   = float(r["total_value"])
            cost  = float(r["total_cost"])
            gain       = round(val - cost, 2)
            gain_pct   = round((gain / cost * 100) if cost else 0, 2)
            if prev_value is not None:
                g_day     = round(val - prev_value, 2)
                g_day_pct = round((g_day / prev_value * 100) if prev_value else 0, 2)
            else:
                g_day = g_day_pct = None
            prev_value = val

            # Only include days within the requested month
            if d.month == month and d.year == year:
                results.append({
                    "date":                  str(d),
                    "total_value":           val,
                    "total_cost":            cost,
                    "gain":                  gain,
                    "gain_pct":              gain_pct,
                    "gain_vs_prev_day":      g_day,
                    "gain_vs_prev_day_pct":  g_day_pct,
                })

        return jsonify(results)
    except Exception as e:
        print(f"Error in /api/investments/history: {e}")
        return jsonify([])

@app.route("/api/investments/trade", methods=["POST"])
def api_investments_trade():
    data   = request.get_json() or {}
    action = data.get("action", "").lower()
    ticker = (data.get("ticker") or "").upper().strip()
    shares = float(data.get("shares", 0) or 0)
    price  = data.get("price")

    if not action or not ticker or shares <= 0:
        return jsonify({"ok": False, "error": "Parámetros inválidos: se requieren action, ticker y shares > 0"}), 400
    if action not in ("buy", "sell"):
        return jsonify({"ok": False, "error": "action debe ser 'buy' o 'sell'"}), 400

    try:
        conn = get_db_connection()
        cur  = conn.cursor()

        if action == "sell":
            cur.execute("SELECT shares, avg_cost FROM investments WHERE ticker = %s", (ticker,))
            row = cur.fetchone()
            if not row:
                cur.close(); conn.close()
                return jsonify({"ok": False, "error": f"No hay posición abierta para {ticker}"}), 404
            new_shares = round(float(row["shares"]) - shares, 6)
            if new_shares <= 0:
                cur.execute("DELETE FROM investments WHERE ticker = %s", (ticker,))
                result = {"ticker": ticker, "shares": 0, "avg_cost": 0, "deleted": True}
            else:
                cur.execute(
                    "UPDATE investments SET shares = %s WHERE ticker = %s RETURNING shares, avg_cost",
                    (new_shares, ticker)
                )
                r = cur.fetchone()
                result = {"ticker": ticker, "shares": float(r["shares"]), "avg_cost": float(r["avg_cost"]), "deleted": False}

        else:  # buy
            if price is None:
                cur.close(); conn.close()
                return jsonify({"ok": False, "error": "Se requiere price para compras"}), 400
            price = float(price)
            cur.execute("SELECT shares, avg_cost FROM investments WHERE ticker = %s", (ticker,))
            row = cur.fetchone()
            if row:
                prev_shares = float(row["shares"])
                prev_cost   = float(row["avg_cost"])
                new_shares  = prev_shares + shares
                new_avg     = round(((prev_shares * prev_cost) + (shares * price)) / new_shares, 2)
                cur.execute(
                    "UPDATE investments SET shares = %s, avg_cost = %s WHERE ticker = %s RETURNING shares, avg_cost",
                    (new_shares, new_avg, ticker)
                )
            else:
                cur.execute(
                    "INSERT INTO investments (ticker, shares, avg_cost) VALUES (%s, %s, %s) RETURNING shares, avg_cost",
                    (ticker, shares, round(price, 2))
                )
            r = cur.fetchone()
            result = {"ticker": ticker, "shares": float(r["shares"]), "avg_cost": float(r["avg_cost"]), "deleted": False}

        conn.commit()
        cur.close(); conn.close()
        return jsonify({"ok": True, **result})
    except Exception as e:
        print(f"Error in /api/investments/trade: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/calendar/month", methods=["GET"])
def api_calendar_month():
    try:
        from calendar_helper import get_calendar_service
        import calendar as cal_mod
        year  = int(request.args.get("year",  datetime.datetime.now().year))
        month = int(request.args.get("month", datetime.datetime.now().month))
        service = get_calendar_service()
        if not service:
            return jsonify([])
        first_day = datetime.datetime(year, month, 1)
        last_day  = datetime.datetime(year, month, cal_mod.monthrange(year, month)[1], 23, 59, 59)
        result = service.events().list(
            calendarId=os.getenv("GOOGLE_CALENDAR_ID", "primary"),
            timeMin=first_day.isoformat() + "Z",
            timeMax=last_day.isoformat() + "Z",
            singleEvents=True, orderBy="startTime"
        ).execute()
        events = []
        for ev in result.get("items", []):
            start_raw = ev["start"].get("dateTime", ev["start"].get("date", ""))
            end_raw   = ev["end"].get("dateTime",   ev["end"].get("date",   ""))
            events.append({
                "id":          ev.get("id"),
                "title":       ev.get("summary", "Sin título"),
                "description": ev.get("description", ""),
                "date":        start_raw[:10],
                "startTime":   start_raw[11:16] if "T" in start_raw else "",
                "endTime":     end_raw[11:16]   if "T" in end_raw   else "",
                "allDay":      "T" not in start_raw,
            })
        return jsonify(events)
    except Exception as e:
        print(f"Error in /api/calendar/month: {e}")
        return jsonify([])


@app.route("/api/calendar/create", methods=["POST"])
def api_calendar_create():
    try:
        from calendar_helper import get_calendar_service
        data        = request.get_json() or {}
        title       = (data.get("title") or "").strip()
        date        = (data.get("date") or "").strip()        # YYYY-MM-DD
        start_time  = (data.get("startTime") or "").strip()  # HH:MM
        end_time    = (data.get("endTime") or "").strip()    # HH:MM
        description = (data.get("description") or "").strip()
        if not title or not date:
            return jsonify({"ok": False, "error": "title y date son requeridos"}), 400
        service = get_calendar_service()
        if not service:
            return jsonify({"ok": False, "error": "No se pudo conectar con Google Calendar"}), 503
        tz_offset = "-06:00"
        if start_time and end_time:
            start_iso = f"{date}T{start_time}:00{tz_offset}"
            end_iso   = f"{date}T{end_time}:00{tz_offset}"
            start_spec = {"dateTime": start_iso, "timeZone": "America/Monterrey"}
            end_spec   = {"dateTime": end_iso,   "timeZone": "America/Monterrey"}
        else:
            import datetime as _dt
            next_day = (_dt.date.fromisoformat(date) + _dt.timedelta(days=1)).isoformat()
            start_spec = {"date": date}
            end_spec   = {"date": next_day}
        body = {"summary": title, "start": start_spec, "end": end_spec}
        if description:
            body["description"] = description
        ev = service.events().insert(
            calendarId=os.getenv("GOOGLE_CALENDAR_ID", "primary"), body=body
        ).execute()
        return jsonify({
            "ok": True,
            "id":        ev.get("id"),
            "title":     ev.get("summary"),
            "htmlLink":  ev.get("htmlLink"),
        })
    except Exception as e:
        print(f"Error in /api/calendar/create: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/calendar/event/<event_id>", methods=["DELETE"])
def api_calendar_delete(event_id):
    try:
        from calendar_helper import get_calendar_service
        service = get_calendar_service()
        if not service:
            return jsonify({"ok": False, "error": "No se pudo conectar con Google Calendar"}), 503
        service.events().delete(
            calendarId=os.getenv("GOOGLE_CALENDAR_ID", "primary"),
            eventId=event_id
        ).execute()
        return jsonify({"ok": True})
    except Exception as e:
        print(f"Error in /api/calendar/event DELETE: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/mail/send", methods=["POST"])
def api_mail_send():
    try:
        from gmail_helper import send_email
        data = request.get_json() or {}
        to      = (data.get("to") or "").strip()
        subject = (data.get("subject") or "").strip()
        body    = (data.get("body") or "").strip()
        if not to or not subject or not body:
            return jsonify({"ok": False, "error": "to, subject, body son requeridos"}), 400
        result = send_email(to=to, subject=subject, body=body)
        if isinstance(result, str) and "Error" in result:
            return jsonify({"ok": False, "error": result}), 500
        return jsonify({"ok": True, "message": "Email enviado"})
    except Exception as e:
        print(f"Error in /api/mail/send: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ─── TRADING AGENT ENDPOINTS ──────────────────────────────────────────────────────

@app.route("/api/trading/config", methods=["POST"])
def api_trading_config():
    """Save Binance API credentials (encrypted) and auto_execute preference"""
    try:
        data = request.get_json() or {}
        api_key = (data.get("api_key") or "").strip()
        api_secret = (data.get("api_secret") or "").strip()
        auto_execute = data.get("auto_execute", False)

        if not api_key or not api_secret:
            return jsonify({"ok": False, "error": "api_key y api_secret son requeridos"}), 400

        encrypted_key = _encrypt(api_key)
        encrypted_secret = _encrypt(api_secret)

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO trading_config (binance_api_key, binance_secret, auto_execute) VALUES (%s, %s, %s) "
            "ON CONFLICT (id) DO UPDATE SET binance_api_key=%s, binance_secret=%s, auto_execute=%s, updated_at=NOW()",
            (encrypted_key, encrypted_secret, auto_execute, encrypted_key, encrypted_secret, auto_execute)
        )
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"ok": True, "message": "Configuración guardada"})
    except Exception as e:
        print(f"Error in /api/trading/config: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/trading/config/status", methods=["GET"])
def api_trading_config_status():
    """Check if Binance config is set and auto_execute status"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, auto_execute FROM trading_config LIMIT 1")
        config = cur.fetchone()
        cur.close()
        conn.close()

        return jsonify({
            "ok": True,
            "configured": config is not None,
            "auto_execute": config["auto_execute"] if config else False
        })
    except Exception as e:
        print(f"Error in /api/trading/config/status: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/trading/strategy", methods=["POST"])
def api_trading_strategy():
    """Save or update a trading strategy"""
    try:
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        prompt = (data.get("prompt") or "").strip()
        active = data.get("active", False)

        if not name or not prompt:
            return jsonify({"ok": False, "error": "name y prompt son requeridos"}), 400

        conn = get_db_connection()
        cur = conn.cursor()

        # If active=True, deactivate other strategies
        if active:
            cur.execute("UPDATE trading_strategies SET active=FALSE")

        # Insert or update
        cur.execute(
            "INSERT INTO trading_strategies (name, prompt, active) VALUES (%s, %s, %s) "
            "ON CONFLICT (name) DO UPDATE SET prompt=%s, active=%s",
            (name, prompt, active, prompt, active)
        )
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"ok": True, "message": "Estrategia guardada"})
    except Exception as e:
        print(f"Error in /api/trading/strategy: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/trading/analyze", methods=["POST"])
def api_trading_analyze():
    """Analyze market with Claude and create a pending signal"""
    try:
        data = request.get_json() or {}
        asset = (data.get("asset") or "BTC/USDT").strip().upper()

        conn = get_db_connection()
        cur = conn.cursor()

        # Get active strategy
        cur.execute("SELECT id, prompt FROM trading_strategies WHERE active=TRUE LIMIT 1")
        strategy = cur.fetchone()

        if not strategy:
            cur.close()
            conn.close()
            return jsonify({"ok": False, "error": "No hay estrategia activa"}), 400

        # Get current price (mock data for MVP)
        # In production: use Binance API or CoinGecko
        price = 42500 if asset == "BTC/USDT" else 2300
        change_24h = 2.5

        # Call Claude with strategy prompt
        prompt_text = f"""
        Eres un agente de trading de criptomonedas experimentado.

        Estrategia: {strategy['prompt']}

        Datos de mercado actuales:
        - Asset: {asset}
        - Precio actual: ${price}
        - Cambio 24h: {change_24h}%

        Basado en la estrategia y los datos, responde con un JSON con:
        {{
            "action": "buy" | "sell" | "hold",
            "amount": número,
            "reasoning": "explicación breve",
            "confidence": 0-1
        }}
        """

        message = anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt_text}]
        )

        response_text = message.content[0].text
        # Extract JSON from response
        import re
        json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            signal_data = json.loads(json_match.group(0))
        else:
            signal_data = {"action": "hold", "amount": 0, "reasoning": response_text, "confidence": 0.5}

        # Insert signal
        cur.execute(
            "INSERT INTO trading_signals (asset, action, price, amount, strategy_id, reasoning, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (asset, signal_data.get("action", "hold"), price, signal_data.get("amount", 0),
             strategy['id'], signal_data.get("reasoning", ""), "pending")
        )
        signal_id = cur.fetchone()['id']

        # Auto-execute if auto_execute=True and confidence > 0.8
        cur.execute("SELECT auto_execute FROM trading_config LIMIT 1")
        config = cur.fetchone()
        confidence = signal_data.get("confidence", 0.5)

        if config and config["auto_execute"] and confidence > 0.8:
            cur.execute(
                "UPDATE trading_signals SET status=%s, executed_at=%s WHERE id=%s",
                ("executed", datetime.now(), signal_id)
            )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "ok": True,
            "signal_id": signal_id,
            "action": signal_data.get("action", "hold"),
            "amount": signal_data.get("amount", 0),
            "confidence": confidence,
            "auto_executed": config and config["auto_execute"] and confidence > 0.8
        })
    except Exception as e:
        print(f"Error in /api/trading/analyze: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/trading/signals", methods=["GET"])
def api_trading_signals():
    """Get pending signals for approval"""
    try:
        status = request.args.get("status", "pending").strip()
        limit = int(request.args.get("limit", 10))

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, asset, action, price, amount, reasoning, status, created_at FROM trading_signals "
            "WHERE status=%s ORDER BY created_at DESC LIMIT %s",
            (status, limit)
        )
        signals = cur.fetchall()
        cur.close()
        conn.close()

        return jsonify({
            "ok": True,
            "signals": [dict(s) for s in signals]
        })
    except Exception as e:
        print(f"Error in /api/trading/signals: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/trading/execute", methods=["POST"])
def api_trading_execute():
    """Approve/reject and execute a signal"""
    try:
        data = request.get_json() or {}
        signal_id = data.get("signal_id")
        approved = data.get("approved", False)

        if not signal_id:
            return jsonify({"ok": False, "error": "signal_id es requerido"}), 400

        conn = get_db_connection()
        cur = conn.cursor()

        if approved:
            # Mark as executed (in MVP, just update status)
            # In production: integrate with Binance API
            cur.execute(
                "UPDATE trading_signals SET status=%s, executed_at=%s WHERE id=%s",
                ("executed", datetime.now(), signal_id)
            )
        else:
            # Mark as rejected
            cur.execute(
                "UPDATE trading_signals SET status=%s WHERE id=%s",
                ("rejected", signal_id)
            )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"ok": True, "message": "Signal updated"})
    except Exception as e:
        print(f"Error in /api/trading/execute: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/trading/history", methods=["GET"])
def api_trading_history():
    """Get trading execution history"""
    try:
        limit = int(request.args.get("limit", 20))

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, asset, action, price, amount, status, executed_at, created_at FROM trading_signals "
            "WHERE status IN ('executed', 'rejected') ORDER BY created_at DESC LIMIT %s",
            (limit,)
        )
        history = cur.fetchall()
        cur.close()
        conn.close()

        return jsonify({
            "ok": True,
            "history": [dict(h) for h in history]
        })
    except Exception as e:
        print(f"Error in /api/trading/history: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ─── AUTH ENDPOINTS ────────────────────────────────────────────────────────────

@app.route("/api/auth/register", methods=["POST"])
def register():
    """Register a new user (admin only, requires ADMIN_SECRET)"""
    try:
        data = request.get_json()
        email = data.get("email", "").strip()
        password = data.get("password", "").strip()
        name = data.get("name", "").strip()
        admin_secret = data.get("admin_secret", "")

        # Validate admin secret
        if not ADMIN_SECRET or admin_secret != ADMIN_SECRET:
            return jsonify({"ok": False, "error": "Invalid admin secret"}), 401

        # Validate inputs
        if not email or not password:
            return jsonify({"ok": False, "error": "Email and password required"}), 400

        # Hash password with bcrypt (rounds=12)
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

        # Insert user into database
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users (email, password_hash, name) VALUES (%s, %s, %s) RETURNING id, email, name",
                (email, password_hash, name)
            )
            user = cur.fetchone()
            conn.commit()
            user_id = user['id']
        except psycopg2.IntegrityError:
            conn.rollback()
            cur.close()
            conn.close()
            return jsonify({"ok": False, "error": "Email already exists"}), 400
        finally:
            cur.close()
            conn.close()

        # Create JWT token (expires in 24 hours)
        payload = {
            "user_id": user_id,
            "email": user['email'],
            "name": user['name'],
            "exp": datetime.utcnow() + timedelta(hours=24)
        }
        token = pyjwt.encode(payload, JWT_SECRET, algorithm="HS256")

        return jsonify({"ok": True, "token": token}), 201
    except Exception as e:
        print(f"Error in /api/auth/register: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/auth/login", methods=["POST"])
def login():
    """Login with email and password"""
    try:
        data = request.get_json()
        email = data.get("email", "").strip()
        password = data.get("password", "").strip()

        if not email or not password:
            return jsonify({"ok": False, "error": "Email and password required"}), 400

        # Get user from database
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, email, name, password_hash FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if not user:
            return jsonify({"ok": False, "error": "Invalid email or password"}), 401

        # Verify password with bcrypt
        if not bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
            return jsonify({"ok": False, "error": "Invalid email or password"}), 401

        # Create JWT token (expires in 24 hours)
        payload = {
            "user_id": user['id'],
            "email": user['email'],
            "name": user['name'],
            "exp": datetime.utcnow() + timedelta(hours=24)
        }
        token = pyjwt.encode(payload, JWT_SECRET, algorithm="HS256")

        return jsonify({
            "ok": True,
            "token": token,
            "user": {
                "email": user['email'],
                "name": user['name']
            }
        }), 200
    except Exception as e:
        print(f"Error in /api/auth/login: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/auth/verify", methods=["GET"])
def verify():
    """Verify JWT token from Authorization header"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"ok": False, "error": "Missing or invalid Authorization header"}), 401

        token = auth_header[7:]  # Remove "Bearer " prefix

        # Decode JWT
        try:
            payload = pyjwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        except pyjwt.ExpiredSignatureError:
            return jsonify({"ok": False, "error": "Token expired"}), 401
        except pyjwt.InvalidTokenError:
            return jsonify({"ok": False, "error": "Invalid token"}), 401

        return jsonify({
            "ok": True,
            "user": {
                "email": payload['email'],
                "name": payload['name']
            }
        }), 200
    except Exception as e:
        print(f"Error in /api/auth/verify: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    # Bind to 0.0.0.0 to work on Render, read port from environment (Render sets PORT)
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
# updated
