import os
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import psycopg2.extras
from twilio.rest import Client
from calendar_helper import get_todays_events
import psycopg2

def get_weather():
    try:
        import requests
        # Coordenadas de Monterrey, México
        url = "https://api.open-meteo.com/v1/forecast?latitude=25.6866&longitude=-100.3161&current=temperature_2m,weathercode,windspeed_10m&timezone=America%2FMexico_City&temperature_unit=celsius"
        response = requests.get(url, timeout=5)
        data = response.json()
        temp = data['current']['temperature_2m']
        code = data['current']['weathercode']
        wind = data['current']['windspeed_10m']
        weather_descriptions = {
            0: "☀️ Despejado", 1: "🌤️ Mayormente despejado", 2: "⛅ Parcialmente nublado",
            3: "☁️ Nublado", 45: "🌫️ Neblina", 48: "🌫️ Neblina",
            51: "🌦️ Llovizna", 61: "🌧️ Lluvia", 71: "❄️ Nieve",
            80: "🌧️ Chubascos", 95: "⛈️ Tormenta"
        }
        desc = weather_descriptions.get(code, "🌡️ Variable")
        return f"{desc} | {temp}°C | Viento: {wind} km/h"
    except Exception as e:
        return "Clima no disponible"

def get_news():
    try:
        import requests
        import xml.etree.ElementTree as ET
        url = "https://news.google.com/rss?hl=es-419&gl=MX&ceid=MX:es-419"
        response = requests.get(url, timeout=5)
        root = ET.fromstring(response.content)
        items = root.findall('.//item')[:3]
        news_list = []
        for item in items:
            title = item.find('title').text
            # Limpiar el título quitando el nombre del medio al final
            if ' - ' in title:
                title = title.rsplit(' - ', 1)[0]
            news_list.append(f"• {title}")
        return "\n".join(news_list)
    except Exception as e:
        return "Noticias no disponibles"

def send_morning_briefing():
    """
    Fetches today's events, tasks, weather, and news, and sends a WhatsApp message summarizing the day.
    """
    print("Executing Morning Briefing Job...")
    
    # 1. Fetch Today's Events
    agenda = get_todays_events()
    if "No tienes ningún evento" in agenda or "No pude conectarme" in agenda or "Ocurrió un error" in agenda:
        eventos_str = "Sin eventos hoy"
    else:
        eventos_str = agenda
    
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
                tasks_list = []
                for t in tasks:
                    status = "✅" if t['completed'] else "⏳"
                    tasks_list.append(f"{status} #{t['id']} — {t['task']}")
                tasks_str = "\n".join(tasks_list)
        except Exception as e:
            print(f"Error fetching tasks for morning briefing: {e}")
            
    if not tasks_str:
        tasks_str = "Sin pendientes"
        
    # 3. Fetch Weather & News
    clima = get_weather()
    noticias = get_news()
    
    # 4. Format Message
    message_body = f"""☀️ *Buenos días, Leo! Aquí tu resumen del día:*

📅 *Eventos de hoy:*
{eventos_str}

✅ *Pendientes de hoy:*
{tasks_str}

🌤️ *Clima en Monterrey:*
{clima}

📰 *Noticias de hoy:*
{noticias}

¡Que tengas un excelente día! 💪"""
    
    # 5. Send via Twilio
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_number = os.getenv("TWILIO_WHATSAPP_NUMBER")
    target_twilio_number = "whatsapp:+5218129354808"
    
    if not all([account_sid, auth_token, twilio_number]):
        print("Error: Twilio credentials not fully configured in environment variables.")
        return
        
    try:
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            from_=twilio_number,
            body=message_body,
            to=target_twilio_number
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

def reset_weekly_salary():
    print("Executing Weekly Salary Reset Job...")
    database_url = os.getenv("DATABASE_URL")
    if not database_url: return
    try:
        conn = psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        
        phone = "5218129354808"
        amount = 2500.00
        # Insert this week's salary
        cur.execute("INSERT INTO salary (phone_number, amount) VALUES (%s, %s)", (phone, amount))
        conn.commit()
        print(f"Weekly salary of {amount} registered for {phone}.")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error in reset_weekly_salary: {e}")

def send_portfolio_weekly_report():
    print("Executing Weekly Portfolio Report Job...")
    database_url = os.getenv("DATABASE_URL")
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_number = os.getenv("TWILIO_WHATSAPP_NUMBER")
    target_number = "whatsapp:+5218129354808"
    
    if not all([database_url, account_sid, auth_token, twilio_number]):
        return
        
    client = Client(account_sid, auth_token)
    try:
        from finance_helper import get_weekly_report
        phone = "5218129354808"
        report_text = get_weekly_report(phone)
        if report_text and "No tienes acciones" not in report_text:
            client.messages.create(
                from_=twilio_number,
                body=report_text,
                to=target_number
            )
            print("Weekly portfolio report sent.")
    except Exception as e:
        print(f"Error in send_portfolio_weekly_report: {e}")

def start_scheduler():
    """
    Initializes and starts the APScheduler.
    """
    # Use Mexico City Timezone (GMT-6)
    mx_tz = pytz.timezone('America/Mexico_City')
    
    scheduler = BackgroundScheduler(timezone=mx_tz)
    
    # Schedule to run every day at 08:20 AM
    if not scheduler.get_job("morning_briefing_job"):
        scheduler.add_job(
            func=send_morning_briefing,
            trigger="cron",
            hour=8,
            minute=20,
            id="morning_briefing_job",
            replace_existing=True
        )
    
    # Schedule hourly email alerts
    if not scheduler.get_job("hourly_email_alerts"):
        scheduler.add_job(
            func=send_hourly_alerts,
            trigger="interval",
            hours=1,
            id="hourly_email_alerts",
            replace_existing=True
        )
    
    # Schedule evening summary at 10:00 PM
    if not scheduler.get_job("evening_summary_job"):
        scheduler.add_job(
            func=send_evening_summary,
            trigger="cron",
            hour=22,
            minute=0,
            id="evening_summary_job",
            replace_existing=True
        )
    
    # Schedule cleanup at 11:59 PM
    if not scheduler.get_job("cleanup_tasks_job"):
        scheduler.add_job(
            func=cleanup_daily_tasks,
            trigger="cron",
            hour=23,
            minute=59,
            id="cleanup_tasks_job",
            replace_existing=True
        )
    
    # Schedule monthly report (Day 1 of each month at 09:00 AM)
    if not scheduler.get_job("monthly_report_job"):
        scheduler.add_job(
            func=send_monthly_report,
            trigger="cron",
            day=1,
            hour=9,
            minute=0,
            id="monthly_report_job",
            replace_existing=True
        )
    
    # Schedule weekly salary reset every Monday at 00:00
    if not scheduler.get_job("weekly_salary_reset_job"):
        scheduler.add_job(
            func=reset_weekly_salary,
            trigger="cron",
            day_of_week="mon",
            hour=0,
            minute=0,
            id="weekly_salary_reset_job",
            replace_existing=True
        )
    
    # Schedule weekly portfolio report every Sunday at 8:00 PM
    if not scheduler.get_job("weekly_portfolio_report_job"):
        scheduler.add_job(
            func=send_portfolio_weekly_report,
            trigger="cron",
            day_of_week="sun",
            hour=20,
            minute=0,
            id="weekly_portfolio_report_job",
            replace_existing=True
        )
    
    scheduler.start()
    print("Background scheduler started containing all alerts, briefings, and productivity jobs.")
