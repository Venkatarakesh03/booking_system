from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import psycopg2.extras
import os
from contextlib import contextmanager
from dotenv import load_dotenv
from urllib.parse import urlparse, parse_qs

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://username:password@ep-example.us-east-2.aws.neon.tech/neondb?sslmode=require"
)

if not DATABASE_URL:
    DATABASE_URL = "postgresql://neondb_owner:npg_hYoB4uUiaq1v@ep-morning-meadow-ae8u1jey-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"
    print("⚠ Warning: Using fallback DATABASE_URL. Consider fixing your .env file.")

# --- Database Connection Manager ---
@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = None
    try:
        # Parse the database URL properly
        url = urlparse(DATABASE_URL)
        params = parse_qs(url.query)

        conn = psycopg2.connect(
            dbname=url.path[1:],  # remove leading "/"
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port or 5432,
            sslmode=params.get("sslmode", ["require"])[0]
        )
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

# --- Initialize Database ---
def init_database():
    """Initialize database tables"""
    with get_db_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                address TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workers (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                profession VARCHAR(255),
                hourly_charge DECIMAL(10,2),
                city VARCHAR(255)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                worker_id INTEGER REFERENCES workers(id),
                booking_date DATE,
                booking_time TIME,
                status VARCHAR(50) DEFAULT 'Pending'
            )
        """)
        conn.commit()
        cur.close()

@app.route('/')
def home():
    try:
        return render_template('index.html')
    except Exception as e:
        print(f"Error in home route: {str(e)}")
        return f"Template error: {str(e)}"

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        role = request.form['role']
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        try:
            with get_db_connection() as conn:
                cur = conn.cursor()

                if role == 'user':
                    door_no = request.form['doorNo']
                    street = request.form['street']
                    city = request.form['city']
                    address = f"{door_no}, {street}, {city}"
                    cur.execute(
                        "INSERT INTO users (name, email, password, address) VALUES (%s, %s, %s, %s)",
                        (name, email, hashed_password, address)
                    )

                elif role == 'worker':
                    profession = request.form['profession']
                    hourly_charge = request.form['hourlyCharge']
                    worker_city = request.form['workerCity']
                    cur.execute(
                        "INSERT INTO workers (name, email, password, profession, hourly_charge, city) VALUES (%s, %s, %s, %s, %s, %s)",
                        (name, email, hashed_password, profession, hourly_charge, worker_city)
                    )

                conn.commit()
                cur.close()

        except psycopg2.IntegrityError:
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
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

                cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                user_data = cur.fetchone()

                if user_data and check_password_hash(user_data['password'], password):
                    session['user_id'] = user_data['id']
                    session['user_type'] = 'user'
                    return redirect(url_for('user_dashboard'))

                cur.execute("SELECT * FROM workers WHERE email = %s", (email,))
                worker_data = cur.fetchone()

                if worker_data and check_password_hash(worker_data['password'], password):
                    session['user_id'] = worker_data['id']
                    session['user_type'] = 'worker'
                    return redirect(url_for('worker_dashboard'))

                cur.close()

        except Exception as e:
            return f"An error occurred: {str(e)}"

        return "Invalid credentials, please try again."
    return render_template('login.html')

@app.route('/user_dashboard', methods=['GET', 'POST'])
def user_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        with get_db_connection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
            user_data = cur.fetchone()

            cur.execute("""
                SELECT b.*, w.name AS worker_name, w.profession
                FROM bookings b
                JOIN workers w ON b.worker_id = w.id
                WHERE b.user_id = %s
                ORDER BY b.booking_date DESC
            """, (session['user_id'],))
            bookings = cur.fetchall()

            cur.execute("SELECT * FROM workers ORDER BY name")
            workers = cur.fetchall()
            cur.close()

        return render_template('user_dashboard.html', user=user_data, bookings=bookings, workers=workers)
    except Exception as e:
        return f"Dashboard Error: {str(e)}"

@app.route('/worker_dashboard')
def worker_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        with get_db_connection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM workers WHERE id = %s", (session['user_id'],))
            worker = cur.fetchone()

            if not worker:
                return "Worker not found", 404

            cur.execute("""
                SELECT b.*, u.name as user_name, u.address as user_address 
                FROM bookings b 
                JOIN users u ON b.user_id = u.id 
                WHERE b.worker_id = %s
            """, (session['user_id'],))
            bookings = cur.fetchall()
            cur.close()

    except Exception as e:
        return f"An error occurred: {str(e)}"

    total_requests = len(bookings)
    accepted_count = sum(1 for b in bookings if b['status'] == 'Accepted')
    rejected_count = sum(1 for b in bookings if b['status'] == 'Rejected')

    return render_template('worker_dashboard.html', worker=worker, bookings=bookings, total_requests=total_requests,
                           accepted_count=accepted_count, rejected_count=rejected_count)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_type', None)
    return redirect(url_for('login'))

@app.route('/book_worker', methods=['POST'])
def book_worker():
    try:
        worker_id = request.form['worker_id']
        booking_date = request.form['date']
        booking_time = request.form['time']
        user_id = session['user_id']

        if not worker_id or not booking_date or not booking_time:
            return "Error: Missing required fields", 400

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO bookings (user_id, worker_id, booking_date, booking_time, status) VALUES (%s, %s, %s, %s, %s)",
                (user_id, worker_id, booking_date, booking_time, 'Pending')
            )
            conn.commit()
            cur.close()

        return redirect(url_for('user_dashboard'))
    except KeyError as e:
        return f"Error: Missing form field {e}", 400
    except Exception as e:
        return f"An unexpected error occurred: {e}", 500

@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    try:
        with get_db_connection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("""
                SELECT b.*, w.name as worker_name, w.city as worker_city, w.hourly_charge 
                FROM bookings b 
                JOIN workers w ON b.worker_id = w.id 
                WHERE b.user_id = %s
            """, (user_id,))
            bookings = cur.fetchall()
            cur.close()
    except Exception as e:
        return f"An error occurred: {str(e)}"

    return render_template('history.html', bookings=bookings)

@app.route('/accept_booking/<int:booking_id>', methods=['POST'])
def accept_booking(booking_id):
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE bookings SET status = %s WHERE id = %s", ('Accepted', booking_id))
            conn.commit()
            cur.close()
    except Exception as e:
        return f"An error occurred: {str(e)}"
    return redirect(url_for('worker_dashboard'))

@app.route('/reject_booking/<int:booking_id>', methods=['POST'])
def reject_booking(booking_id):
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE bookings SET status = %s WHERE id = %s", ('Rejected', booking_id))
            conn.commit()
            cur.close()
    except Exception as e:
        return f"An error occurred: {str(e)}"
    return redirect(url_for('worker_dashboard'))

if __name__ == '__main__':
    try:
        init_database()
        print("✅ Database initialized successfully!")
    except Exception as e:
        print(f"Database initialization error: {e}")

    app.run(host='0.0.0.0', port=5000, debug=True)
