import os
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Define the scopes required for modifying calendar events
SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    """
    Authenticates and returns the Google Calendar API service using a Service Account.
    Expects GOOGLE_APPLICATION_CREDENTIALS in the environment.
    """
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not credentials_path or not os.path.exists(credentials_path):
        print(f"Warning: Google credentials not found at {credentials_path}")
        return None

    try:
        creds = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=SCOPES
        )
        service = build('calendar', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"Error initializing Google Calendar service: {e}")
        return None

def get_todays_events():
    """
    Fetches events from the Google Calendar for the current day.
    """
    service = get_calendar_service()
    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
    
    if not service:
        return "No pude conectarme al calendario."

    try:
        # Get start and end of today in UTC format required by Google API
        now = datetime.datetime.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat() + 'Z'

        print(f"Fetching events from {start_of_day} to {end_of_day}")
        events_result = service.events().list(
            calendarId=calendar_id, 
            timeMin=start_of_day,
            timeMax=end_of_day,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])

        if not events:
            return "No tienes ningún evento programado para hoy."

        # Format events nicely
        response_lines = ["Estos son tus eventos de hoy:"]
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            summary = event.get('summary', 'Sin título')
            # Very basic string manipulation to make it readable, Claude will format it better
            response_lines.append(f"- {summary} ({start})")
            
        return "\n".join(response_lines)
    except Exception as e:
        print(f"Error fetching Google Calendar events: {e}")
        return "Ocurrió un error al consultar tu agenda de hoy."

def create_event(summary, start_time, end_time):
    """
    Creates a new event in the Google Calendar.
    start_time and end_time should be ISO 8601 strings (e.g. 2024-05-20T10:00:00-06:00).
    """
    service = get_calendar_service()
    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
    
    if not service:
        return "No pude conectarme al calendario para agendar el evento."

    event_body = {
        'summary': summary,
        'start': {
            'dateTime': start_time,
        },
        'end': {
            'dateTime': end_time,
        },
    }

    try:
        print(f"DEBUG: Attempting to create event '{summary}' from {start_time} to {end_time} in calendar '{calendar_id}'")
        event = service.events().insert(calendarId=calendar_id, body=event_body).execute()
        print(f"DEBUG: Success! Event created with link: {event.get('htmlLink')}")
        return f"¡Listo! Evento '{summary}' agendado exitosamente. Enlace: {event.get('htmlLink')}"
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR creating Google Calendar event:\n{error_details}")
        return f"Ocurrió un error al agendar el evento '{summary}'. Detalles: {str(e)}"

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    # Simple manual test locally if credentials exist
    print(get_todays_events())
