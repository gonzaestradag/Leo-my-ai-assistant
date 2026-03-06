import os
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
from twilio.rest import Client
from calendar_helper import get_todays_events

def send_morning_briefing():
    """
    Fetches today's events and sends a WhatsApp message summarizing the day.
    """
    print("Executing Morning Briefing Job...")
    
    # 1. Fetch Today's Events
    agenda = get_todays_events()
    
    # 2. Format Message
    message_body = "☀️ *Buenos días, Jarvis aquí con tu resumen del día:*\n\n"
    
    if "No tienes ningún evento" in agenda or "No pude conectarme" in agenda or "Ocurrió un error" in agenda:
        message_body += "No tienes eventos programados para hoy en tu calendario. ¡Que tengas un excelente día y aprovecha para relajarte o adelantar pendientes!"
    else:
        # agenda string already contains the formatted events list from calendar_helper
        message_body += agenda + "\n\n¡Que tengas un excelente y productivo día!"
    
    # 3. Send via Twilio
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_number = os.getenv("TWILIO_WHATSAPP_NUMBER")
    
    # The specific number the user requested
    target_number = "whatsapp:+5218129354808"
    
    if not all([account_sid, auth_token, twilio_number]):
        print("Error: Twilio credentials not fully configured in environment variables.")
        return
        
    try:
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            from_=twilio_number,
            body=message_body,
            to=target_number
        )
        print(f"Morning Briefing sent successfully! Message SID: {message.sid}")
    except Exception as e:
        print(f"Failed to send morning briefing via Twilio: {e}")

def start_scheduler():
    """
    Initializes and starts the APScheduler.
    """
    # Use Mexico City Timezone (GMT-6)
    mx_tz = pytz.timezone('America/Mexico_City')
    
    scheduler = BackgroundScheduler(timezone=mx_tz)
    
    # Schedule to run every day at 08:20 AM
    scheduler.add_job(
        func=send_morning_briefing,
        trigger="cron",
        hour=8,
        minute=20,
        id="morning_briefing_job",
        replace_existing=True
    )
    
    scheduler.start()
    print("Background scheduler started. Morning Briefing scheduled for 08:20 AM (Mexico City Time).")
