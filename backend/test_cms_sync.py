import psycopg2
import logging
from helpers.config import DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
from main import sync_cms_data
from cms_api_client import CMSAPIClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_cms_sync():
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cursor = conn.cursor()

        # Test CMS API directly
        cms_client = CMSAPIClient()
        hospitals = cms_client.get_all_hospitals()
        logger.info(f"Successfully processed {len(hospitals)} unique hospitals from CSV")
        
        if hospitals:
            logger.info(f"Sample hospital data: {hospitals[0]}")

        # If the above succeeds, try syncing
        sync_cms_data(cursor)

        # Check if data was inserted
        cursor.execute("SELECT COUNT(*) FROM hospitals")
        count = cursor.fetchone()[0]
        logger.info(f"Number of hospitals synced: {count}")

        # Check a few specific hospitals
        cursor.execute("SELECT facility_name, emergency_services, has_live_wait_time FROM hospitals LIMIT 5")
        sample_hospitals = cursor.fetchall()
        logger.info("Sample hospitals:")
        for hospital in sample_hospitals:
            logger.info(f"  {hospital[0]} - Emergency Services: {hospital[1]}, Has live wait time: {hospital[2]}")

    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    test_cms_sync()