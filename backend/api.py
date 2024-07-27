from flask import Flask, jsonify, send_from_directory, send_file, request, render_template_string
from flask_cors import CORS
import psycopg2
import psycopg2.extras
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
    return send_from_directory(app.static_folder, path)
    # if os.path.exists(os.path.join(app.static_folder, path)):
    #     return send_from_directory(app.static_folder, path)
    # else:
    #     return "File not found", 404
    
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

def get_db_connection():
    return psycopg2.connect(
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
    )

@app.route('/api/hospitals', methods=['GET'])
def get_hospitals():
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)
    radius = request.args.get('radius', default=10, type=float)

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    query = """
    SELECT *
    FROM hospitals
    WHERE ST_DWithin(
        ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
        ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
        %s * 1609.34  -- Convert miles to meters
    )
    """
    cur.execute(query, (lon, lat, radius))
    hospitals = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify(hospitals)

@app.route('/')
def serve_frontend():
    return send_from_directory(app.static_folder, 'index.html')
    # with open(os.path.join(app.static_folder, 'index.html'), 'r') as file:
    #     html_content = file.read()
    
    # # Replace the placeholder with the actual API key
    # html_content = html_content.replace('{{GOOGLE_MAPS_API_KEY}}', GOOGLE_MAPS_API_KEY)
    
    # return render_template_string(html_content)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)