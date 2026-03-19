import os
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import psycopg2.extras
from twilio.rest import Client
from calendar_helper import get_todays_events
import psycopg2

def send_morning_briefing():
    """
    Fetches today's events and sends a WhatsApp message summarizing the day.
    """
    print("Executing Morning Briefing Job...")
    
    # 1. Fetch Today's Events
    agenda = get_todays_events()
    
    # 2. Format Message
    message_body = "☀️ *Buenos días, Jarvis aquí con tu resumen del día:*\n\n"
    
    # 2. Fetch Today's Tasks
    target_number = "5218129354808"
    database_url = os.getenv("DATABASE_URL")
    tasks_str = ""
    if database_url:
        try:
            conn = psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)
            cur = conn.cursor()
            cur.execute("SELECT * FROM tasks WHERE phone_number = %s AND task_date = CURRENT_DATE ORDER BY created_at ASC", (target_number,))
            tasks = cur.fetchall()
            cur.close()
            conn.close()
            if tasks:
                tasks_str = "📋 *Tus tareas programadas para hoy:*\n"
                for t in tasks:
                    status = "✅" if t['completed'] else "⏳"
                    tasks_str += f"{status} #{t['id']} — {t['task']}\n"
                tasks_str += "\n"
        except Exception as e:
            print(f"Error fetching tasks for morning briefing: {e}")
            
    if "No tienes ningún evento" in agenda or "No pude conectarme" in agenda or "Ocurrió un error" in agenda:
        message_body += "No tienes eventos programados para hoy en tu calendario. "
    else:
        # agenda string already contains the formatted events list from calendar_helper
        message_body += agenda + "\n\n"
        
    if tasks_str:
        message_body += tasks_str
    else:
        message_body += "No tienes tareas pendientes para hoy. "
        
    message_body += "\n¡Que tengas un excelente y productivo día!"
    
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

def send_hourly_alerts():
    """
    Checks for new important emails every hour and sends a WhatsApp alert if any are found.
    Ensures no duplicate alerts using the email_alerts DB table.
    """
    print("Executing Hourly Email Alerts Job...")
    from gmail_helper import check_important_emails
    
    important_emails = check_important_emails()
    if not important_emails:
        return
        
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("Error: DATABASE_URL not configured for hourly alerts.")
        return
        
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_number = os.getenv("TWILIO_WHATSAPP_NUMBER")
    target_number = "whatsapp:+5218129354808"
    
    if not all([account_sid, auth_token, twilio_number]):
        print("Error: Twilio credentials not fully configured.")
        return
        
    client = Client(account_sid, auth_token)
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        for email in important_emails:
            gmail_id = email['id']
            # Check if alerted already
            cur.execute("SELECT 1 FROM email_alerts WHERE gmail_id = %s", (gmail_id,))
            if cur.fetchone():
                continue # Already alerted
                
            sender = email['sender']
            subject = email['subject']
            message_body = f"🚨 *Jarvis Alert* — Tienes un email importante:\n📧 De: {sender}\n📋 Asunto: {subject}"
            
            try:
                # Send alert
                message = client.messages.create(
                    from_=twilio_number,
                    body=message_body,
                    to=target_number
                )
                print(f"Alert sent successfully. SID: {message.sid}")
                
                # Save to DB to avoid duplicates
                cur.execute("INSERT INTO email_alerts (gmail_id) VALUES (%s) ON CONFLICT DO NOTHING", (gmail_id,))
                conn.commit()
            except Exception as msg_e:
                print(f"Failed to send alert via Twilio for {gmail_id}: {msg_e}")
                
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Database error in hourly alerts: {e}")

def send_evening_summary():
    print("Executing Evening Summary Job...")
    database_url = os.getenv("DATABASE_URL")
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_number = os.getenv("TWILIO_WHATSAPP_NUMBER")
    target_number = "whatsapp:+5218129354808"
    
    if not all([database_url, account_sid, auth_token, twilio_number]):
        return
        
    client = Client(account_sid, auth_token)
    try:
        conn = psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        
        phone = "5218129354808"
        cur.execute("SELECT * FROM tasks WHERE phone_number = %s AND task_date = CURRENT_DATE", (phone,))
        tasks = cur.fetchall()
        
        if tasks:
            task_list = ["🌙 *Resumen del día* — ¿Cuáles cumpliste?\n"]
            for t in tasks:
                status = "✅" if t['completed'] else "⏳"
                task_list.append(f"{status} #{t['id']} — {t['task']}")
                
            task_list.append("\nResponde: 'listo #1 #3' para marcar como cumplidas")
            
            message = client.messages.create(
                from_=twilio_number,
                body="\n".join(task_list),
                to=target_number
            )
            print("Evening summary sent")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error in send_evening_summary: {e}")

def cleanup_daily_tasks():
    print("Executing Task Cleanup Job...")
    database_url = os.getenv("DATABASE_URL")
    if not database_url: return
    try:
        conn = psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        
        phone = "5218129354808"
        cur.execute("SELECT COUNT(*) as total, COUNT(NULLIF(completed, false)) as completed FROM tasks WHERE phone_number = %s AND task_date = CURRENT_DATE", (phone,))
        stats = cur.fetchone()
        
        if stats and stats['total'] > 0:
            cur.execute("INSERT INTO task_stats (phone_number, stat_date, total_tasks, completed_tasks) VALUES (%s, CURRENT_DATE, %s, %s)",
                       (phone, stats['total'], stats['completed']))
            cur.execute("DELETE FROM tasks WHERE phone_number = %s AND task_date = CURRENT_DATE", (phone,))
            conn.commit()
            print("Daily tasks cleaned up and stats saved.")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error in cleanup_daily_tasks: {e}")

def send_monthly_report():
    print("Executing Monthly Report Job...")
    database_url = os.getenv("DATABASE_URL")
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_number = os.getenv("TWILIO_WHATSAPP_NUMBER")
    target_number = "whatsapp:+5218129354808"
    
    if not all([database_url, account_sid, auth_token, twilio_number]):
        return
        
    client = Client(account_sid, auth_token)
    try:
        conn = psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        
        phone = "5218129354808"
        cur.execute("SELECT SUM(total_tasks) as total, SUM(completed_tasks) as completed FROM task_stats WHERE phone_number = %s AND stat_date >= date_trunc('month', CURRENT_DATE - INTERVAL '1 month') AND stat_date < date_trunc('month', CURRENT_DATE)", (phone,))
        stats = cur.fetchone()
        
        if stats and stats['total'] and stats['total'] > 0:
            percentage = round((stats['completed'] / stats['total']) * 100, 1)
            body = f"📊 *Reporte Mensual de Productividad*\nEl mes pasado tuviste {stats['total']} tareas y completaste {stats['completed']} ({percentage}% de cumplimiento)."
            client.messages.create(
                from_=twilio_number,
                body=body,
                to=target_number
            )
            print("Monthly report sent.")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error in send_monthly_report: {e}")

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
    
    # Schedule hourly email alerts
    scheduler.add_job(
        func=send_hourly_alerts,
        trigger="interval",
        hours=1,
        id="hourly_email_alerts",
        replace_existing=True
    )
    
    # Schedule evening summary at 10:00 PM
    scheduler.add_job(
        func=send_evening_summary,
        trigger="cron",
        hour=22,
        minute=0,
        id="evening_summary_job",
        replace_existing=True
    )
    
    # Schedule cleanup at 11:59 PM
    scheduler.add_job(
        func=cleanup_daily_tasks,
        trigger="cron",
        hour=23,
        minute=59,
        id="cleanup_tasks_job",
        replace_existing=True
    )
    
    # Schedule monthly report (Day 1 of each month at 09:00 AM)
    scheduler.add_job(
        func=send_monthly_report,
        trigger="cron",
        day=1,
        hour=9,
        minute=0,
        id="monthly_report_job",
        replace_existing=True
    )
    
    scheduler.start()
    print("Background scheduler started containing all alerts, briefings, and productivity jobs.")
