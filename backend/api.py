from flask import Flask, jsonify, send_from_directory, request, render_template
from flask_cors import CORS
import psycopg2
import psycopg2.extras
from helpers.config import DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, GOOGLE_MAPS_API_KEY
import os
import logging

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
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
        radius = float(request.args.get('radius', default=10))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid latitude, longitude, or radius"}), 400

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

    return jsonify(list(hospitals))

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