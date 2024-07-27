import time
import numpy as np
import cv2
import base64
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import psycopg2
from psycopg2.extras import execute_values
from logger_setup import logger
from dotenv import load_dotenv
import json
import os

from helpers.fetch_data import fetch_hospital_data
from helpers.config import OPENAI_API_KEY, DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
from helpers.hospital_search import get_hospital_address_geocoding
from cms_api_client import CMSAPIClient
from data_processor import HospitalDataProcessor

load_dotenv()  # Load environment variables from .env

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
                    "If you don't find an address fill it with 'Hospital address not found'. If you don't find a wait time fill it with 'Wait time not found'. "
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

def hospital_search(hospital_name, network_name):
    return get_hospital_address_geocoding(hospital_name, network_name)

def parse_extracted_data(extracted_data, network_name):
    wait_times = []

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
            wait_times.append((hospital_name, hospital_address, wait_time))
    except json.JSONDecodeError as e:
        logger.error("Error parsing JSON: %s", e)

    return wait_times

def capture_full_page_screenshot(driver):
    total_height = driver.execute_script("return document.body.scrollHeight")
    viewport_height = driver.execute_script("return window.innerHeight")
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

    return stitched_image

def sync_cms_data(cursor):
    cms_client = CMSAPIClient()
    processor = HospitalDataProcessor()

    raw_hospitals = cms_client.get_all_hospitals()
    processed_hospitals = processor.process_hospitals(raw_hospitals)

    execute_values(cursor, """
        INSERT INTO hospitals (
            facility_id, website_id, facility_name, address, city, state, zip_code, county,
            phone_number, emergency_services, has_live_wait_time, latitude, longitude
        ) VALUES %s
        ON CONFLICT (facility_id) DO UPDATE SET
            website_id = EXCLUDED.website_id,
            facility_name = EXCLUDED.facility_name,
            address = EXCLUDED.address,
            city = EXCLUDED.city,
            state = EXCLUDED.state,
            zip_code = EXCLUDED.zip_code,
            county = EXCLUDED.county,
            phone_number = EXCLUDED.phone_number,
            emergency_services = EXCLUDED.emergency_services,
            has_live_wait_time = EXCLUDED.has_live_wait_time,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude
    """, [(
        h['facility_id'], h.get('website_id'), h['facility_name'], h['address'],
        h['city'], h['state'], h['zip_code'], h['county'], h['phone_number'],
        h['emergency_services'], h['has_live_wait_time'], h['latitude'], h['longitude']
    ) for h in processed_hospitals])


def main():
    rows = fetch_hospital_data()

    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=chrome_options)
    except Exception as e:
        logger.error("Error initializing WebDriver: %s", e)
        raise

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

        # Sync CMS data
        sync_cms_data(cursor)
        logger.info("Synced CMS data")

        for row in rows:
            url, network_name, hospital_num = row
            try:
                driver.get(url)
                time.sleep(5)  # Wait for the page to load completely

                img = capture_full_page_screenshot(driver)
                logger.debug(f"Captured full-page screenshot for URL: {url}")

                base64_image = encode_image(img)

                extracted_data = get_wait_times_from_image(OPENAI_API_KEY, base64_image, network_name, hospital_num, detail='high')

                wait_times = parse_extracted_data(extracted_data, network_name)

                if not wait_times:
                    logger.error("No wait times extracted for URL: %s", url)
                    continue

                # Update wait times in the database
                for hospital_name, hospital_address, wait_time in wait_times:
                    cursor.execute("""
                        WITH hospital_id AS (
                            SELECT id FROM hospitals 
                            WHERE facility_name = %s AND address = %s
                        )
                        INSERT INTO wait_times (hospital_id, wait_time)
                        SELECT id, %s FROM hospital_id
                    """, (hospital_name, hospital_address, wait_time))
                    conn.commit()
                logger.info(f"Stored wait times for network: {network_name}")

            except Exception as e:
                logger.error("Error processing URL %s: %s", url, e)
                continue

    except Exception as e:
        logger.error("Error connecting to the database: %s", e)
        raise

    finally:
        if conn:
            conn.close()
        driver.quit()
        logger.info("Closed database connection and WebDriver")

if __name__ == "__main__":
    main()