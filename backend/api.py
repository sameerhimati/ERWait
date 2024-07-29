from flask import Flask, jsonify, send_from_directory, request, render_template
from flask_cors import CORS
import psycopg2
import psycopg2.extras
from helpers.config import DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, GOOGLE_MAPS_API_KEY
import os
import logging
from hospital_data_service import hospital_data_service

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Set up Flask app
app = Flask(__name__, 
            static_folder=os.path.abspath('../frontend'),
            template_folder=os.path.abspath('../frontend'))
CORS(app)

def get_db_connection():
    return psycopg2.connect(
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
    )

@app.route('/api/hospitals', methods=['GET'])
def get_hospitals():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        search_term = request.args.get('search', None)
        
        result = hospital_data_service.get_hospitals_paginated(page, per_page, search_term)
        
        return jsonify(result)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid parameters"}), 400

@app.route('/api/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message')
    # Implement chat logic here
    response = f"You said: {user_input}"
    return jsonify({"response": response})

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
        return send_from_directory(app.static_folder, path)
    else:
        return render_template('index.html', google_maps_api_key=GOOGLE_MAPS_API_KEY)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)