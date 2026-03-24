import os
import requests
import psycopg2
from psycopg2.extras import RealDictCursor

BLACKBOARD_URL = "https://cursos-udem.blackboard.com"

def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"), cursor_factory=RealDictCursor)

def get_bb_token():
    try:
        token_url = f"{BLACKBOARD_URL}/learn/api/public/v1/oauth2/token"
        response = requests.post(
            token_url,
            data={
                'grant_type': 'password',
                'username': os.getenv('BB_USERNAME'),
                'password': os.getenv('BB_PASSWORD')
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=15
        )
        if response.status_code == 200:
            return response.json().get('access_token')
        # Si falla OAuth, intentar con session cookie
        return None
    except Exception as e:
        print(f"Error getting BB token: {e}")
        return None

def get_bb_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'es-MX,es;q=0.9',
    })
    try:
        # Login para Blackboard Ultra
        login_url = f"{BLACKBOARD_URL}/webapps/login/"
        login_data = {
            'user_id': os.getenv('BB_USERNAME'),
            'password': os.getenv('BB_PASSWORD'),
            'action': 'login',
            'new_loc': '/ultra/institution-page'
        }
        response = session.post(login_url, data=login_data, timeout=15, allow_redirects=True)
        print(f"Login status: {response.status_code}")
        print(f"Cookies: {dict(session.cookies)}")
        return session
    except Exception as e:
        print(f"Error logging in: {e}")
        return None

def get_bb_assignments():
    try:
        # Intentar con REST API primero
        token = get_bb_token()
        if token:
            headers = {'Authorization': f'Bearer {token}'}
            # Obtener cursos via API
            courses_resp = requests.get(
                f"{BLACKBOARD_URL}/learn/api/public/v1/users/me/courses?limit=10",
                headers=headers, timeout=15
            )
            if courses_resp.status_code == 200:
                courses = courses_resp.json().get('results', [])
                assignments = []
                for course in courses:
                    course_id = course.get('courseId', '')
                    # Obtener contenido del curso
                    content_resp = requests.get(
                        f"{BLACKBOARD_URL}/learn/api/public/v1/courses/{course_id}/gradebook/columns?limit=10",
                        headers=headers, timeout=10
                    )
                    if content_resp.status_code == 200:
                        items = content_resp.json().get('results', [])
                        for item in items:
                            if not item.get('score', {}).get('given'):
                                assignments.append({
                                    'course': course.get('course', {}).get('name', 'Curso'),
                                    'title': item.get('name', 'Tarea'),
                                    'due': item.get('dueDate', 'Sin fecha')
                                })
                if assignments:
                    lines = [f"📚 Tareas pendientes en Blackboard:\n"]
                    for a in assignments:
                        lines.append(f"• {a['course']}")
                        lines.append(f"  📝 {a['title']}")
                        if a['due'] != 'Sin fecha':
                            lines.append(f"  📅 Entrega: {a['due'][:10]}")
                    return "\n".join(lines)
                return "No tienes tareas pendientes en Blackboard ✅"
        
        # Fallback: session scraping
        session = get_bb_session()
        if not session:
            return "No pude conectarme a Blackboard. Verifica tus credenciales en Render."
        
        # Intentar API con session cookies
        api_resp = session.get(
            f"{BLACKBOARD_URL}/learn/api/public/v1/users/me/courses?limit=10",
            timeout=15
        )
        print(f"API response: {api_resp.status_code} - {api_resp.text[:200]}")
        
        if api_resp.status_code == 200:
            courses = api_resp.json().get('results', [])
            if not courses:
                return "No encontré cursos activos en Blackboard."
            return f"Encontré {len(courses)} cursos activos. Obteniendo tareas..."
        
        return f"Blackboard respondió con código {api_resp.status_code}. Puede ser que la sesión no se autenticó correctamente."
        
    except Exception as e:
        return f"Error conectando a Blackboard: {str(e)}"

def get_bb_grades():
    try:
        token = get_bb_token()
        headers = {'Authorization': f'Bearer {token}'} if token else {}
        
        session = get_bb_session() if not token else None
        
        requester = requests if token else session
        req_headers = headers if token else {}
        
        courses_resp = requester.get(
            f"{BLACKBOARD_URL}/learn/api/public/v1/users/me/courses?limit=10",
            headers=req_headers, timeout=15
        )
        
        if courses_resp.status_code != 200:
            return f"No pude obtener tus cursos (error {courses_resp.status_code})"
        
        courses = courses_resp.json().get('results', [])
        lines = ["📊 Tus calificaciones:\n"]
        
        for course in courses:
            course_id = course.get('courseId', '')
            course_name = course.get('course', {}).get('name', 'Curso')
            
            grades_resp = requester.get(
                f"{BLACKBOARD_URL}/learn/api/public/v1/courses/{course_id}/gradebook/users/me",
                headers=req_headers, timeout=10
            )
            
            if grades_resp.status_code == 200:
                grades = grades_resp.json().get('results', [])
                if grades:
                    lines.append(f"📚 {course_name}:")
                    for g in grades[:3]:
                        score = g.get('score', {})
                        given = score.get('given', 'N/A')
                        possible = score.get('possible', 100)
                        lines.append(f"  • {g.get('columnName', 'Tarea')}: {given}/{possible}")
        
        return "\n".join(lines) if len(lines) > 1 else "No hay calificaciones disponibles aún."
        
    except Exception as e:
        return f"Error obteniendo calificaciones: {str(e)}"
