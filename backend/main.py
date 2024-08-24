import asyncio
import aiohttp
import time
import numpy as np
import cv2
import base64
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import asyncpg
from contextlib import asynccontextmanager
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
from websocket_events import broadcast_wait_time_update
from tenacity import retry, stop_after_attempt, wait_exponential

urllib3.disable_warnings(urllib3.exceptions.NotOpenSSLWarning)

load_dotenv()

@asynccontextmanager
async def get_db_pool():
    pool = await asyncpg.create_pool(
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    try:
        yield pool
    finally:
        await pool.close()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def get_wait_times_from_image(api_key, base64_image, network_name, hospital_num, detail='auto'):
    async with aiohttp.ClientSession() as session:
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

        async with session.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                extracted_data = data['choices'][0]['message']['content']
                logger.debug(f"Extracted data type: {type(extracted_data)}")
                logger.debug(f"Extracted data: {extracted_data}")
                return extracted_data
            else:
                error_data = await response.json()
                logger.error(f"Error from OpenAI API: {error_data}")
                raise Exception(f"OpenAI API error: {error_data}")

async def capture_full_page_screenshot(driver):
    total_height = await asyncio.to_thread(driver.execute_script, "return document.body.scrollHeight")
    viewport_height = await asyncio.to_thread(driver.execute_script, "return window.innerHeight")
    
    stitched_image = None
    for y in range(0, total_height, viewport_height):
        await asyncio.to_thread(driver.execute_script, f"window.scrollTo(0, {y});")
        await asyncio.sleep(1)
        screenshot = await asyncio.to_thread(driver.get_screenshot_as_png)
        np_image = np.frombuffer(screenshot, np.uint8)
        img = cv2.imdecode(np_image, cv2.IMREAD_COLOR)
        
        if stitched_image is None:
            stitched_image = img
        else:
            stitched_image = np.vstack((stitched_image, img))
    
    scale_percent = 50
    width = int(stitched_image.shape[1] * scale_percent / 100)
    height = int(stitched_image.shape[0] * scale_percent / 100)
    dim = (width, height)
    resized = cv2.resize(stitched_image, dim, interpolation = cv2.INTER_AREA)
    
    return resized

def encode_image(image):
    _, buffer = cv2.imencode('.png', image)
    return base64.b64encode(buffer).decode('utf-8')

async def parse_extracted_data(extracted_data, network_name):
    extracted_hospitals = []
    try:
        if extracted_data.startswith("```json"):
            extracted_data = extracted_data[7:]
        if extracted_data.endswith("```"):
            extracted_data = extracted_data[:-3]

        data = json.loads(extracted_data)
        hospitals = data.get("hospitals", [])
        for hospital in hospitals:
            hospital_name = hospital.get("hospital_name", "").strip()
            hospital_address = hospital.get("address", "").strip()
            if hospital_address == "Hospital address not found" or not hospital_address[-3:].isdigit():
                new_address = await hospital_search(hospital_name, network_name)
                if new_address != "Address not found":
                    hospital_address = new_address
            wait_time = hospital.get("wait_time", "").strip()
            
            extracted_hospitals.append({
                "hospital_name": hospital_name,
                "address": hospital_address,
                "wait_time": wait_time,
                "network_name": network_name
            })
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON: {e}")
        logger.error(f"Raw extracted data: {extracted_data}")

    return extracted_hospitals

async def hospital_search(hospital_name, network_name=""):
    api_key = os.getenv('GOOGLE_MAPS_API_KEY')
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    
    params = {
        "address": f"{network_name} {hospital_name}",
        "key": api_key
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(base_url, params=params) as response:
            data = await response.json()
    
    if data["status"] == "OK":
        address = data["results"][0]["formatted_address"]
        return address
    else:
        return "Address not found"

async def process_hospital_page(url, hospital_name, hospital_num, driver, database_hospitals, pool):
    logger.info(f"Processing network: {hospital_name}, URL: {url}")
    try:
        await asyncio.to_thread(driver.get, url)
        logger.info(f"Loaded URL: {url}")
        
        # Wait for the page to load
        try:
            await asyncio.to_thread(
                WebDriverWait(driver, 10).until,
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except Exception as e:
            logger.error(f"Timeout waiting for page to load: {url}")
            return

        await asyncio.sleep(5)

        img = await capture_full_page_screenshot(driver)
        logger.info(f"Captured full-page screenshot for URL: {url}")

        base64_image = encode_image(img)
        logger.info("Encoded screenshot to base64")

        extracted_data = await get_wait_times_from_image(OPENAI_API_KEY, base64_image, hospital_name, hospital_num, detail='high')
        logger.info("Extracted wait times from image")
        logger.debug(f"Extracted data for {hospital_name}: {extracted_data}")

        extracted_hospitals = await parse_extracted_data(extracted_data, hospital_name)

        if not extracted_hospitals:
            logger.warning(f"No wait times extracted for URL: {url}")
            return

        logger.info(f"Matching extracted hospitals with database for network: {hospital_name}")
        matched_pairs = await asyncio.to_thread(
            hospital_data_service.match_hospitals_from_screenshot,
            extracted_hospitals,
            database_hospitals,
            hospital_name
        )

        async with pool.acquire() as conn:
            for pair in matched_pairs:
                extracted_hospital = pair['extracted']
                matched_hospital = pair['matched']
                match_score = pair['score']
                logger.info(f"Matched {extracted_hospital['hospital_name']} to {matched_hospital['facility_name']} with score {match_score}")
                await update_wait_times(conn, matched_hospital['id'], extracted_hospital['wait_time'])

        logger.info(f"Completed processing for network: {hospital_name}")

    except Exception as e:
        logger.error(f"Error processing URL {url}: {str(e)}", exc_info=True)

async def update_wait_times(conn, hospital_id, wait_time):
    try:
        await conn.execute("""
            UPDATE hospitals
            SET wait_time = $1,
                has_wait_time_data = TRUE,
                has_live_wait_time = TRUE,
                last_updated = NOW()
            WHERE id = $2
        """, wait_time, hospital_id)
        logger.info(f"Updated wait time for hospital {hospital_id}")
        
        # Call the broadcast function
        await broadcast_wait_time_update(hospital_id, wait_time, True)
    except Exception as e:
        logger.error(f"Error updating wait time for hospital {hospital_id}: {e}")

async def get_last_run_time(conn):
    row = await conn.fetchrow("SELECT last_run FROM script_metadata WHERE script_name = 'main_script'")
    if row:
        last_run = row['last_run']
        if last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=timezone.utc)
        return last_run
    else:
        return datetime.min.replace(tzinfo=timezone.utc)

async def update_last_run_time(conn):
    current_time = datetime.now(timezone.utc)
    await conn.execute("""
        INSERT INTO script_metadata (script_name, last_run)
        VALUES ('main_script', $1)
        ON CONFLICT (script_name) DO UPDATE SET last_run = EXCLUDED.last_run
    """, current_time)

async def main():
    logger.info("Starting main process")
    
    driver = None
    try:
        async with get_db_pool() as pool:
            async with pool.acquire() as conn:
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
                    await conn.executemany("""
                        INSERT INTO hospital_pages (hospital_name, url, hospital_num)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (hospital_name) DO UPDATE SET
                            url = EXCLUDED.url,
                            hospital_num = EXCLUDED.hospital_num
                    """, hospital_pages_data)
                except Exception as e:
                    logger.error(f"Error populating hospital pages: {e}")

                last_run_time = await get_last_run_time(conn)
                logger.info(f"Last successful run: {last_run_time}")

                # Run CMS data sync task
                logger.info("Starting CMS data sync task")
                await asyncio.to_thread(run_task_in_background, sync_cms_data_task, last_run_time)

                # Fetch all database hospitals for later matching
                database_hospitals = await conn.fetch("""
                    SELECT id, facility_id, facility_name, address, city, state, zip_code, latitude, longitude
                    FROM hospitals
                """)
                logger.info(f"Fetched {len(database_hospitals)} hospitals from database for matching")

                # Initialize WebDriver
                logger.info("Initializing WebDriver")
                chrome_options = Options()
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--window-size=1920,1080")
                driver = webdriver.Chrome(options=chrome_options)
                logger.info("WebDriver initialized successfully")

                # Fetch hospital pages data
                logger.info("Fetching hospital pages data")
                rows = await conn.fetch("SELECT url, hospital_name, hospital_num FROM hospital_pages")
                logger.info(f"Fetched {len(rows)} hospital pages")

                # Process hospital pages concurrently
                tasks = [process_hospital_page(row['url'], row['hospital_name'], row['hospital_num'], driver, database_hospitals, pool) for row in rows]
                await asyncio.gather(*tasks)

                logger.info("Updating last run time")
                await update_last_run_time(conn)

                logger.info("Verifying data insertion")
                hospital_count = await conn.fetchval("SELECT COUNT(*) FROM hospitals")
                wait_time_count = await conn.fetchval("SELECT COUNT(*) FROM wait_times")
                hospital_pages_count = await conn.fetchval("SELECT COUNT(*) FROM hospital_pages")
                logger.info(f"Data verification: Hospitals: {hospital_count}, Wait Times: {wait_time_count}, Hospital Pages: {hospital_pages_count}")

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
    asyncio.run(main())