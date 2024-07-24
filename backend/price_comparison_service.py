import psycopg2
from helpers.config import DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT

def get_price_comparison(zip_code, treatment):
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cursor = conn.cursor()

        # This is a placeholder query. You'll need to adjust it based on your actual database schema
        cursor.execute("""
            SELECT facility_name, price
            FROM treatment_prices
            WHERE zip_code = %s AND treatment_name ILIKE %s
            ORDER BY price ASC
            LIMIT 5
        """, (zip_code, f"%{treatment}%"))

        results = cursor.fetchall()
        conn.close()

        return [{"facilityName": row[0], "price": row[1]} for row in results]
    except Exception as e:
        print(f"Error in price comparison service: {str(e)}")
        return []

# You can add more functions here for additional price comparison features or data processing