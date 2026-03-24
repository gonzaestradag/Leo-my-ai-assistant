import os
import requests
from bs4 import BeautifulSoup
import psycopg2
from psycopg2.extras import RealDictCursor

BLACKBOARD_URL = "https://cursos-udem.blackboard.com"

def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"), cursor_factory=RealDictCursor)

def get_bb_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    })
    try:
        # Login a Blackboard
        login_url = f"{BLACKBOARD_URL}/webapps/login/"
        login_data = {
            'user_id': os.getenv('BB_USERNAME'),
            'password': os.getenv('BB_PASSWORD'),
            'action': 'login',
            'new_loc': '/webapps/portal/execute/tabs/tabAction?tab_tab_group_id=_1_1'
        }
        response = session.post(login_url, data=login_data, timeout=15)
        if 'logout' in response.text.lower() or session.cookies:
            return session
        return None
    except Exception as e:
        print(f"Error logging in to Blackboard: {e}")
        return None

def get_bb_assignments():
    session = get_bb_session()
    if not session:
        return "No pude conectarme a Blackboard. Verifica tus credenciales."
    try:
        # Obtener cursos
        response = session.get(f"{BLACKBOARD_URL}/webapps/portal/execute/tabs/tabAction?tab_tab_group_id=_1_1", timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        courses = []
        for link in soup.find_all('a', href=True):
            if '/webapps/blackboard/execute/launcher?type=Course' in link['href']:
                courses.append({
                    'name': link.text.strip(),
                    'url': BLACKBOARD_URL + link['href']
                })
        if not courses:
            return "No encontré cursos activos en Blackboard."
        assignments = []
        for course in courses[:5]:  # máximo 5 cursos para no hacer timeout
            try:
                course_response = session.get(course['url'], timeout=10)
                course_soup = BeautifulSoup(course_response.text, 'html.parser')
                # Buscar tareas
                for item in course_soup.find_all(['a', 'span'], class_=lambda x: x and 'assignment' in x.lower() if x else False):
                    assignments.append({
                        'course': course['name'],
                        'title': item.text.strip()
                    })
            except:
                continue
        if not assignments:
            return f"Tienes {len(courses)} cursos activos pero no encontré tareas pendientes visibles."
        lines = [f"📚 Tareas en Blackboard ({len(assignments)} encontradas):\n"]
        for a in assignments:
            lines.append(f"• {a['course']}: {a['title']}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error obteniendo tareas: {str(e)}"

def get_bb_grades():
    session = get_bb_session()
    if not session:
        return "No pude conectarme a Blackboard."
    try:
        grades_url = f"{BLACKBOARD_URL}/webapps/bb-mygrades-BBLEARN/myGrades?stream_name=mygrades&useStudentAccessible=true"
        response = session.get(grades_url, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        grades = []
        for row in soup.find_all('li', class_=lambda x: x and 'grade' in x.lower() if x else False):
            title = row.find('span', class_=lambda x: x and 'title' in x.lower() if x else False)
            grade = row.find('span', class_=lambda x: x and 'grade' in x.lower() if x else False)
            if title:
                grades.append({
                    'title': title.text.strip(),
                    'grade': grade.text.strip() if grade else 'Sin calificar'
                })
        if not grades:
            return "No encontré calificaciones disponibles en este momento."
        lines = ["📊 Tus calificaciones:\n"]
        for g in grades:
            lines.append(f"• {g['title']}: {g['grade']}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error obteniendo calificaciones: {str(e)}"
