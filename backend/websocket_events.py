from flask_socketio import SocketIO
import asyncio
from flask import request
from hospital_data_service import hospital_data_service
from logger_setup import logger
import urllib3

urllib3.disable_warnings(urllib3.exceptions.NotOpenSSLWarning)

class SocketIOWrapper:
    _instance = None

    @classmethod
    def initialize(cls, app):
        if cls._instance is None:
            cls._instance = SocketIO(app, async_mode='asyncio', cors_allowed_origins="*")
        return cls._instance

    @classmethod
    def get_instance(cls):
        return cls._instance

    @classmethod
    def is_initialized(cls):
        return cls._instance is not None

def init_socketio(app):
    socketio = SocketIOWrapper.initialize(app)
    
    @socketio.on('connect')
    def handle_connect():
        logger.info('Client connected')

    @socketio.on('disconnect')
    def handle_disconnect():
        logger.info('Client disconnected')

    @socketio.on('request_initial_data')
    def handle_initial_data_request(data):
        logger.info('Received request for initial data')
        hospitals = hospital_data_service.get_hospitals_paginated(
            page=1, 
            per_page=50, 
            lat=data.get('lat'), 
            lon=data.get('lon'), 
            radius=data.get('radius', 50)
        )
        socketio.emit('initial_data', hospitals[0])

    logger.info("SocketIO initialized successfully")
    return socketio

async def broadcast_wait_time_update(hospital_id, new_wait_time, is_live):
    if not SocketIOWrapper.is_initialized():
        logger.info("SocketIO not initialized. Skipping real-time broadcast.")
        return

    try:
        socketio = SocketIOWrapper.get_instance()
        def emit_update():
            socketio.emit('wait_time_update', {
                'hospital_id': hospital_id,
                'new_wait_time': new_wait_time,
                'is_live': is_live
            }, broadcast=True)

        await asyncio.get_event_loop().run_in_executor(None, emit_update)
        logger.info(f"Broadcasted wait time update for hospital {hospital_id}")
    except Exception as e:
        logger.error(f"Failed to broadcast wait time update: {e}")
        logger.info("Continuing execution without broadcasting.")