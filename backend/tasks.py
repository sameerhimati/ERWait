from hospital_data_service import hospital_data_service
from contextlib import contextmanager
import psycopg2
from helpers.config import DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
from logger_setup import logger

@contextmanager
def get_db_cursor():
    conn = psycopg2.connect(
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
    )
    try:
        yield conn.cursor()
        conn.commit()
    finally:
        conn.close()

def sync_cms_data_task(last_run_time):
    logger.info("Starting CMS data sync task")
    try:
        service = hospital_data_service
        with get_db_cursor() as cursor:
            service.sync_cms_data(cursor, last_run_time)
        logger.info("CMS data sync task completed successfully")
    except Exception as e:
        logger.error(f"Error in CMS data sync task: {str(e)}")
        raise