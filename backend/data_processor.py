import json
import os
from typing import List, Dict, Any
import requests
import time
from requests.exceptions import RequestException
from datetime import datetime, timezone

# Set up logging
from logger_setup import logger

# Define a constant for the minimum date
MIN_DATE = datetime(1970, 1, 1, tzinfo=timezone.utc)

class GeocodingService:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://maps.googleapis.com/maps/api/geocode/json"
        self.logger = logger

    def geocode(self, address, max_retries=3, initial_delay=1):
        self.logger.info(f"Geocoding address: {address}")
        params = {
            "address": address,
            "key": self.api_key
        }
        
        for attempt in range(max_retries):
            try:
                self.logger.debug(f"Geocoding attempt {attempt + 1} for address: {address}")
                response = requests.get(self.base_url, params=params, timeout=5)
                response.raise_for_status()
                
                data = response.json()
                
                if data["status"] == "OK":
                    location = data["results"][0]["geometry"]["location"]
                    self.logger.info(f"Successfully geocoded address: {address}")
                    return location["lat"], location["lng"]
                elif data["status"] == "ZERO_RESULTS":
                    self.logger.warning(f"No results found for address: {address}")
                    return None
                else:
                    raise Exception(f"Geocoding API error: {data['status']}")
                    
            except RequestException as e:
                delay = initial_delay * (2 ** attempt)
                self.logger.warning(f"Geocoding attempt {attempt + 1} failed for {address}: {str(e)}. Retrying in {delay} seconds.")
                time.sleep(delay)
        
        self.logger.error(f"Geocoding failed for {address} after {max_retries} attempts")
        return None

class HospitalDataProcessor:
    def __init__(self):
        self.logger = logger
        self.logger.info("Initializing HospitalDataProcessor")
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        mapping_file = os.path.join(current_dir, 'hospital_mapping.json')
        
        try:
            with open(mapping_file, 'r') as f:
                self.hospital_mapping = json.load(f)
            self.logger.info(f"Loaded hospital mapping from {mapping_file}")
        except FileNotFoundError:
            self.logger.error(f"Error: hospital_mapping.json not found at {mapping_file}")
            self.hospital_mapping = {}
        
        google_maps_api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        if not google_maps_api_key:
            self.logger.error("GOOGLE_MAPS_API_KEY environment variable is not set")
            raise ValueError("GOOGLE_MAPS_API_KEY environment variable is not set")
        
        self.geocoding_service = GeocodingService(google_maps_api_key)
        self.logger.info("GeocodingService initialized")

    def process_hospitals(self, hospitals: List[Dict[str, Any]], last_run_time: datetime) -> List[Dict[str, Any]]:
        logger.info(f"Processing {len(hospitals)} hospitals")
        processed_hospitals = []
        for i, hospital in enumerate(hospitals, 1):
            logger.debug(f"Processing hospital {i}/{len(hospitals)}: {hospital.get('Facility Name', 'Unknown')}")
            
            # Check if the hospital data has been updated since the last run
            last_updated_str = hospital.get('Last Updated', '1970-01-01T00:00:00+00:00')
            try:
                last_updated = datetime.fromisoformat(last_updated_str.replace('Z', '+00:00'))
            except ValueError as e:
                logger.warning(f"Error parsing date for hospital {hospital.get('Facility Name', 'Unknown')}: {e}")
                last_updated = datetime.min.replace(tzinfo=timezone.utc)
            
            # Remove this condition to process all hospitals regardless of last update time
            # if last_updated <= last_run_time:
            #     logger.debug(f"Skipping hospital {hospital.get('Facility Name', 'Unknown')} - no updates")
            #     continue

            processed_hospital = self.clean_hospital_data(hospital)
            
            # Check if this hospital is in our mapping
            for website_id, mapped_data in self.hospital_mapping.items():
                if mapped_data['facility_id'] == processed_hospital['facility_id']:
                    processed_hospital['website_id'] = website_id
                    processed_hospital['has_live_wait_time'] = True
                    logger.debug(f"Matched hospital to website_id: {website_id}")
                    break
            
            # Add geocoding if needed
            if processed_hospital['latitude'] == 0 and processed_hospital['longitude'] == 0:
                logger.debug(f"Geocoding required for {processed_hospital['facility_name']}")
                coordinates = self.geocode_address(processed_hospital)
                if coordinates:
                    processed_hospital['latitude'], processed_hospital['longitude'] = coordinates
                    logger.debug(f"Geocoding successful for {processed_hospital['facility_name']}")
                else:
                    logger.warning(f"Geocoding failed for {processed_hospital['facility_name']}")
            
            processed_hospitals.append(processed_hospital)
            
            # Log progress every 100 hospitals
            if i % 100 == 0:
                logger.info(f"Processed {i} hospitals")
        
        logger.info(f"Processed {len(processed_hospitals)} hospitals")
        return processed_hospitals

    def geocode_address(self, hospital: Dict[str, Any]) -> tuple:
        address = f"{hospital['address']}, {hospital['city']}, {hospital['state']} {hospital['zip_code']}"
        self.logger.info(f"Geocoding address for {hospital['facility_name']}: {address}")
        return self.geocoding_service.geocode(address)

    @staticmethod
    def clean_hospital_data(hospital: Dict[str, Any]) -> Dict[str, Any]:
        logger.debug(f"Cleaning data for hospital: {hospital.get('Facility Name', 'Unknown')}")
        return {
            "facility_id": hospital.get("Facility ID"),
            "facility_name": hospital.get("Facility Name"),
            "address": hospital.get("Address"),
            "city": hospital.get("City/Town"),
            "state": hospital.get("State"),
            "zip_code": hospital.get("ZIP Code"),
            "county": hospital.get("County/Parish"),
            "phone_number": hospital.get("Telephone Number"),
            "emergency_services": hospital.get("emergency_services", False),
            "has_live_wait_time": False,  # Default value, updated in process_hospitals if necessary
            "latitude": 0,  # Will be updated by geocoding
            "longitude": 0,  # Will be updated by geocoding
        }