from flask import Flask, jsonify, send_from_directory, request, render_template
from flask_cors import CORS
import psycopg2
import psycopg2.extras
from helpers.config import DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, GOOGLE_MAPS_API_KEY
import os
from hospital_data_service import hospital_data_service
from websocket_events import init_socketio
# Set up logging
from logger_setup import logger

# Set up Flask app
app = Flask(__name__, 
            static_folder=os.path.abspath('../frontend'),
            template_folder=os.path.abspath('../frontend'))
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = init_socketio(app)

def get_db_connection():
    return psycopg2.connect(
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
    )

@app.route('/styles.css')
def serve_css():
    return send_from_directory(app.static_folder, 'css/styles.css', mimetype='text/css')

@app.route('/api/hospitals', methods=['GET'])
def get_hospitals():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        search_term = request.args.get('search', None)
        lat = float(request.args.get('lat', 0))
        lon = float(request.args.get('lon', 0))
        radius = float(request.args.get('radius', 0))
        
        logger.debug(f"Fetching hospitals: page={page}, per_page={per_page}, search_term={search_term}, lat={lat}, lon={lon}, radius={radius}")
        
        result, debug_info = hospital_data_service.get_hospitals_paginated(page, per_page, search_term, lat, lon, radius)
        
        # Process the data to match our new schema
        for hospital in result['hospitals']:
            if not hospital['has_wait_time_data']:
                hospital['wait_time'] = None
            elif hospital['wait_time'] is None or hospital['wait_time'] == '':
                hospital['wait_time'] = 'N/A'
            else:
                hospital['wait_time'] = int(hospital['wait_time'])
        
        logger.debug(f"SQL Query: {debug_info['query']}")
        logger.debug(f"SQL Parameters: {debug_info['params']}")
        logger.debug(f"Fetched {len(result['hospitals'])} hospitals")
        
        return jsonify(result)
    except (TypeError, ValueError) as e:
        logger.error(f"Invalid parameters: {str(e)}")
        return jsonify({"error": "Invalid parameters"}), 400


@app.route('/api/price-comparison', methods=['POST'])
def price_comparison():
    zip_code = request.json.get('zipCode')
    treatment = request.json.get('treatment')
    # Implement price comparison logic here
    results = [{"facilityName": "Sample Hospital", "price": 1000}]
    return jsonify(results)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        if path.endswith('.js'):
            return send_from_directory(app.static_folder, path, mimetype='application/javascript')
        elif path.endswith('.css'):
            return send_from_directory(app.static_folder, path, mimetype='text/css')
        return send_from_directory(app.static_folder, path)
    else:
        return render_template('index.html', google_maps_api_key=GOOGLE_MAPS_API_KEY)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
