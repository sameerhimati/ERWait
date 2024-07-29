from flask_socketio import SocketIO, emit
from flask import request
from hospital_data_service import hospital_data_service
from logger_setup import logger

socketio = SocketIO()

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('request_initial_data')
def handle_initial_data_request(data):
    # Fetch initial data for the client
    hospitals = hospital_data_service.get_hospitals_paginated(
        page=1, 
        per_page=50, 
        lat=data.get('lat'), 
        lon=data.get('lon'), 
        radius=data.get('radius', 50)
    )
    emit('initial_data', hospitals[0])

def broadcast_wait_time_update(hospital_id, new_wait_time, is_live):
    try:
        socketio.emit('wait_time_update', {
            'hospital_id': hospital_id,
            'new_wait_time': new_wait_time,
            'is_live': is_live
        }, broadcast=True)
        logger.info(f"Broadcasted wait time update for hospital {hospital_id}")
    except Exception as e:
        logger.error(f"Failed to broadcast wait time update: {e}")

def init_socketio(app):
    socketio.init_app(app)
    return socketio