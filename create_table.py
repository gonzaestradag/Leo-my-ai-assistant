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
