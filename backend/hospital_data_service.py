import csv
import os
import psycopg2
from psycopg2.extras import execute_values
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderQuotaExceeded, GeocoderServiceError
from fuzzywuzzy import fuzz
import time
from datetime import datetime
import json
from helpers.config import DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
from logger_setup import logger
import multiprocessing
from dateutil import parser
from geopy.distance import geodesic
import requests

def parse_date(date_string):
    try:
        return parser.parse(date_string).date()
    except ValueError:
        logger.warning(f"Invalid date format: {date_string}")
        return None

def process_hospital_chunk(chunk):
    processed_hospitals = []
    for hospital in chunk:
        try:
            processed_hospital = clean_hospital_data(hospital)
            processed_hospitals.append(processed_hospital)
        except Exception as e:
            logger.error(f"Error processing hospital {hospital.get('Facility ID')}: {str(e)}")
    return processed_hospitals

def clean_hospital_data(hospital):
    facility_id = hospital.get("Facility ID", "")
    facility_name = hospital.get("Facility Name", "")
    address = hospital.get("Address", "")
    city = hospital.get("City", "")
    state = hospital.get("State", "")
    zip_code = hospital.get("ZIP Code", "")
    
    logger.info(f"Processing {facility_id}: {facility_name}")

    last_updated = parse_date(hospital.get("Last Updated Date", ""))

    return {
        "facility_id": facility_id,
        "facility_name": facility_name,
        "address": address,
        "city": city,
        "state": state,
        "zip_code": zip_code,
        "county": hospital.get("County", ""),
        "phone_number": hospital.get("Phone Number", ""),
        "emergency_services": hospital.get("Emergency Services", False),
        "er_volume": hospital.get("ER Volume", ""),
        "wait_time": hospital.get("Wait Time", "360"),
        "has_live_wait_time": False,
        "latitude": hospital.get('latitude'),
        "longitude": hospital.get('longitude'),
        "last_updated": last_updated
    }

class HospitalDataService:
    def __init__(self):
        self.csv_path = os.path.join(os.path.dirname(__file__), 'data', 'Hospital_General_Information.csv')
        self.geolocator = None
        self.geocode_cache = {}
        self.load_geocode_cache()

    def get_coordinates(self, address):
        base_url = "https://maps.googleapis.com/maps/api/geocode/json"
        api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        
        params = {
            "address": address,
            "key": api_key
        }
        
        response = requests.get(base_url, params=params)
        data = response.json()
        
        if data["status"] == "OK":
            location = data["results"][0]["geometry"]["location"]
            return (location["lat"], location["lng"])
        else:
            logger.warning(f"Geocoding failed for address: {address}")
            return None


    def init_geolocator(self):
        self.geolocator = Nominatim(user_agent="hospital_matcher", timeout=10)

    def get_db_connection(self):
        return psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
        )

    def load_geocode_cache(self):
        try:
            with open('geocode_cache.json', 'r') as f:
                self.geocode_cache = json.load(f)
        except FileNotFoundError:
            self.geocode_cache = {}
            logger.warning("geocode_cache.json not found. Proceeding without pre-loaded cache.")

    def save_geocode_cache(self):
        with open('geocode_cache.json', 'w') as f:
            json.dump(self.geocode_cache, f)

    def geocode_addresses(self, hospitals):
        logger.info("Starting geocoding of addresses")
        self.init_geolocator()
        
        for hospital in hospitals:
            facility_name = hospital.get("Facility Name", "")
            address = hospital.get("Address", "")
            city = hospital.get("City", "")
            state = hospital.get("State", "")
            zip_code = hospital.get("ZIP Code", "")
            
            logger.info(f"Geocoding hospital: {facility_name}")

            key = f"{facility_name}, {city}, {state}"
            if key in self.geocode_cache:
                hospital['latitude'], hospital['longitude'] = self.geocode_cache[key]
                logger.info(f"Found cached coordinates for {key}: {self.geocode_cache[key]}")
                continue

            geocoding_attempts = [
                f"{address}, {city}, {state} {zip_code}",
                f"{facility_name}, {city}, {state}",
                f"{facility_name}, {city}",
                f"{facility_name}, {state}",
                facility_name,
                f"{city}, {state} {zip_code}"
            ]

            for attempt in geocoding_attempts:
                try:
                    logger.info(f"Attempting to geocode: {attempt}")
                    location = self.geolocator.geocode(attempt)
                    if location:
                        result = (location.latitude, location.longitude)
                        self.geocode_cache[key] = result
                        hospital['latitude'], hospital['longitude'] = result
                        logger.info(f"Geocoding successful for {attempt}: {result}")
                        break
                    time.sleep(1)
                except (GeocoderTimedOut, GeocoderServiceError) as e:
                    logger.warning(f"Geocoding error for {attempt}: {str(e)}")
                    time.sleep(2)
                except Exception as e:
                    logger.error(f"Unexpected error geocoding {attempt}: {str(e)}")

            if 'latitude' not in hospital or 'longitude' not in hospital:
                logger.error(f"Failed to geocode hospital: {facility_name}")
                hospital['latitude'], hospital['longitude'] = None, None

        logger.info("Geocoding of addresses completed")

    def get_all_hospitals(self):
        logger.info(f"Reading CSV file: {self.csv_path}")
        
        hospitals = {}
        total_rows = 0
        er_count = 0
        wait_time_count = 0
        
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as csvfile:
                csv_reader = csv.DictReader(csvfile)
                
                for row in csv_reader:
                    total_rows += 1
                    facility_id = row.get('Facility ID', '')
                    measure_id = row.get('Measure ID', '')
                    
                    if measure_id == 'EDV':
                        er_count += 1
                        if facility_id not in hospitals:
                            hospitals[facility_id] = {
                                'Facility ID': facility_id,
                                'Facility Name': row.get('Facility Name', ''),
                                'Address': row.get('Address', ''),
                                'City': row.get('City/Town', ''),
                                'State': row.get('State', ''),
                                'ZIP Code': row.get('ZIP Code', ''),
                                'County': row.get('County/Parish', ''),
                                'Phone Number': row.get('Telephone Number', ''),
                                'Emergency Services': True,
                                'ER Volume': row.get('Score', ''),
                                'Wait Time': '360',
                                'Last Updated Date': row.get('End Date', '')
                            }
                    elif measure_id == 'ED_2_Strata_1':
                        if facility_id in hospitals:
                            wait_time_count += 1
                            hospitals[facility_id]['Wait Time'] = row.get('Score', '360')

            logger.info(f"Total rows in CSV: {total_rows}")
            logger.info(f"Total Emergency Rooms found: {er_count}")
            logger.info(f"Total Wait Times found: {wait_time_count}")
            logger.info(f"Successfully processed {len(hospitals)} unique Emergency Room hospitals")
            return list(hospitals.values())
        
        except Exception as e:
            logger.error(f"Unexpected error when reading CSV: {str(e)}")
            raise

    def sync_cms_data(self, cursor, last_run_time):
        logger.info("Starting CMS data sync")
        
        try:
            raw_hospitals = self.get_all_hospitals()
            logger.info(f"Fetched {len(raw_hospitals)} hospitals from CMS")

            cursor.execute("SELECT facility_id, latitude, longitude FROM hospitals")
            existing_hospitals = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

            hospitals_to_process = [
                hospital for hospital in raw_hospitals
                if hospital.get("Facility ID") not in existing_hospitals or 
                self.is_hospital_new_or_updated(hospital, last_run_time)
            ]

            logger.info(f"Found {len(hospitals_to_process)} hospitals to process")

            # Geocode addresses before multiprocessing
            self.geocode_addresses(hospitals_to_process)

            # Use multiprocessing Pool for data cleaning
            with multiprocessing.Pool() as pool:
                chunk_size = 100
                hospital_chunks = [hospitals_to_process[i:i+chunk_size] for i in range(0, len(hospitals_to_process), chunk_size)]
                
                logger.info(f"Splitting {len(hospitals_to_process)} hospitals into {len(hospital_chunks)} chunks")
                for chunk_result in pool.imap_unordered(process_hospital_chunk, hospital_chunks):
                    logger.info(f"Processed chunk of {len(chunk_result)} hospitals")
                    logger.info("Pool Number: {}".format(multiprocessing.current_process().name))
                    if chunk_result:
                        logger.info(f"Updating database with chunk of {len(chunk_result)} hospitals")
                        self.bulk_upsert_hospitals(cursor, chunk_result)

            self.save_geocode_cache()

            logger.info("CMS data sync completed")
        
        except Exception as e:
            logger.error(f"Error in CMS data sync: {str(e)}")
            raise

    def is_hospital_new_or_updated(self, hospital, last_run_time):
        last_updated_str = hospital.get('Last Updated Date', '').strip()
        if not last_updated_str:
            return True
        try:
            hospital_update_date = parse_date(last_updated_str)
            return hospital_update_date > last_run_time.date()
        except ValueError:
            logger.warning(f"Invalid date format for hospital {hospital.get('Facility Name', 'Unknown')}: {last_updated_str}")
            return True

    def update_wait_times(self, cursor, hospital_identifier, wait_time, is_live=False):
        try:
            if isinstance(hospital_identifier, int):
                cursor.execute("""
                    UPDATE hospitals
                    SET wait_time = %s, 
                        has_wait_time_data = TRUE, 
                        has_live_wait_time = CASE WHEN %s THEN TRUE ELSE has_live_wait_time END,
                        last_updated = NOW()
                    WHERE id = %s
                """, (wait_time, is_live, hospital_identifier))
            else:
                cursor.execute("""
                    UPDATE hospitals h
                    SET wait_time = %s, 
                        has_wait_time_data = TRUE, 
                        has_live_wait_time = CASE WHEN %s THEN TRUE ELSE has_live_wait_time END,
                        last_updated = NOW()
                    FROM hospital_page_links hpl
                    JOIN hospital_pages hp ON hpl.hospital_page_id = hp.id
                    WHERE h.id = hpl.hospital_id AND hp.hospital_name = %s
                """, (wait_time, is_live, hospital_identifier))

            if cursor.rowcount > 0:
                logger.info(f"Updated wait time for {hospital_identifier}")
                return True
            else:
                logger.warning(f"No matching hospital found for {hospital_identifier}")
                return False

        except Exception as e:
            logger.error(f"Error updating wait time for {hospital_identifier}: {e}")
            raise

    

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

    
    def bulk_upsert_hospitals(self, cursor, hospitals):
        if not hospitals:
            logger.warning("No hospitals to upsert")
            return

        insert_query = """
        INSERT INTO hospitals (
            facility_id, facility_name, address, city, state, zip_code, county,
            phone_number, emergency_services, er_volume, wait_time, has_wait_time_data, has_live_wait_time, 
            latitude, longitude, last_updated
        ) VALUES %s
        ON CONFLICT (facility_id) DO UPDATE SET
            facility_name = EXCLUDED.facility_name,
            address = EXCLUDED.address,
            city = EXCLUDED.city,
            state = EXCLUDED.state,
            zip_code = EXCLUDED.zip_code,
            county = EXCLUDED.county,
            phone_number = EXCLUDED.phone_number,
            emergency_services = EXCLUDED.emergency_services,
            er_volume = EXCLUDED.er_volume,
            wait_time = EXCLUDED.wait_time,
            has_wait_time_data = CASE
                WHEN EXCLUDED.wait_time IS NOT NULL AND EXCLUDED.wait_time != 'N/A' THEN TRUE
                ELSE hospitals.has_wait_time_data
            END,
            has_live_wait_time = hospitals.has_live_wait_time,
            latitude = COALESCE(EXCLUDED.latitude, hospitals.latitude),
            longitude = COALESCE(EXCLUDED.longitude, hospitals.longitude),
            last_updated = EXCLUDED.last_updated
        """
        
        hospital_data = [
            (
                h['facility_id'], h['facility_name'], h['address'], h['city'],
                h['state'], h['zip_code'], h['county'], h['phone_number'],
                h['emergency_services'], h['er_volume'], h['wait_time'], 
                h['wait_time'] is not None and h['wait_time'] != 'N/A',  # has_wait_time_data
                False,  # has_live_wait_time (CMS data is not live)
                h['latitude'], h['longitude'], h['last_updated']
            )
            for h in hospitals
        ]

        try:
            execute_values(cursor, insert_query, hospital_data)
            logger.info(f"Upserted {len(hospital_data)} hospitals")
        except Exception as e:
            logger.error(f"Error during bulk upsert: {str(e)}")
            for h in hospital_data:
                try:
                    cursor.execute(insert_query, (h,))
                    logger.info(f"Inserted hospital {h[0]} individually")
                except Exception as individual_error:
                    logger.error(f"Error inserting hospital {h[0]}: {str(individual_error)}")
            cursor.connection.commit()

    def match_hospitals_from_screenshot(self, extracted_hospitals, database_hospitals, network_name):
        matched_pairs = []
        matched_db_hospitals = set()
        start_time = time.time()
        logger.info(f"Starting matching process for {len(extracted_hospitals)} extracted hospitals against {len(database_hospitals)} database hospitals")
        
        for i, extracted_hospital in enumerate(extracted_hospitals):
            best_match = None
            best_score = 0
            logger.info(f"Processing extracted hospital {i+1}/{len(extracted_hospitals)}: {extracted_hospital['hospital_name']}")
            
            extracted_name = extracted_hospital['hospital_name'].lower()
            extracted_address = extracted_hospital['address'].lower()
            
            # Get coordinates for extracted hospital
            extracted_coords = self.get_coordinates(f"{extracted_name}, {extracted_address}")
            
            for j, db_hospital in enumerate(database_hospitals):
                if db_hospital['id'] in matched_db_hospitals:
                    continue  # Skip already matched hospitals
                
                db_name = db_hospital['facility_name'].lower()
                db_address = f"{db_hospital['address']}, {db_hospital['city']}, {db_hospital['state']} {db_hospital['zip_code']}".lower()
                
                # Calculate various similarity scores
                name_score = fuzz.token_set_ratio(extracted_name, db_name)
                address_score = fuzz.token_set_ratio(extracted_address, db_address)
                network_score = fuzz.partial_ratio(network_name.lower(), db_name) * 0.1
                
                # Calculate geographic distance if coordinates are available
                distance_score = 0
                if db_hospital['latitude'] and db_hospital['longitude'] and extracted_coords:
                    try:
                        distance = geodesic(extracted_coords, (db_hospital['latitude'], db_hospital['longitude'])).miles
                        distance_score = max(0, 100 - distance)  # 100 points for 0 miles, decreasing as distance increases
                    except Exception as e:
                        logger.warning(f"Error calculating distance: {e}")
                
                # Calculate weighted total score
                total_score = (
                    (name_score * 0.4) +
                    (address_score * 0.3) +
                    (network_score * 0.1) +
                    (distance_score * 0.2)
                )
                
                if total_score > best_score:
                    best_score = total_score
                    best_match = db_hospital
            
            # Determine if the match is good enough
            if best_match and best_score >= 70:  # Increased threshold
                matched_pairs.append({
                    'extracted': extracted_hospital,
                    'matched': best_match,
                    'score': best_score
                })
                matched_db_hospitals.add(best_match['id'])
                logger.info(f"Matched {extracted_hospital['hospital_name']} to {best_match['facility_name']} with score {best_score}")
            else:
                logger.warning(f"No confident match found for {extracted_hospital['hospital_name']}. Best score: {best_score}")
        
        end_time = time.time()
        logger.info(f"Matching process completed in {end_time - start_time:.2f} seconds")
        return matched_pairs

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

    def get_all_database_hospitals(self, cursor):
        start_time = time.time()
        cursor.execute("""
            SELECT id, facility_id, facility_name, address, city, state, zip_code, latitude, longitude
            FROM hospitals
        """)
        results = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
        end_time = time.time()
        logger.info(f"Retrieved {len(results)} hospitals from database in {end_time - start_time:.2f} seconds")
        return results
    
    def get_hospitals_paginated(self, page=1, per_page=50, search_term=None, lat=0, lon=0, radius=0):
        offset = (page - 1) * per_page
        query = """
            SELECT id, facility_name, address, city, state, zip_code, latitude, longitude, 
                   wait_time, has_live_wait_time, has_wait_time_data
            FROM hospitals
            WHERE (%s IS NULL OR facility_name ILIKE %s OR address ILIKE %s)
            AND (
                %s = 0 OR %s = 0 OR %s = 0 OR
                (
                    6371 * acos(
                        cos(radians(%s)) * cos(radians(latitude)) *
                        cos(radians(longitude) - radians(%s)) +
                        sin(radians(%s)) * sin(radians(latitude))
                    )
                ) <= %s
            )
            ORDER BY facility_name
            LIMIT %s OFFSET %s
        """
        count_query = """
            SELECT COUNT(*) FROM hospitals
            WHERE (%s IS NULL OR facility_name ILIKE %s OR address ILIKE %s)
            AND (
                %s = 0 OR %s = 0 OR %s = 0 OR
                (
                    6371 * acos(
                        cos(radians(%s)) * cos(radians(latitude)) *
                        cos(radians(longitude) - radians(%s)) +
                        sin(radians(%s)) * sin(radians(latitude))
                    )
                ) <= %s
            )
        """
        search_pattern = f'%{search_term}%' if search_term else None
        
        params = (search_term, search_pattern, search_pattern, lat, lon, radius, lat, lon, lat, radius)
        count_params = params
        query_params = params + (per_page, offset)
        
        with self.get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(count_query, count_params)
                total_count = cursor.fetchone()[0]
                
                cursor.execute(query, query_params)
                hospitals = cursor.fetchall()
        
        result = {
            'hospitals': []
        }

        for hospital in hospitals:
            hospital_dict = dict(zip(['id', 'facility_name', 'address', 'city', 'state', 'zip_code', 'latitude', 'longitude', 'wait_time', 'has_live_wait_time', 'has_wait_time_data'], hospital))
            
            # Sanitize wait_time
            if hospital_dict['wait_time'] in ['Hospital address not found', 'N/A', None, '']:
                hospital_dict['wait_time'] = None
            else:
                try:
                    hospital_dict['wait_time'] = int(hospital_dict['wait_time'])
                except ValueError:
                    hospital_dict['wait_time'] = None

            result['hospitals'].append(hospital_dict)

        result.update({
            'total_count': total_count,
            'page': page,
            'per_page': per_page,
            'total_pages': (total_count + per_page - 1) // per_page
        })
        
        debug_info = {
            'query': query,
            'params': query_params
        }
        
        return result, debug_info

hospital_data_service = HospitalDataService()