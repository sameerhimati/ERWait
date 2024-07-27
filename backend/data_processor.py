import json
import os
from typing import List, Dict, Any
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import time
import logging

class HospitalDataProcessor:
    def __init__(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        mapping_file = os.path.join(current_dir, 'hospital_mapping.json')
        
        try:
            with open(mapping_file, 'r') as f:
                self.hospital_mapping = json.load(f)
        except FileNotFoundError:
            print(f"Error: hospital_mapping.json not found at {mapping_file}")
            self.hospital_mapping = {}
        
        self.geolocator = Nominatim(user_agent="healthguide_app")
        self.logger = logging.getLogger(__name__)

    def process_hospitals(self, hospitals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        processed_hospitals = []
        for hospital in hospitals:
            processed_hospital = self.clean_hospital_data(hospital)
            
            # Check if this hospital is in our mapping
            for website_id, mapped_data in self.hospital_mapping.items():
                if mapped_data['facility_id'] == processed_hospital['facility_id']:
                    processed_hospital['website_id'] = website_id
                    processed_hospital['has_live_wait_time'] = True
                    break
            
            # Add geocoding
            if processed_hospital['latitude'] == 0 and processed_hospital['longitude'] == 0:
                lat, lon = self.geocode_address(processed_hospital)
                processed_hospital['latitude'] = lat
                processed_hospital['longitude'] = lon
            
            processed_hospitals.append(processed_hospital)
        
        return processed_hospitals

    def geocode_address(self, hospital: Dict[str, Any], max_retries=3) -> tuple:
        address = f"{hospital['address']}, {hospital['city']}, {hospital['state']} {hospital['zip_code']}"
        for attempt in range(max_retries):
            try:
                location = self.geolocator.geocode(address)
                if location:
                    return location.latitude, location.longitude
                time.sleep(1)  # Be nice to the geocoding service
            except (GeocoderTimedOut, GeocoderUnavailable) as e:
                self.logger.warning(f"Geocoding attempt {attempt + 1} failed for {address}: {str(e)}")
                time.sleep(2 ** attempt)  # Exponential backoff
        
        self.logger.error(f"Geocoding failed for {address} after {max_retries} attempts")
        return 0, 0  # Return default values if geocoding fails

    @staticmethod
    def clean_hospital_data(hospital: Dict[str, Any]) -> Dict[str, Any]:
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