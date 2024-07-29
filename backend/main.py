import time
import numpy as np
import sys
import cv2
import base64
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import psycopg2
from psycopg2.extras import execute_values
from contextlib import contextmanager
from logger_setup import logger
from dotenv import load_dotenv
import json
import os
from datetime import datetime, timezone
from helpers.config import OPENAI_API_KEY, DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
from hospital_data_service import hospital_data_service
from tasks import sync_cms_data_task
from background_tasks import run_task_in_background
import urllib3
urllib3.disable_warnings(urllib3.exceptions.NotOpenSSLWarning)
from websocket_events import broadcast_wait_time_update
from hospital_data_service import hospital_data_service
from websocket_events import broadcast_wait_time_update

load_dotenv()  # Load environment variables from .env

@contextmanager
def get_db_cursor():
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def encode_image(image):
    _, buffer = cv2.imencode('.png', image)
    return base64.b64encode(buffer).decode('utf-8')

def get_wait_times_from_image(api_key, base64_image, network_name, hospital_num, detail='auto'):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an assistant that extracts hospital names, addresses, and wait times from screenshots of hospital network websites. "
                    "Your output should be in the following JSON format: "
                    "{\"hospitals\": [{\"hospital_name\": \"<hospital_name>\", \"address\": \"<hospital_address>\", \"wait_time\": \"<wait_time>\"}]}. "
                    f"This page belongs to the hospital network {network_name}, and you need to extract information for {hospital_num} hospitals. "
                    "The address will sometimes include phone numbers and other information that isn't the address. Make sure to only include the street address. "
                    "If you don't find an address fill it with 'Hospital address not found'. If you don't find a wait time fill it with '0'. It cannot be a string. "
                    "All wait times should be in minutes so if the wait time is 30 minutes, it should be written as 30 and if it's 1 hour, it should be written as 60. "
                    "All the outputs should be strings. Output nothing else other than the json."
                )
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Please extract all hospital names, addresses, and their corresponding wait times from the image."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}",
                            "detail": detail
                        }
                    }
                ]
            }
        ],
        "max_tokens": 1500
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
    if response.status_code == 200:
        extracted_data = response.json()['choices'][0]['message']['content']
        logger.debug(f"Extracted data type: {type(extracted_data)}")
        logger.debug(f"Extracted data: {extracted_data}")
        return extracted_data
    else:
        logger.error("Error from OpenAI API: %s", response.json())
        return ""

def hospital_search(hospital_name, network_name=""):
    # Replace with your actual Google Maps API key
    api_key = "your_google_maps_api_key"
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    
    params = {
        "address": network_name + " " + hospital_name,
        "key": api_key
    }
    
    response = requests.get(base_url, params=params)
    data = response.json()
    
    if data["status"] == "OK":
        address = data["results"][0]["formatted_address"]
        return address
    else:
        return "Address not found"
    
import requests


def parse_extracted_data(extracted_data, network_name):
    extracted_hospitals = []
    try:
        # Remove any leading/trailing triple backticks
        if extracted_data.startswith("```json"):
            extracted_data = extracted_data[7:]  # Remove "```json\n"
        if extracted_data.endswith("```"):
            extracted_data = extracted_data[:-3]  # Remove "```"

        data = json.loads(extracted_data)
        hospitals = data.get("hospitals", [])
        for hospital in hospitals:
            hospital_name = hospital.get("hospital_name", "").strip()
            hospital_address = hospital.get("address", "").strip()
            if hospital_address == "Hospital address not found" or not hospital_address[-3:].isdigit():
                new_address = hospital_search(hospital_name, network_name)
                if new_address != "Address not found":
                    hospital_address = new_address
                # If hospital_search also fails, keep the original address
            wait_time = hospital.get("wait_time", "").strip()
            
            extracted_hospitals.append({
                "hospital_name": hospital_name,
                "address": hospital_address,
                "wait_time": wait_time,
                "network_name": network_name
            })
    except json.JSONDecodeError as e:
        logger.error("Error parsing JSON: %s", e)

    return extracted_hospitals

def capture_full_page_screenshot(driver):
    total_height = driver.execute_script("return document.body.scrollHeight")
    viewport_height = driver.execute_script("return window.innerHeight")
    #driver.set_window_size(1280, viewport_height)
    
    stitched_image = None
    for y in range(0, total_height, viewport_height):
        driver.execute_script(f"window.scrollTo(0, {y});")
        time.sleep(1)
        screenshot = driver.get_screenshot_as_png()
        np_image = np.frombuffer(screenshot, np.uint8)
        img = cv2.imdecode(np_image, cv2.IMREAD_COLOR)
        
        if stitched_image is None:
            stitched_image = img
        else:
            stitched_image = np.vstack((stitched_image, img))
    
    # Resize the image to reduce its size
    scale_percent = 50  # percent of original size
    width = int(stitched_image.shape[1] * scale_percent / 100)
    height = int(stitched_image.shape[0] * scale_percent / 100)
    dim = (width, height)
    resized = cv2.resize(stitched_image, dim, interpolation = cv2.INTER_AREA)
    
    return resized


def get_last_run_time(cursor):
    cursor.execute("SELECT last_run FROM script_metadata WHERE script_name = 'main_script'")
    result = cursor.fetchone()
    if result:
        last_run = result[0]
        if last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=timezone.utc)
        return last_run
    else:
        return datetime.min.replace(tzinfo=timezone.utc)

def update_last_run_time(cursor):
    current_time = datetime.now(timezone.utc)
    cursor.execute("""
        INSERT INTO script_metadata (script_name, last_run)
        VALUES ('main_script', %s)
        ON CONFLICT (script_name) DO UPDATE SET last_run = EXCLUDED.last_run
    """, (current_time,))

def update_wait_times(cursor, hospital_identifier, wait_time):
    try:
        # Update the database
        result = hospital_data_service.update_wait_times(cursor, hospital_identifier, wait_time, is_live=True)
        
        if result:
            logger.info(f"Updated live wait time for {hospital_identifier}")
            # Attempt to broadcast the update, but don't let it block or crash the process
            try:
                broadcast_wait_time_update(hospital_identifier, wait_time, is_live=True)
            except Exception as broadcast_error:
                logger.error(f"Failed to broadcast wait time update: {broadcast_error}")
        else:
            logger.warning(f"No matching hospital found for {hospital_identifier}")

    except Exception as e:
        logger.error(f"Error updating wait time for {hospital_identifier}: {e}")
        raise

def verify_data_insertion(cursor):
    cursor.execute("SELECT COUNT(*) FROM hospitals")
    hospital_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM wait_times")
    wait_time_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM hospital_pages")
    hospital_pages_count = cursor.fetchone()[0]
    
    logger.info(f"Data verification: Hospitals: {hospital_count}, Wait Times: {wait_time_count}, Hospital Pages: {hospital_pages_count}")

def run_sync_cms_data_task(last_run_time):
    logger.info("Starting CMS data sync task")
    try:
        with get_db_cursor() as cursor:
            hospital_data_service.sync_cms_data(cursor, last_run_time)
        logger.info("CMS data sync task completed successfully")
    except Exception as e:
        logger.error(f"Error in CMS data sync task: {str(e)}", exc_info=True)
        raise

def main():
    logger.info("Starting main process")
    
    driver = None
    try:
        with get_db_cursor() as cursor:
            logger.info("Database connection established")

            # Populate hospital_pages table
            logger.info("Populating hospital_pages table")
            hospital_pages_data = [
                ("Edward Health Elmhurst", "https://www.eehealth.org/services/emergency/wait-times/", 3),
                ("Piedmont", "https://www.piedmont.org/emergency-room-wait-times/emergency-room-wait-times", 21),
                ("Baptist", "https://www.baptistonline.org/services/emergency", 18),
                ("Northern Nevada Sparks", "https://www.nnmc.com/services/emergency-medicine/er-at-sparks/", 1),
                ("Northern Nevada Reno", "https://www.nnmc.com/services/emergency-medicine/er-at-reno/", 1),
                ("Northern Nevada Spanish", "https://www.nnmc.com/services/emergency-medicine/er-at-spanish/", 1),
                ("Metro Health", "https://www.metrohealth.org/emergency-room", 4)
            ]
            try:
                hospital_data_service.populate_hospital_pages(cursor, hospital_pages_data)
            except AttributeError:
                logger.warning("populate_hospital_pages method not found. Skipping population.")
            except Exception as e:
                logger.error(f"Error populating hospital pages: {e}")

            last_run_time = get_last_run_time(cursor)
            logger.info(f"Last successful run: {last_run_time}")

            # Run CMS data sync task
            logger.info("Starting CMS data sync task")
            task = run_task_in_background(run_sync_cms_data_task, last_run_time)
            
            task.join()

            # Fetch all database hospitals for later matching
            database_hospitals = hospital_data_service.get_all_database_hospitals(cursor)
            logger.info(f"Fetched {len(database_hospitals)} hospitals from database for matching")

            # Initialize WebDriver
            logger.info("Initializing WebDriver")
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--window-size=1920,1080")  # Set a specific window size
            driver = webdriver.Chrome(options=chrome_options)
            logger.info("WebDriver initialized successfully")

            # Fetch hospital pages data
            logger.info("Fetching hospital pages data")
            rows = hospital_data_service.fetch_hospital_network_data()
            logger.info(f"Fetched {len(rows)} hospital pages")

            for row in rows:
                url, hospital_name, hospital_num = row
                logger.info(f"Processing network: {hospital_name}, URL: {url}")
                try:
                    driver.get(url)
                    logger.info(f"Loaded URL: {url}")
                    time.sleep(5)

                    img = capture_full_page_screenshot(driver)
                    logger.info(f"Captured full-page screenshot for URL: {url}")

                    base64_image = encode_image(img)
                    logger.info("Encoded screenshot to base64")

                    extracted_data = get_wait_times_from_image(OPENAI_API_KEY, base64_image, hospital_name, hospital_num, detail='high')
                    print(extracted_data)
                    logger.info("Extracted wait times from image")

                    extracted_hospitals = parse_extracted_data(extracted_data, hospital_name)

                    if not extracted_hospitals:
                        logger.warning(f"No wait times extracted for URL: {url}")
                        continue

                    logger.info(f"Matching extracted hospitals with database for network: {hospital_name}")
                    matched_pairs = hospital_data_service.match_hospitals_from_screenshot(extracted_hospitals, database_hospitals, hospital_name)

                    for pair in matched_pairs:
                        extracted_hospital = pair['extracted']
                        matched_hospital = pair['matched']
                        match_score = pair['score']
                        logger.info(f"Matched {extracted_hospital['hospital_name']} to {matched_hospital['facility_name']} with score {match_score}")
                        update_wait_times(cursor, matched_hospital['id'], extracted_hospital['wait_time'])

                    logger.info(f"Completed processing for network: {hospital_name}")

                except Exception as e:
                    logger.error(f"Error processing URL {url}: {str(e)}")
                    continue

            logger.info("Updating last run time")
            update_last_run_time(cursor)

            logger.info("Verifying data insertion")
            verify_data_insertion(cursor)

        logger.info("All operations completed successfully. Transaction committed.")

    except Exception as e:
        logger.error(f"Critical error in main process: {e}", exc_info=True)
        raise

    finally:
        if driver:
            driver.quit()
            logger.info("Closed WebDriver")

    logger.info("Main process completed")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Unhandled exception in main: {e}", exc_info=True)