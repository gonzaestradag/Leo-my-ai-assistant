import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Define the scopes required for reading Gmail
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    """
    Authenticates and returns the Gmail API service using a Service Account.
    Note: Reading personal Gmail via Service Account requires Domain-Wide Delegation in Google Workspace.
    """
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not credentials_path or not os.path.exists(credentials_path):
        print(f"Warning: Google credentials not found at {credentials_path}")
        return None

    try:
        creds = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=SCOPES
        )
        
        user_email = os.getenv("GOOGLE_CALENDAR_ID")
        # To access a user's Gmail with a service account, we generally need to impersonate them
        # This requires Google Workspace and domain-wide delegation enabled.
        if user_email:
            try:
                delegated_creds = creds.with_subject(user_email)
                service = build('gmail', 'v1', credentials=delegated_creds)
                return service
            except Exception as e:
                print(f"Could not impersonate {user_email}, falling back to default creds. Error: {e}")
                
        service = build('gmail', 'v1', credentials=creds)
        return service
    except Exception as e:
        print(f"Error initializing Gmail service: {e}")
        return None

def get_recent_unread_emails():
    """
    Fetches the 5 most recent unread emails.
    """
    service = get_gmail_service()
    user_id = os.getenv("GOOGLE_CALENDAR_ID", "me")
    
    if not service:
        return "No pude conectarme a Gmail para leer tus correos."

    try:
        print(f"DEBUG: Fetching unread emails for user '{user_id}'")
        results = service.users().messages().list(
            userId=user_id, 
            labelIds=['UNREAD'], 
            maxResults=5
        ).execute()
        
        messages = results.get('messages', [])

        if not messages:
            return "No tienes correos nuevos sin leer."

        email_list = ["Estos son tus 5 correos sin leer más recientes:"]
        for msg in messages:
            msg_data = service.users().messages().get(
                userId=user_id, id=msg['id'], format='metadata', metadataHeaders=['From', 'Subject']
            ).execute()
            
            headers = msg_data.get('payload', {}).get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'Sin Asunto')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Desconocido')
            
            email_list.append(f"- De: {sender}\n  Asunto: {subject}")
            
        return "\n".join(email_list)
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR fetching Gmail unread emails:\n{error_details}")
        
        # This error commonly occurs if Domain-Wide Delegation is not set up
        if "Precondition check failed" in str(e) or "Client is unauthorized to retrieve access tokens" in str(e):
            return "Ocurrió un error de permisos. Recuerda que para leer tu Gmail con una Service Account, necesitas Google Workspace y habilitar 'Domain-Wide Delegation'."
            
        return f"Ocurrió un error al consultar tus correos. Detalles: {str(e)}"

def get_urgent_emails():
    """
    Fetches the 5 most recent important or starred emails.
    """
    service = get_gmail_service()
    user_id = os.getenv("GOOGLE_CALENDAR_ID", "me")
    
    if not service:
        return "No pude conectarme a Gmail para leer tus correos importantes."

    try:
        print(f"DEBUG: Fetching urgent/important emails for user '{user_id}'")
        # q parameter allows us to use Gmail search operators
        results = service.users().messages().list(
            userId=user_id, 
            q="is:important OR is:starred", 
            maxResults=5
        ).execute()
        
        messages = results.get('messages', [])

        if not messages:
            return "No tienes correos marcados como importantes o destacados."

        email_list = ["Estos son tus correos importantes/destacados más recientes:"]
        for msg in messages:
            msg_data = service.users().messages().get(
                userId=user_id, id=msg['id'], format='metadata', metadataHeaders=['From', 'Subject']
            ).execute()
            
            headers = msg_data.get('payload', {}).get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'Sin Asunto')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Desconocido')
            
            email_list.append(f"- De: {sender}\n  Asunto: {subject}")
            
        return "\n".join(email_list)
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR fetching Gmail urgent emails:\n{error_details}")
        return f"Ocurrió un error al consultar tus correos urgentes. Detalles: {str(e)}"

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    print(get_recent_unread_emails())
