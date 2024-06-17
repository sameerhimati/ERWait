import time
import numpy as np
import cv2
import base64
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from fetch_data import fetch_hospital_data
from config import OPENAI_API_KEY, DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
import psycopg2
from logger_setup import logger
from dotenv import load_dotenv
import os

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
                    "You are an assistant that extracts hospital names, addresses, and wait times from images. "
                    "Your output should be in the following format: "
                    "Hospital Name: <hospital_name>, Address: <hospital_address>, Wait Time: <wait_time>. "
                    f"This page belongs to the hospital network {network_name}, and you need to extract information for {hospital_num} hospitals. "
                    "If you don't find an address, please leave it blank. Same with any other information."
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

def parse_extracted_data(extracted_data):
    wait_times = []

    # Check if extracted_data is a list or string and handle accordingly
    if isinstance(extracted_data, list):
        extracted_data = '\n'.join(map(str, extracted_data))

    for line in extracted_data.split('\n'):
        if line.strip():
            try:
                parts = line.split(',', 2)
                hospital_name = parts[0].split("Hospital Name:")[-1].strip()
                hospital_address = parts[1].split("Address:")[-1].strip() if len(parts) > 2 else ""
                wait_time = parts[-1].split("Wait Time:")[-1].strip()
                wait_times.append((hospital_name, hospital_address, wait_time))
            except ValueError as e:
                logger.error("Error parsing line: %s; error: %s", line, e)
    return wait_times

def capture_full_page_screenshot(driver):
    # Get the total height of the page
    total_height = driver.execute_script("return document.body.scrollHeight")
    viewport_height = driver.execute_script("return window.innerHeight")
    stitched_image = None

    for y in range(0, total_height, viewport_height):
        driver.execute_script(f"window.scrollTo(0, {y});")
        time.sleep(1)  # Wait for the scroll action to complete
        screenshot = driver.get_screenshot_as_png()
        np_image = np.frombuffer(screenshot, np.uint8)
        img = cv2.imdecode(np_image, cv2.IMREAD_COLOR)

        if stitched_image is None:
            stitched_image = img
        else:
            stitched_image = np.vstack((stitched_image, img))

    return stitched_image

def main():
    rows = fetch_hospital_data()

    try:
        driver = webdriver.Chrome() # executable_path=os.getenv('CHROMEDRIVER_PATH')
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

        for row in rows:
            url, network_name, hospital_num = row
            try:
                driver.get(url)
                time.sleep(5)  # Wait for the page to load completely

                # Capture the full-page screenshot
                img = capture_full_page_screenshot(driver)
                logger.debug(f"Captured full-page screenshot for URL: {url}")

                # Encode the image to base64
                base64_image = encode_image(img)

                # Extract wait times using OpenAI API
                extracted_data = get_wait_times_from_image(OPENAI_API_KEY, base64_image, network_name, hospital_num, detail='high')

                wait_times = parse_extracted_data(extracted_data)

                if not wait_times:
                    logger.error("No wait times extracted for URL: %s", url)
                    continue

                # Store extracted data into PostgreSQL database
                for hospital_name, hospital_address, wait_time in wait_times:
                    cursor.execute(
                        "INSERT INTO hospital_wait_times (hospital_name, hospital_address, wait_time) VALUES (%s, %s, %s)",
                        (hospital_name, hospital_address, wait_time)
                    )
                    conn.commit()
                logger.info(f"Stored wait times for URL: {url}")

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
