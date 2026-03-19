import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
database_url = os.getenv("DATABASE_URL")

table_query = """
CREATE TABLE IF NOT EXISTS contacts (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(20),
    name VARCHAR(100),
    email VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_alerts (
    id SERIAL PRIMARY KEY,
    gmail_id VARCHAR(100) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(20),
    task TEXT,
    task_date DATE DEFAULT CURRENT_DATE,
    completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_stats (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(20),
    stat_date DATE,
    total_tasks INTEGER,
    completed_tasks INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

if database_url:
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        cur.execute(table_query)
        conn.commit()
        cur.close()
        conn.close()
        print("Table 'contacts' created successfully in database.")
    except Exception as e:
        print(f"Error creating table: {e}")
else:
    print("No DATABASE_URL found in .env.")
