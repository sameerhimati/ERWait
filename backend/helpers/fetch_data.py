import psycopg2
from helpers.config import DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
from logger_setup import logger

def fetch_hospital_data():
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute("SELECT url, network_name, hospital_num FROM hospital_pages")
        rows = cursor.fetchall()
        conn.close()
        logger.info("Fetched hospital network data successfully")
        return rows
    except Exception as e:
        logger.error("Error fetching hospital network data: %s", e)
        raise