from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import psycopg2.extras
import os
from contextlib import contextmanager
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Neon Database Connection
DATABASE_URL = os.getenv('DATABASE_URL')


# Fallback to direct connection string if .env not working
if not DATABASE_URL:
    DATABASE_URL = 'postgresql://neondb_owner:npg_hYoB4uUiaq1v@ep-morning-meadow-ae8u1jey-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
    print("Warning: Using fallback DATABASE_URL. Consider fixing your .env file.")

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

def init_database():
    """Initialize database tables"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        
        # Create users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                address TEXT
            )
        """)
        
        # Create workers table
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
        
        # Create bookings table
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

# Routes
# @app.route('/')
# def index():
#     return render_template('index.html')

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

                    # Insert into Users table
                    cur.execute(
                        "INSERT INTO users (name, email, password, address) VALUES (%s, %s, %s, %s)",
                        (name, email, hashed_password, address)
                    )

                elif role == 'worker':
                    profession = request.form['profession']
                    hourly_charge = request.form['hourlyCharge']
                    worker_city = request.form['workerCity']

                    # Insert into Workers table
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

        return redirect(url_for('login'))  # Redirect to login page after successful signup
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        try:
            with get_db_connection() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                
                # Check users table
                cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                user_data = cur.fetchone()
                
                if user_data:
                    if check_password_hash(user_data['password'], password):
                        session['user_id'] = user_data['id']
                        session['user_type'] = 'user'
                        return redirect(url_for('user_dashboard'))
                
                # Check workers table
                cur.execute("SELECT * FROM workers WHERE email = %s", (email,))
                worker_data = cur.fetchone()
                
                if worker_data:
                    if check_password_hash(worker_data['password'], password):
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

            # ✅ Get the logged-in user's info
            cur.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
            user_data = cur.fetchone()  # ✅ get ONE row

            # ✅ Get the user's bookings with worker info
            cur.execute("""
                SELECT b.*, w.name AS worker_name, w.profession
                FROM bookings b
                JOIN workers w ON b.worker_id = w.id
                WHERE b.user_id = %s
                ORDER BY b.booking_date DESC
            """, (session['user_id'],))
            bookings = cur.fetchall()
            
            # ✅ Get all available workers for booking
            cur.execute("SELECT * FROM workers ORDER BY name")
            workers = cur.fetchall()

            cur.close()

        # ✅ Send user info, bookings, and workers to template
        return render_template('user_dashboard.html', user=user_data, bookings=bookings, workers=workers)

    except Exception as e:
        return f"Dashboard Error: {str(e)}"



@app.route('/worker_dashboard')
def worker_dashboard():
    # Check if worker is logged in (session should store worker_id, not user_id)
    if 'user_id' not in session:  
        return redirect(url_for('login'))  # Redirect to login if not logged in

    try:
        with get_db_connection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Fetch worker details
            cur.execute("SELECT * FROM workers WHERE id = %s", (session['user_id'],))
            worker = cur.fetchone()
            
            if not worker:  # If no worker found
                return "Worker not found", 404

            # Fetch bookings for this worker with user details
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

    # Booking statistics
    total_requests = len(bookings)
    accepted_count = sum(1 for b in bookings if b['status'] == 'Accepted')
    rejected_count = sum(1 for b in bookings if b['status'] == 'Rejected')

    return render_template(
        'worker_dashboard.html',
        worker=worker,  # Pass single worker, not list
        bookings=bookings,
        total_requests=total_requests,
        accepted_count=accepted_count,
        rejected_count=rejected_count
    )

@app.route('/logout')
def logout():
    # Logic to handle logout (e.g., clearing session or cookies)
    session.pop('user_id', None)  # Example to pop the user session
    session.pop('user_type', None)  # Ensure user_type is cleared as well
    return redirect(url_for('login'))  # Redirect to login page after logging out

@app.route('/book_worker', methods=['POST'])
def book_worker():
    try:
        worker_id = request.form['worker_id']
        booking_date = request.form['date']
        booking_time = request.form['time']
        user_id = session['user_id']
        
        # Ensure that required fields are present
        if not worker_id or not booking_date or not booking_time:
            return "Error: Missing required fields", 400

        # Insert the booking into the database
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
        # If a required form key is missing
        return f"Error: Missing form field {e}", 400
    except Exception as e:
        # Handle other exceptions
        return f"An unexpected error occurred: {e}", 500

@app.route('/history')
def history():
    # Check if user is logged in (if 'user_id' is in the session)
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    user_id = session['user_id']
    
    try:
        with get_db_connection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Fetch bookings made by the user with worker details
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
    # Initialize database tables
    try:
        init_database()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Database initialization error: {e}")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
