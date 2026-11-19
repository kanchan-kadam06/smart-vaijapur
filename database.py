import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():

    try:
        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "smart_vaijapur")
        )

        if connection.is_connected():
            print("Database Connected Successfully!")

        return connection

    except Error as e:
        print("Database Connection Failed:", e)
        return None


if __name__ == "__main__":

    db = get_db_connection()

    if db:
        db.close()
        print("Database Connection Closed.")