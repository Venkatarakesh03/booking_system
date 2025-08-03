from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import os
from contextlib import contextmanager
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Database URL (SQLAlchemy + pg8000)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+pg8000://username:password@ep-example.us-east-2.aws.neon.tech/neondb?sslmode=require"
)

# Create database engine
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

@contextmanager
def get_db_connection():
    """Database connection context manager using SQLAlchemy."""
    connection = engine.connect()
    try:
        yield connection
    finally:
        connection.close()

def init_database():
    """Initialize database tables if they don't exist."""
    with get_db_connection() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                address TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS workers (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                profession VARCHAR(255),
                hourly_charge DECIMAL(10,2),
                city VARCHAR(255)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS bookings (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                worker_id INTEGER REFERENCES workers(id),
                booking_date DATE,
                booking_time TIME,
                status VARCHAR(50) DEFAULT 'Pending'
            )
        """))
        conn.commit()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        role = request.form['role']
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        try:
            with get_db_connection() as conn:
                if role == 'user':
                    address = f"{request.form['doorNo']}, {request.form['street']}, {request.form['city']}"
                    conn.execute(text(
                        "INSERT INTO users (name, email, password, address) VALUES (:name, :email, :password, :address)"
                    ), {"name": name, "email": email, "password": password, "address": address})

                elif role == 'worker':
                    conn.execute(text(
                        "INSERT INTO workers (name, email, password, profession, hourly_charge, city) "
                        "VALUES (:name, :email, :password, :profession, :hourly_charge, :city)"
                    ), {
                        "name": name,
                        "email": email,
                        "password": password,
                        "profession": request.form['profession'],
                        "hourly_charge": request.form['hourlyCharge'],
                        "city": request.form['workerCity']
                    })

                conn.commit()
        except IntegrityError:
            return "Email already exists. Please use a different email."
        except Exception as e:
            return f"An error occurred: {str(e)}"

        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            with get_db_connection() as conn:
                user = conn.execute(text("SELECT * FROM users WHERE email = :email"), {"email": email}).mappings().first()
                if user and check_password_hash(user['password'], password):
                    session['user_id'] = user['id']
                    session['user_type'] = 'user'
                    return redirect(url_for('user_dashboard'))

                worker = conn.execute(text("SELECT * FROM workers WHERE email = :email"), {"email": email}).mappings().first()
                if worker and check_password_hash(worker['password'], password):
                    session['user_id'] = worker['id']
                    session['user_type'] = 'worker'
                    return redirect(url_for('worker_dashboard'))
        except Exception as e:
            return f"An error occurred: {str(e)}"

        return "Invalid credentials, please try again."
    return render_template('login.html')

@app.route('/user_dashboard')
def user_dashboard():
    if 'user_id' not in session or session.get('user_type') != 'user':
        return redirect(url_for('login'))

    with get_db_connection() as conn:
        user = conn.execute(text("SELECT * FROM users WHERE id = :id"), {"id": session['user_id']}).mappings().first()
        bookings = conn.execute(text("""
            SELECT b.*, w.name AS worker_name, w.profession 
            FROM bookings b 
            JOIN workers w ON b.worker_id = w.id 
            WHERE b.user_id = :id
            ORDER BY b.booking_date DESC
        """), {"id": session['user_id']}).mappings().all()
        workers = conn.execute(text("SELECT * FROM workers ORDER BY name")).mappings().all()

    return render_template('user_dashboard.html', user=user, bookings=bookings, workers=workers)

@app.route('/worker_dashboard')
def worker_dashboard():
    if 'user_id' not in session or session.get('user_type') != 'worker':
        return redirect(url_for('login'))

    with get_db_connection() as conn:
        worker = conn.execute(text("SELECT * FROM workers WHERE id = :id"), {"id": session['user_id']}).mappings().first()
        bookings = conn.execute(text("""
            SELECT b.*, u.name AS user_name, u.address AS user_address
            FROM bookings b 
            JOIN users u ON b.user_id = u.id 
            WHERE b.worker_id = :id
        """), {"id": session['user_id']}).mappings().all()

    total_requests = len(bookings)
    accepted_count = sum(1 for b in bookings if b['status'] == 'Accepted')
    rejected_count = sum(1 for b in bookings if b['status'] == 'Rejected')

    return render_template('worker_dashboard.html', worker=worker, bookings=bookings,
                           total_requests=total_requests, accepted_count=accepted_count, rejected_count=rejected_count)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/book_worker', methods=['POST'])
def book_worker():
    worker_id = request.form['worker_id']
    booking_date = request.form['date']
    booking_time = request.form['time']
    user_id = session['user_id']

    with get_db_connection() as conn:
        conn.execute(text(
            "INSERT INTO bookings (user_id, worker_id, booking_date, booking_time, status) "
            "VALUES (:user_id, :worker_id, :booking_date, :booking_time, 'Pending')"
        ), {"user_id": user_id, "worker_id": worker_id, "booking_date": booking_date, "booking_time": booking_time})
        conn.commit()

    return redirect(url_for('user_dashboard'))

@app.route('/accept_booking/<int:booking_id>', methods=['POST'])
def accept_booking(booking_id):
    with get_db_connection() as conn:
        conn.execute(text("UPDATE bookings SET status = 'Accepted' WHERE id = :id"), {"id": booking_id})
        conn.commit()
    return redirect(url_for('worker_dashboard'))

@app.route('/reject_booking/<int:booking_id>', methods=['POST'])
def reject_booking(booking_id):
    with get_db_connection() as conn:
        conn.execute(text("UPDATE bookings SET status = 'Rejected' WHERE id = :id"), {"id": booking_id})
        conn.commit()
    return redirect(url_for('worker_dashboard'))

if __name__ == '__main__':
    init_database()
    app.run(host='0.0.0.0', port=5000, debug=True)
