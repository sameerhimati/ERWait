import csv
import os
import psycopg2
from psycopg2.extras import execute_values
from geopy.distance import great_circle
from geopy.geocoders import Nominatim
from itertools import islice
from geopy.exc import GeocoderTimedOut, GeocoderQuotaExceeded
from fuzzywuzzy import fuzz
import time
from datetime import datetime
import redis
import json
from helpers.config import DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
from logger_setup import logger
from geopy.distance import great_circle
from concurrent.futures import ThreadPoolExecutor, as_completed
from logger_setup import logger
import uszipcode

class HospitalDataService:
    def __init__(self):
        self.csv_path = os.path.join(os.path.dirname(__file__), 'data', 'Hospital_General_Information.csv')
        self.geolocator = Nominatim(user_agent="hospital_matcher", timeout=10)
        self.geocode_cache_file = 'geocode_cache.json'
        self.progress_file = 'geocoding_progress.json'
        self.load_geocode_cache()
        self.search = uszipcode.SearchEngine()

    def load_geocode_cache(self):
        if os.path.exists(self.geocode_cache_file):
            with open(self.geocode_cache_file, 'r') as f:
                self.geocode_cache = json.load(f)
        else:
            self.geocode_cache = {}

    def save_geocode_cache(self):
        with open(self.geocode_cache_file, 'w') as f:
            json.dump(self.geocode_cache, f)

    def load_progress(self):
        if os.path.exists(self.progress_file):
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {'last_processed_index': 0}

    def save_progress(self, index):
        with open(self.progress_file, 'w') as f:
            json.dump({'last_processed_index': index}, f)

    def geocode_address(self, hospital):
        address_parts = [
            hospital['address'].strip(),
            hospital['city'].strip() if hospital['city'] and hospital['city'].lower() != 'none' else '',
            hospital['state'].strip(),
            hospital['zip_code'].strip()
        ]
        address = ', '.join(filter(None, address_parts))
        cache_key = address.lower().replace(' ', '')
        
        if cache_key in self.geocode_cache:
            return self.geocode_cache[cache_key]

        logger.info(f"Geocoding address for {hospital['facility_name']}: {address}")
        
        result = self._geocode_with_retry(address)
        
        if result is None:
            fallback_attempts = [
                f"{hospital['facility_name']}, {hospital['state']}",
                f"{hospital['facility_name']}, {hospital['city']}, {hospital['state']}",
                hospital['zip_code']
            ]
            for attempt in fallback_attempts:
                result = self._geocode_with_retry(attempt)
                if result:
                    logger.info(f"Fallback geocoding successful for {hospital['facility_name']} using {attempt}")
                    break
        
        if result is None:
            # Use zip code centroid as last resort
            zip_info = self.search.by_zipcode(hospital['zip_code'])
            if zip_info:
                result = (zip_info.lat, zip_info.lng)
                logger.info(f"Using zip code centroid for {hospital['facility_name']}")
        
        if result:
            self.geocode_cache[cache_key] = result
            self.save_geocode_cache()
        
        return result

    def _geocode_with_retry(self, query):
        max_retries = 5
        for attempt in range(max_retries):
            try:
                time.sleep(2 ** attempt)  # Exponential backoff
                location = self.geolocator.geocode(query)
                if location:
                    return (location.latitude, location.longitude)
            except GeocoderTimedOut:
                logger.warning(f"Geocoding attempt {attempt + 1} timed out for {query}")
            except GeocoderQuotaExceeded:
                logger.warning(f"Geocoding quota exceeded. Waiting before retry.")
                time.sleep(60)  # Wait 60 seconds before retry
            except Exception as e:
                logger.error(f"Unexpected error during geocoding: {str(e)}")
        
        logger.error(f"Geocoding failed for {query} after {max_retries} attempts")
        return None

    def process_hospitals(self, hospitals, last_run_time):
        logger.info(f"Processing {len(hospitals)} hospitals")
        processed_hospitals = []
        progress = self.load_progress()
        start_index = progress['last_processed_index']
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_hospital = {executor.submit(self.process_hospital, hospital): (i, hospital) 
                                  for i, hospital in enumerate(hospitals[start_index:], start=start_index)}
            for future in as_completed(future_to_hospital):
                i, hospital = future_to_hospital[future]
                try:
                    processed_hospital = future.result()
                    processed_hospitals.append(processed_hospital)
                except Exception as exc:
                    logger.error(f'{hospital["facility_name"]} generated an exception: {exc}')
                
                if len(processed_hospitals) % 50 == 0:
                    logger.info(f"Processed {len(processed_hospitals)} out of {len(hospitals) - start_index} hospitals")
                    self.save_progress(i)
        
        logger.info(f"Processed {len(processed_hospitals)} hospitals")
        return processed_hospitals

    def process_hospital(self, hospital):
        processed_hospital = self.clean_hospital_data(hospital)
        
        coordinates = self.geocode_address(processed_hospital)
        if coordinates:
            processed_hospital['latitude'], processed_hospital['longitude'] = coordinates
        else:
            processed_hospital['latitude'], processed_hospital['longitude'] = None, None
        
        return processed_hospital
    
    def bulk_upsert_hospitals(self, cursor, hospitals):
        insert_query = """
        INSERT INTO hospitals (
            facility_id, facility_name, address, city, state, zip_code, county,
            phone_number, hospital_type, emergency_services, has_live_wait_time, latitude, longitude, last_updated
        ) VALUES %s
        ON CONFLICT (facility_id) DO UPDATE SET
            facility_name = EXCLUDED.facility_name,
            address = EXCLUDED.address,
            city = EXCLUDED.city,
            state = EXCLUDED.state,
            zip_code = EXCLUDED.zip_code,
            county = EXCLUDED.county,
            phone_number = EXCLUDED.phone_number,
            hospital_type = EXCLUDED.hospital_type,
            emergency_services = EXCLUDED.emergency_services,
            has_live_wait_time = EXCLUDED.has_live_wait_time,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            last_updated = EXCLUDED.last_updated
        """
        hospital_data = [
            (
                h['facility_id'], h['facility_name'], h['address'], h['city'],
                h['state'], h['zip_code'], h['county'], h['phone_number'],
                h['hospital_type'], h['emergency_services'], h['has_live_wait_time'],
                h['latitude'], h['longitude'], h['last_updated']
            )
            for h in hospitals
        ]
        execute_values(cursor, insert_query, hospital_data)
        logger.info(f"Upserted {len(hospitals)} hospitals")

    def get_db_connection(self):
        return psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
        )
    
    def get_hospitals_paginated(self, page=1, per_page=50, search_term=None):
        offset = (page - 1) * per_page
        query = """
            SELECT id, facility_name, address, city, state, zip_code, latitude, longitude, has_live_wait_time
            FROM hospitals
            WHERE (%s IS NULL OR facility_name ILIKE %s OR address ILIKE %s)
            ORDER BY facility_name
            LIMIT %s OFFSET %s
        """
        count_query = """
            SELECT COUNT(*) FROM hospitals
            WHERE (%s IS NULL OR facility_name ILIKE %s OR address ILIKE %s)
        """
        search_pattern = f'%{search_term}%' if search_term else None
        
        with self.get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(count_query, (search_term, search_pattern, search_pattern))
                total_count = cursor.fetchone()[0]
                
                cursor.execute(query, (search_term, search_pattern, search_pattern, per_page, offset))
                hospitals = cursor.fetchall()
        
        return {
            'hospitals': hospitals,
            'total_count': total_count,
            'page': page,
            'per_page': per_page,
            'total_pages': (total_count + per_page - 1) // per_page
        }
    
    def populate_hospital_pages(self, cursor, hospital_pages_data):
        for name, url, num in hospital_pages_data:
            cursor.execute("""
                INSERT INTO hospital_pages (hospital_name, url, hospital_num)
                VALUES (%s, %s, %s)
                ON CONFLICT (hospital_name) DO UPDATE SET
                    url = EXCLUDED.url,
                    hospital_num = EXCLUDED.hospital_num
            """, (name, url, num))
        logger.info(f"Populated {len(hospital_pages_data)} hospital pages")

    def get_all_hospitals(self):
        logger.info(f"Reading CSV file: {self.csv_path}")
        
        hospitals = {}
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as csvfile:
                csv_reader = csv.DictReader(csvfile)
                
                # Print column names for debugging
                logger.debug(f"CSV columns: {csv_reader.fieldnames}")
                
                for row in csv_reader:
                    facility_id = row.get('Facility ID')
                    if not facility_id:
                        logger.warning("Row missing Facility ID, skipping")
                        continue
                    
                    if facility_id not in hospitals:
                        hospitals[facility_id] = {
                            'Facility ID': facility_id,
                            'Facility Name': row.get('Facility Name', ''),
                            'Address': row.get('Address', ''),
                            'City': row.get('City/Town', ''),  # Note the change here
                            'State': row.get('State', ''),
                            'ZIP Code': row.get('ZIP Code', ''),
                            'County Name': row.get('County Name', ''),  # This might be the problematic field
                            'Phone Number': row.get('Phone Number', ''),
                            'Hospital Type': row.get('Hospital Type', ''),
                            'Emergency Services': row.get('Emergency Services', 'No') == 'Yes',
                            'Last Updated Date': row.get('Last Updated Date', '')
                        }
                    
                    # Check for emergency services in a separate column if it exists
                    if 'Emergency Services' in row:
                        hospitals[facility_id]['Emergency Services'] = row['Emergency Services'] == 'Yes'

            logger.info(f"Successfully processed {len(hospitals)} unique hospitals")
            return list(hospitals.values())
        
        except KeyError as e:
            logger.error(f"KeyError when reading CSV: {str(e)}. This column is missing from the CSV.")
            raise
        except Exception as e:
            logger.error(f"Unexpected error when reading CSV: {str(e)}")
            raise


    def get_hospital_from_db(self, facility_id):
        with self.get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM hospitals WHERE facility_id = %s
                """, (facility_id,))
                result = cursor.fetchone()
                if result:
                    return dict(zip([column[0] for column in cursor.description], result))
        return None

    def clean_hospital_data(self, hospital):
        return {
            "facility_id": hospital.get("Facility ID", ""),
            "facility_name": hospital.get("Facility Name", ""),
            "address": hospital.get("Address", ""),
            "city": hospital.get("City/Town", ""),
            "state": hospital.get("State", ""),
            "zip_code": hospital.get("ZIP Code", ""),
            "county": hospital.get("County Name", ""),
            "phone_number": hospital.get("Phone Number", ""),
            "hospital_type": hospital.get("Hospital Type", ""),
            "emergency_services": hospital.get("Emergency Services", "No") == "Yes",
            "has_live_wait_time": False,
            "latitude": None,
            "longitude": None,
            "last_updated": hospital.get("Last Updated Date", "")
        }

    def match_hospitals(self, cursor):
        cursor.execute("""
            CREATE EXTENSION IF NOT EXISTS pg_trgm;
            CREATE INDEX IF NOT EXISTS idx_hospital_name_trgm ON hospitals USING gin (facility_name gin_trgm_ops);
            CREATE INDEX IF NOT EXISTS idx_hospital_pages_name_trgm ON hospital_pages USING gin (hospital_name gin_trgm_ops);
        """)

        cursor.execute("""
            SELECT hp.id, hp.hospital_name, h.id, h.facility_name, h.latitude, h.longitude,
                   similarity(hp.hospital_name, h.facility_name) as name_similarity
            FROM hospital_pages hp
            CROSS JOIN LATERAL (
                SELECT id, facility_name, latitude, longitude
                FROM hospitals
                ORDER BY hp.hospital_name <-> facility_name
                LIMIT 5
            ) h
            WHERE similarity(hp.hospital_name, h.facility_name) > 0.3
            ORDER BY hp.id, name_similarity DESC
        """)
        potential_matches = cursor.fetchall()

        for match in potential_matches:
            hp_id, hp_name, h_id, h_name, h_lat, h_lon, name_similarity = match
            
            distance = float('inf')
            if h_lat and h_lon:
                wt_location = self.get_hospital_location(hp_name)
                if wt_location:
                    distance = great_circle((wt_location[0], wt_location[1]), (h_lat, h_lon)).miles

            score = name_similarity * 0.7 + (100 - min(distance, 100)) * 0.3

            if score > 85:
                logger.info(f"Matched {hp_name} to {h_name} with score {score}")
                cursor.execute("""
                    INSERT INTO hospital_page_links (hospital_id, hospital_page_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                """, (h_id, hp_id))
            else:
                logger.warning(f"No suitable match found for {hp_name}")

    def get_hospital_location(self, hospital_name):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                location = self.geolocator.geocode(f"{hospital_name} hospital")
                if location:
                    return (location.latitude, location.longitude)
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                else:
                    logger.warning(f"Failed to geocode {hospital_name} after {max_retries} attempts")
        return None

    def sync_cms_data(self, cursor, last_run_time):
        logger.info("Starting CMS data sync")
        
        try:
            raw_hospitals = self.get_all_hospitals()
            logger.info(f"Fetched {len(raw_hospitals)} hospitals from CMS")

            # Check if this is the initial run
            cursor.execute("SELECT COUNT(*) FROM hospitals")
            is_initial_run = cursor.fetchone()[0] == 0

            if is_initial_run:
                logger.info("Initial run detected. Processing all hospitals.")
                hospitals_to_process = raw_hospitals
            else:
                hospitals_to_process = [
                    hospital for hospital in raw_hospitals
                    if self.is_hospital_new_or_updated(hospital, last_run_time)
                ]
                logger.info(f"Found {len(hospitals_to_process)} new or updated hospitals")

            processed_hospitals = self.process_hospitals(hospitals_to_process, last_run_time)

            if processed_hospitals:
                logger.info("Updating database with processed hospital data")
                self.bulk_upsert_hospitals(cursor, processed_hospitals)
            else:
                logger.info("No hospitals to process")

            logger.info("CMS data sync completed")
        
        except Exception as e:
            logger.error(f"Error in CMS data sync: {str(e)}")
            raise

    def is_hospital_new_or_updated(self, hospital, last_run_time):
        hospital_update_date = datetime.strptime(hospital['Last Updated Date'], '%Y-%m-%d').date()
        return hospital_update_date > last_run_time.date()

    def fetch_hospital_network_data(self):
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT url, hospital_name, hospital_num FROM hospital_pages")
                    rows = cursor.fetchall()
            logger.info("Fetched hospital network data successfully")
            return rows
        except Exception as e:
            logger.error("Error fetching hospital network data: %s", e)
            raise

hospital_data_service = HospitalDataService()