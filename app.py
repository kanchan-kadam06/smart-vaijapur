import os
from dotenv import load_dotenv

load_dotenv()
from uuid import uuid4

from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from werkzeug.utils import secure_filename
from database import get_db_connection


# =====================================
# FLASK CONFIGURATION
# =====================================

app = Flask(__name__)
app.secret_key = os.getenv("secret_key")

UPLOAD_FOLDER = os.path.join(
    app.root_path, "static", "uploads"
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# =====================================
# HOME
# =====================================

@app.route("/")
def index():
    return render_template("index.html")


# =====================================
# CITIZEN REGISTRATION
# =====================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        full_name = request.form.get("full_name", "").strip()
        mobile = request.form.get("mobile", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not all([full_name, mobile, email, password]):
            flash("Please fill all fields.")
            return render_template("register.html")

        hashed_password = generate_password_hash(password)

        db = get_db_connection()

        if not db:
            flash("Database connection failed.")
            return render_template("register.html")

        cursor = db.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO citizens
                (full_name, mobile, email, password)
                VALUES (%s, %s, %s, %s)
                """,
                (full_name, mobile, email, hashed_password)
            )

            db.commit()

            flash("Registration successful! Please login.")
            return redirect(url_for("login"))

        except Exception as e:
            db.rollback()
            print("Registration Error:", e)
            flash("Registration failed. Email may already exist.")

        finally:
            cursor.close()
            db.close()

    return render_template("register.html")


# =====================================
# CITIZEN LOGIN
# =====================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db_connection()

        if not db:
            flash("Database connection failed.")
            return render_template("login.html")

        cursor = db.cursor(dictionary=True)

        try:
            cursor.execute(
                """
                SELECT citizen_id, full_name, email, password
                FROM citizens
                WHERE LOWER(email)=%s
                """,
                (email,)
            )

            citizen = cursor.fetchone()

            if citizen:

                stored_password = citizen["password"]

                try:
                    password_valid = check_password_hash(
                        stored_password, password
                    )
                except (ValueError, TypeError):
                    password_valid = False

                if not password_valid:
                    password_valid = stored_password == password

                if password_valid:

                    if stored_password == password:
                        new_hash = generate_password_hash(password)

                        cursor.execute(
                            """
                            UPDATE citizens
                            SET password=%s
                            WHERE citizen_id=%s
                            """,
                            (new_hash, citizen["citizen_id"])
                        )

                        db.commit()

                    session.clear()

                    session["citizen_id"] = citizen["citizen_id"]
                    session["citizen_name"] = citizen["full_name"]

                    flash("Login successful!")
                    return redirect(url_for("index"))

            flash("Invalid email or password.")

        except Exception as e:
            db.rollback()
            print("Citizen Login Error:", e)
            flash("Login failed. Please try again.")

        finally:
            cursor.close()
            db.close()

    return render_template("login.html")


# =====================================
# CITIZEN LOGOUT
# =====================================

@app.route("/logout")
def logout():

    session.clear()
    flash("You have logged out successfully.")

    return redirect(url_for("index"))


# =====================================
# ONLINE COMPLAINT WITH ID
# =====================================

@app.route("/complaint", methods=["GET", "POST"])
def complaint():

    if "citizen_id" not in session:
        flash("Please login first.")
        return redirect(url_for("login"))

    if request.method == "POST":

        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        location = request.form.get("location", "").strip()

        photo = request.files.get("photo")
        photo_path = None

        if not all([category, description, location]):
            flash("Please fill all complaint details.")
            return redirect(url_for("complaint"))

        if photo and photo.filename:

            if not allowed_file(photo.filename):
                flash("Only JPG, JPEG and PNG files are allowed.")
                return redirect(url_for("complaint"))

            filename = secure_filename(photo.filename)
            unique_filename = str(uuid4()) + "_" + filename

            photo.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    unique_filename
                )
            )

            photo_path = "uploads/" + unique_filename

        db = get_db_connection()

        if not db:
            flash("Database connection failed.")
            return redirect(url_for("complaint"))

        cursor = db.cursor()

        try:

            cursor.execute(
                """
                INSERT INTO complaints
                (citizen_id, category, description, location, photo)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    session["citizen_id"],
                    category,
                    description,
                    location,
                    photo_path
                )
            )

            complaint_id = cursor.lastrowid

            db.commit()

            session["last_complaint_id"] = complaint_id

            flash(
                f"Complaint submitted successfully! "
                f"Your Complaint ID is {complaint_id}"
            )

            return redirect(url_for("tracking"))

        except Exception as e:
            db.rollback()
            print("Complaint Error:", e)
            flash("Complaint submission failed.")

        finally:
            cursor.close()
            db.close()

    return render_template("complaint.html")


# =====================================
# COMPLAINT TRACKING
# =====================================

@app.route("/tracking", methods=["GET", "POST"])
def tracking():

    if "citizen_id" not in session:
        flash("Please login first.")
        return redirect(url_for("login"))

    complaint_data = None

    if request.method == "POST":

        complaint_id = request.form.get("complaint_id", "").strip()

        if not complaint_id.isdigit():
            flash("Please enter a valid Complaint ID.")
            return render_template(
                "tracking.html", complaint=None
            )

        db = get_db_connection()

        if not db:
            flash("Database connection failed.")
            return render_template(
                "tracking.html", complaint=None
            )

        cursor = db.cursor(dictionary=True)

        try:
            cursor.execute(
                """
                SELECT *
                FROM complaints
                WHERE complaint_id=%s AND citizen_id=%s
                """,
                (complaint_id, session["citizen_id"])
            )

            complaint_data = cursor.fetchone()

            if not complaint_data:
                flash("Complaint not found.")

        except Exception as e:
            print("Tracking Error:", e)
            flash("Unable to track complaint.")

        finally:
            cursor.close()
            db.close()

    return render_template(
        "tracking.html",
        complaint=complaint_data
    )


# =====================================
# ADMIN LOGIN
# =====================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        db = get_db_connection()

        if not db:
            flash("Database connection failed.")
            return render_template("admin_login.html")

        cursor = db.cursor(dictionary=True)

        try:
            cursor.execute(
                "SELECT * FROM admin WHERE email=%s",
                (email,)
            )

            admin_data = cursor.fetchone()

            valid_password = False

            if admin_data:

                stored_password = admin_data["password"]

                try:
                    valid_password = check_password_hash(
                        stored_password, password
                    )
                except (ValueError, TypeError):
                    valid_password = False

                if not valid_password:
                    valid_password = stored_password == password

            if admin_data and valid_password:

                session.clear()
                session["admin_id"] = admin_data["admin_id"]

                flash("Admin login successful!")
                return redirect(url_for("admin"))

            flash("Invalid admin email or password.")

        except Exception as e:
            print("Admin Login Error:", e)
            flash("Admin login failed.")

        finally:
            cursor.close()
            db.close()

    return render_template("admin_login.html")


# =====================================
# ADMIN DASHBOARD
# =====================================

@app.route("/admin")
def admin():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    db = get_db_connection()

    complaints = []

    stats = {
        "total": 0,
        "pending": 0,
        "in_progress": 0,
        "resolved": 0
    }

    if db:
        cursor = db.cursor(dictionary=True)

        try:
            cursor.execute(
                """
                SELECT complaints.*, citizens.full_name,
                citizens.mobile
                FROM complaints
                JOIN citizens
                ON complaints.citizen_id = citizens.citizen_id
                ORDER BY complaints.complaint_id DESC
                """
            )

            complaints = cursor.fetchall()

            cursor.execute(
                "SELECT COUNT(*) AS total FROM complaints"
            )
            stats["total"] = cursor.fetchone()["total"]

            cursor.execute(
                """
                SELECT COUNT(*) AS total FROM complaints
                WHERE status='Pending'
                """
            )
            stats["pending"] = cursor.fetchone()["total"]

            cursor.execute(
                """
                SELECT COUNT(*) AS total FROM complaints
                WHERE status='In Progress'
                """
            )
            stats["in_progress"] = cursor.fetchone()["total"]

            cursor.execute(
                """
                SELECT COUNT(*) AS total FROM complaints
                WHERE status='Resolved'
                """
            )
            stats["resolved"] = cursor.fetchone()["total"]

        except Exception as e:
            print("Admin Dashboard Error:", e)

        finally:
            cursor.close()
            db.close()

    return render_template(
        "admin.html",
        complaints=complaints,
        stats=stats
    )


# =====================================
# UPDATE STATUS + NOTIFICATION
# =====================================

@app.route("/admin/update/<int:complaint_id>", methods=["POST"])
def update_status(complaint_id):

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    new_status = request.form.get("status", "")

    allowed_statuses = [
        "Pending",
        "In Progress",
        "Resolved"
    ]

    if new_status not in allowed_statuses:
        flash("Invalid complaint status.")
        return redirect(url_for("admin"))

    db = get_db_connection()

    if not db:
        flash("Database connection failed.")
        return redirect(url_for("admin"))

    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT citizen_id, status
            FROM complaints
            WHERE complaint_id=%s
            """,
            (complaint_id,)
        )

        complaint_data = cursor.fetchone()

        if complaint_data:

            citizen_id = complaint_data["citizen_id"]
            old_status = complaint_data["status"]

            cursor.execute(
                """
                UPDATE complaints
                SET status=%s
                WHERE complaint_id=%s
                """,
                (new_status, complaint_id)
            )

            if old_status != new_status:

                message = (
                    f"Your complaint #{complaint_id} "
                    f"status has been updated to {new_status}."
                )

                cursor.execute(
                    """
                    INSERT INTO notifications
                    (citizen_id, message, created_at)
                    VALUES (%s, %s, NOW())
                    """,
                    (citizen_id, message)
                )

            db.commit()
            flash("Complaint status updated successfully!")

        else:
            flash("Complaint not found.")

    except Exception as e:
        db.rollback()
        print("Status Update Error:", e)
        flash("Status update failed.")

    finally:
        cursor.close()
        db.close()

    return redirect(url_for("admin"))


# =====================================
# ADMIN LOGOUT
# =====================================

@app.route("/admin/logout")
def admin_logout():

    session.clear()
    flash("Admin logged out successfully.")

    return redirect(url_for("admin_login"))


# =====================================
# CITIZEN FEEDBACK
# =====================================

@app.route("/feedback", methods=["GET", "POST"])
def feedback():

    if "citizen_id" not in session:
        flash("Please login first.")
        return redirect(url_for("login"))

    if request.method == "POST":

        complaint_id = request.form.get("complaint_id", "").strip()
        rating = request.form.get("rating", "")
        feedback_text = request.form.get("feedback_text", "").strip()

        if not all([complaint_id, rating, feedback_text]):
            flash("Please fill all feedback fields.")
            return redirect(url_for("feedback"))

        db = get_db_connection()

        if not db:
            flash("Database connection failed.")
            return redirect(url_for("feedback"))

        cursor = db.cursor()

        try:
            cursor.execute(
                """
                SELECT complaint_id
                FROM complaints
                WHERE complaint_id=%s AND citizen_id=%s
                """,
                (complaint_id, session["citizen_id"])
            )

            complaint_data = cursor.fetchone()

            if complaint_data:

                cursor.execute(
                    """
                    INSERT INTO feedback
                    (citizen_id, complaint_id, feedback_text, rating)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        session["citizen_id"],
                        complaint_id,
                        feedback_text,
                        rating
                    )
                )

                db.commit()
                flash("Feedback submitted successfully!")

            else:
                flash("Invalid complaint ID.")

        except Exception as e:
            db.rollback()
            print("Feedback Error:", e)
            flash("Feedback submission failed.")

        finally:
            cursor.close()
            db.close()

        return redirect(url_for("feedback"))

    return render_template("feedback.html")


# =====================================
# ADMIN VIEW FEEDBACK
# =====================================

@app.route("/admin/feedback")
def admin_feedback():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    db = get_db_connection()
    feedback_list = []

    if db:
        cursor = db.cursor(dictionary=True)

        try:
            cursor.execute(
                """
                SELECT feedback.*, citizens.full_name,
                citizens.mobile, complaints.category
                FROM feedback
                JOIN citizens
                ON feedback.citizen_id = citizens.citizen_id
                JOIN complaints
                ON feedback.complaint_id = complaints.complaint_id
                ORDER BY feedback.feedback_id DESC
                """
            )

            feedback_list = cursor.fetchall()

        except Exception as e:
            print("Admin Feedback Error:", e)

        finally:
            cursor.close()
            db.close()

    return render_template(
        "admin_feedback.html",
        feedback_list=feedback_list
    )


# =====================================
# CITIZEN NOTIFICATIONS
# =====================================

@app.route("/notifications")
def notifications():

    if "citizen_id" not in session:
        flash("Please login first.")
        return redirect(url_for("login"))

    db = get_db_connection()
    notification_list = []

    if not db:
        flash("Database connection failed.")
        return render_template(
            "notifications.html",
            notifications=notification_list
        )

    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT notification_id, citizen_id,
            message, created_at
            FROM notifications
            WHERE citizen_id=%s
            ORDER BY created_at DESC
            """,
            (session["citizen_id"],)
        )

        notification_list = cursor.fetchall()

    except Exception as e:
        print("Notification Error:", e)
        flash("Unable to load notifications.")

    finally:
        cursor.close()
        db.close()

    return render_template(
        "notifications.html",
        notifications=notification_list
    )


# =====================================
# FILE SIZE ERROR
# =====================================

@app.errorhandler(413)
def file_too_large(error):
    flash("Photo size must be less than 5 MB.")
    return redirect(url_for("complaint"))


# =====================================
# RUN APPLICATION
# =====================================

if __name__ == "__main__":
    app.run(debug=True)