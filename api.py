from flask import Flask, jsonify, send_from_directory, send_file
from flask_cors import CORS
import psycopg2
from config import DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, GOOGLE_MAPS_API_KEY
import os
import googlemaps
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=os.path.abspath('frontend'))
CORS(app)

# Initialize the Google Maps client
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

def geocode_address(address):
    if address == "Hospital address not found":
        return None
    
    try:
        result = gmaps.geocode(address)
        if result:
            location = result[0]['geometry']['location']
            return location['lat'], location['lng']
        return None
    except Exception as e:
        logger.error(f"Geocoding error for address {address}: {str(e)}")
        return None

@app.route('/')
def serve_frontend():
    return send_file(os.path.join(app.static_folder, 'index.html'))

@app.route('/<path:path>')
def serve_static(path):
    if os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return "File not found", 404

@app.route('/api/hospitals', methods=['GET'])
def get_hospitals():
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute("SELECT hospital_name, hospital_address, wait_time FROM hospital_wait_times")
        rows = cursor.fetchall()
        conn.close()

        hospitals = []
        for row in rows:
            hospital = {
                "name": row[0],
                "address": row[1] if row[1] != "Hospital address not found" else "Address unavailable",
                "waitTime": row[2]
            }
            if row[1] != "Hospital address not found":
                coordinates = geocode_address(row[1])
                if coordinates:
                    hospital["lat"] = coordinates[0]
                    hospital["lon"] = coordinates[1]
            hospitals.append(hospital)

        logger.info(f"Processed {len(hospitals)} hospitals")
        return jsonify(hospitals)
    except Exception as e:
        logger.error(f"Error fetching hospital data: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)