import csv
from typing import Dict, List, Any, Optional
import logging
import os

class CMSAPIClient:
    def __init__(self):
        self.csv_path = os.path.join(os.path.dirname(__file__), 'data', 'Hospital_General_Information.csv')
        self.logger = logging.getLogger(__name__)

    def get_all_hospitals(self) -> List[Dict[str, Any]]:
        """Fetch all hospital data from the CSV file."""
        self.logger.info(f"Reading CSV file: {self.csv_path}")
        
        hospitals = {}
        with open(self.csv_path, 'r') as csvfile:
            csv_reader = csv.DictReader(csvfile)
            for row in csv_reader:
                facility_id = row['Facility ID']
                if facility_id not in hospitals:
                    hospitals[facility_id] = {
                        'Facility ID': facility_id,
                        'Facility Name': row['Facility Name'],
                        'Address': row['Address'],
                        'City/Town': row['City/Town'],
                        'State': row['State'],
                        'ZIP Code': row['ZIP Code'],
                        'County/Parish': row['County/Parish'],
                        'Telephone Number': row['Telephone Number'],
                        'emergency_services': False
                    }
                
                # Check for emergency services
                if row['Measure ID'] == 'EDV' and row['Measure Name'] == 'Emergency department volume':
                    hospitals[facility_id]['emergency_services'] = True

        self.logger.info(f"Successfully processed {len(hospitals)} unique hospitals")
        return list(hospitals.values())

    def get_hospital_by_id(self, facility_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a specific hospital by its facility ID."""
        hospitals = self.get_all_hospitals()
        for hospital in hospitals:
            if hospital['Facility ID'] == facility_id:
                return hospital
        return None