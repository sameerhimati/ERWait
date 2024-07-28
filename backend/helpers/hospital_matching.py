import psycopg2
from fuzzywuzzy import fuzz
from geopy.distance import great_circle
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from helpers.config import OPENAI_API_KEY, DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
import time
import logging
# Set up logging
from logger_setup import logger

def get_hospital_location(hospital_name):
    geolocator = Nominatim(user_agent="hospital_matcher")
    max_retries = 3
    for attempt in range(max_retries):
        try:
            location = geolocator.geocode(f"{hospital_name} hospital")
            if location:
                return (location.latitude, location.longitude)
        except (GeocoderTimedOut, GeocoderServiceError):
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            else:
                logger.warning(f"Failed to geocode {hospital_name} after {max_retries} attempts")
    return None

def match_hospitals(cursor):
    # Fetch all hospitals from the CMS dataset
    cursor.execute("""
        SELECT id, facility_name, latitude, longitude
        FROM hospitals
    """)
    cms_hospitals = cursor.fetchall()

    # Fetch all hospitals from the hospital_pages table
    cursor.execute("""
        SELECT id, hospital_name
        FROM hospital_pages
    """)
    wait_time_hospitals = cursor.fetchall()

    for wt_hospital in wait_time_hospitals:
        best_match = None
        best_score = 0
        for cms_hospital in cms_hospitals:
            # Calculate name similarity
            name_similarity = fuzz.ratio(wt_hospital[1].lower(), cms_hospital[1].lower())

            # If name similarity is above a threshold, consider it a potential match
            if name_similarity > 80:
                # Calculate geographic distance (if lat/long are available)
                distance = float('inf')
                if cms_hospital[2] and cms_hospital[3]:
                    wt_location = get_hospital_location(wt_hospital[1])
                    if wt_location:
                        distance = great_circle(
                            (wt_location[0], wt_location[1]),
                            (cms_hospital[2], cms_hospital[3])
                        ).miles

                # Combine name similarity and distance for an overall score
                # You may want to adjust the weights based on your preferences
                score = name_similarity * 0.7 + (100 - min(distance, 100)) * 0.3

                if score > best_score:
                    best_score = score
                    best_match = cms_hospital

        if best_match and best_score > 85:  # You can adjust this threshold
            logger.info(f"Matched {wt_hospital[1]} to {best_match[1]} with score {best_score}")
            # Insert into hospital_page_links table
            cursor.execute("""
                INSERT INTO hospital_page_links (hospital_id, hospital_page_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (best_match[0], wt_hospital[0]))
        else:
            logger.warning(f"No suitable match found for {wt_hospital[1]}")

    cursor.connection.commit()

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Database connection (replace with your actual connection details)
    conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
    )
    cursor = conn.cursor()

    try:
        match_hospitals(cursor)
    finally:
        cursor.close()
        conn.close()