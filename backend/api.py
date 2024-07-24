from flask import Flask, jsonify, send_from_directory, send_file, request, render_template_string
from flask_cors import CORS
import psycopg2
from helpers.config import DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, GOOGLE_MAPS_API_KEY
import os
import googlemaps
import logging
from chat_service import get_chat_response
from price_comparison_service import get_price_comparison

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
    
@app.route('/api/geocode', methods=['GET'])
def geocode():
    address = request.args.get('address')
    if not address:
        return jsonify({"error": "No address provided"}), 400

    try:
        result = gmaps.geocode(address)
        if result:
            location = result[0]['geometry']['location']
            return jsonify({"lat": location['lat'], "lon": location['lng']})
        return jsonify({"error": "Address not found"}), 404
    except Exception as e:
        logger.error(f"Geocoding error for address {address}: {str(e)}")
        return jsonify({"error": "Geocoding failed"}), 500
    

@app.route('/<path:path>')
def serve_static(path):
    if os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return "File not found", 404
    
@app.route('/api/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message')
    response = get_chat_response(user_input)
    return jsonify({"response": response})

@app.route('/api/price-comparison', methods=['POST'])
def price_comparison():
    zip_code = request.json.get('zipCode')
    treatment = request.json.get('treatment')
    results = get_price_comparison(zip_code, treatment)
    return jsonify(results)

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
        
        # Join the hospital_wait_times and hospital_pages tables
        cursor.execute("""
            SELECT hwt.hospital_name, hwt.hospital_address, hwt.wait_time, hp.url, hwt.network_name
            FROM hospital_wait_times hwt
            LEFT JOIN hospital_pages hp ON hwt.network_name = hp.network_name
        """)
        rows = cursor.fetchall()
        conn.close()

        hospitals = []
        for row in rows:
            hospital = {
                "name": row[0],
                "address": row[1] if row[1] != "Hospital address not found" else "Address unavailable",
                "waitTime": row[2],
                "website": row[3] if row[3] else "#",
                "networkName": row[4]
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

@app.route('/')
def serve_frontend():
    with open(os.path.join(app.static_folder, 'index.html'), 'r') as file:
        html_content = file.read()
    
    # Replace the placeholder with the actual API key
    html_content = html_content.replace('{{GOOGLE_MAPS_API_KEY}}', GOOGLE_MAPS_API_KEY)
    
    return render_template_string(html_content)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)