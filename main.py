import time
import numpy as np
import cv2
from selenium import webdriver
import openai
from fetch_data.py import fetch_hospital_data
from config import OPENAI_API_KEY, DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
import psycopg2

openai.api_key = OPENAI_API_KEY

def get_wait_time_from_text(text):
    response = openai.Completion.create(
        model="gpt-4",
        prompt=f"Extract the wait time from the following text:\n{text}\nWait time:",
        max_tokens=10
    )
    return response.choices[0].text.strip()

def main():
    rows = fetch_hospital_data()

    driver = webdriver.Chrome(executable_path='/path/to/chromedriver')

    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    cursor = conn.cursor()

    for row in rows:
        url, hospital_name, hospital_address = row
        driver.get(url)
        time.sleep(5)  # Wait for the page to load completely

        # Take a screenshot
        png = driver.get_screenshot_as_png()

        # Convert the screenshot to OpenCV format
        np_image = np.frombuffer(png, np.uint8)
        img = cv2.imdecode(np_image, cv2.IMREAD_COLOR)

        # Use OpenAI API for image to text
        encoded_img = cv2.imencode('.png', img)[1].tobytes()
        response = openai.Image.create(
            model="gpt-4-vision",
            images=[encoded_img]
        )
        extracted_text = response.choices[0].text

        # Extract wait time from the text using GPT-4
        wait_time = get_wait_time_from_text(extracted_text)

        # Store extracted data into PostgreSQL database
        cursor.execute(
            "INSERT INTO hospital_wait_times (hospital_name, hospital_address, wait_time) VALUES (%s, %s, %s)",
            (hospital_name, hospital_address, wait_time)
        )
        conn.commit()

    driver.quit()
    conn.close()

if __name__ == "__main__":
    main()
