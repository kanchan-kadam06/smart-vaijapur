from database import get_db_connection
from werkzeug.security import generate_password_hash
from getpass import getpass

email = input("Enter Admin Email: ").strip()
password = getpass("Create Admin Password: ")

if not email or len(password) < 8:
    print("Email is required and password must be at least 8 characters.")
else:
    db = get_db_connection()

    if db:
        cursor = db.cursor()

        try:
            hashed_password = generate_password_hash(password)

            query = """
            INSERT INTO admin (email, password)
            VALUES (%s, %s)
            """

            cursor.execute(query, (email, hashed_password))
            db.commit()

            print("Admin Account Created Successfully!")

        except Exception as e:
            db.rollback()
            print("Admin account could not be created:", e)

        finally:
            cursor.close()
            db.close()