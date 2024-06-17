import psycopg2
from config import DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT

def fetch_hospital_data():
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    cursor = conn.cursor()
    cursor.execute("SELECT url, hospital_name, hospital_address FROM hospital_pages")
    rows = cursor.fetchall()
    conn.close()
    return rows
