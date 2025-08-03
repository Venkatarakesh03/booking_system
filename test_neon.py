import psycopg2
import psycopg2.extras
import os
from contextlib import contextmanager
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Neon Database Connection
DATABASE_URL = os.getenv( 'postgresql://neondb_owner:npg_hYoB4uUiaq1v@ep-morning-meadow-ae8u1jey-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require')

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set. Please check your .env file.")

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

def test_connection():
    """Test the database connection"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Test basic connection
            cur.execute("SELECT version();")
            version = cur.fetchone()
            print("Successfully connected to Neon PostgreSQL!")
            print(f"PostgreSQL version: {version[0]}")
            
            # Test if tables exist
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            tables = cur.fetchall()
            
            if tables:
                print(f"Found {len(tables)} tables:")
                for table in tables:
                    print(f"  - {table[0]}")
            else:
                print("No tables found. Run the main app to create tables.")
            
            cur.close()
            
    except Exception as e:
        print(f"Error connecting to Neon database: {e}")
        print("\nPlease make sure to:")
        print("1. Replace the DATABASE_URL with your actual Neon connection string")
        print("2. Set the DATABASE_URL environment variable")
        print("3. Ensure your Neon database is accessible")

if __name__ == "__main__":
    test_connection()
