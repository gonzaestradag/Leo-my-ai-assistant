import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Define the scopes required for reading and sending Gmail
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send'
]

def get_token_path():
    render_path = '/etc/secrets/token.json'
    local_path = 'token.json'
    if os.path.exists(render_path):
        return render_path
    return local_path

def get_gmail_service():
    """
    Authenticates and returns the Gmail API service using OAuth 2.0.
    Expects 'credentials.json' (Client ID file) in the project root.
    Will create 'token.json' after first manual login.
    """
    creds = None
    # 'token.json' stores the user's access and refresh tokens.
    if os.path.exists(get_token_path()):
        try:
            creds = Credentials.from_authorized_user_file(get_token_path(), SCOPES)
        except Exception as e:
            print(f"Error loading token.json: {e}")

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        try:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists('credentials.json'):
                    print("Error: 'credentials.json' NO encontrado. Descarga tu OAuth Client ID desde Google Cloud.")
                    return None
                    
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                # Open browser for authentication
                creds = flow.run_local_server(port=0)
                
            # Save the credentials for the next run
            with open(get_token_path(), 'w') as token:
                token.write(creds.to_json())
            print("Successfully authenticated and saved token.json")
        except Exception as e:
            print(f"Autenticación OAuth fallida: {e}")
            return None

    try:
        service = build('gmail', 'v1', credentials=creds)
        return service
    except Exception as e:
        print(f"Error inicializando Gmail service: {e}")
        return None

def get_recent_unread_emails():
    """
    Fetches the 5 most recent unread emails.
    """
    service = get_gmail_service()
    user_id = "me"
    
    if not service:
        return "No pude conectarme a Gmail. Faltan credenciales o token de autenticación."

    try:
        print(f"DEBUG: Fetching unread emails for '{user_id}' via OAuth")
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
        print(f"ERROR fetching Gmail unread emails via OAuth:\n{error_details}")
        return f"Ocurrió un error al consultar tus correos. Detalles: {str(e)}"

def get_urgent_emails():
    """
    Fetches the 5 most recent important or starred emails.
    """
    service = get_gmail_service()
    user_id = "me"
    
    if not service:
        return "No pude conectarme a Gmail para leer tus correos importantes."

    try:
        print(f"DEBUG: Fetching urgent/important emails for '{user_id}' via OAuth")
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
        print(f"ERROR fetching Gmail urgent emails via OAuth:\n{error_details}")
        return f"Ocurrió un error al consultar tus correos urgentes. Detalles: {str(e)}"

def send_email(to, subject, body):
    service = get_gmail_service()
    if not service:
        return "No pude conectarme a Gmail para enviar el correo."
    try:
        import base64
        from email.mime.text import MIMEText
        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(userId='me', body={'raw': raw}).execute()
        return f"✅ Email enviado a {to} con asunto '{subject}'"
    except Exception as e:
        return f"Error enviando email: {str(e)}"

if __name__ == '__main__':
    # Running directly will prompt the OAuth flow if token.json is missing
    print(get_recent_unread_emails())
