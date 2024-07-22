from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import psycopg2
from config import DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
from logger_setup import logger
import os
import requests

app = Flask(__name__, static_folder='frontend')
CORS(app)

@app.route('/')
def serve_frontend():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)

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
            hospitals.append({
                "name": row[0],
                "address": row[1],
                "waitTime": row[2]
            })

        return jsonify(hospitals)
    except Exception as e:
        logger.error("Error fetching hospital data: %s", e)
        return jsonify({"error": "Internal server error"}), 500

def geocode_address(address):
    try:
        response = requests.get(f"https://nominatim.openstreetmap.org/search?format=json&q={address}")
        data = response.json()
        if data:
            return float(data[0]['lat']), float(data[0]['lon'])
        return None
    except Exception as e:
        logger.error(f"Geocoding error: {e}")
        return None

if __name__ == '__main__':
    app.run(debug=True)