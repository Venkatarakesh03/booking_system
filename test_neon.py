import psycopg2
import psycopg2.extras
import os
from contextlib import contextmanager
from dotenv import load_dotenv
import urllib.parse as urlparse

# Load environment variables from .env file
load_dotenv()

# Get Neon Database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

# Fallback if environment variable is missing
if not DATABASE_URL:
    DATABASE_URL = "postgresql://neondb_owner:npg_hYoB4uUiaq1v@ep-morning-meadow-ae8u1jey-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"
    print("⚠ Warning: DATABASE_URL not found in .env. Using fallback connection string.")

# Parse the URL to remove unsupported parameters (like channel_binding)
urlparse.uses_netloc.append("postgres")
url = urlparse.urlparse(DATABASE_URL)

query_params = dict(urlparse.parse_qsl(url.query))
query_params.pop("channel_binding", None)  # ❌ Remove unsupported param

# Rebuild connection params for psycopg2
CONNECTION_PARAMS = {
    "database": url.path[1:],
    "user": url.username,
    "password": url.password,
    "host": url.hostname,
    "port": url.port,
    "sslmode": query_params.get("sslmode", "require")
}

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = None
    try:
        conn = psycopg2.connect(**CONNECTION_PARAMS)
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

            # Test connection
            cur.execute("SELECT version();")
            version = cur.fetchone()
            print("✅ Successfully connected to Neon PostgreSQL!")
            print(f"PostgreSQL version: {version[0]}")

            # Check existing tables
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            tables = cur.fetchall()

            if tables:
                print(f"📋 Found {len(tables)} tables:")
                for table in tables:
                    print(f"  - {table[0]}")
            else:
                print("⚠ No tables found. Run the main app to create tables.")

            cur.close()

    except Exception as e:
        print(f"❌ Error connecting to Neon database: {e}")
        print("\nPlease check:")
        print("1. DATABASE_URL in your .env file")
        print("2. Neon database credentials")
        print("3. Network/firewall settings for Neon connection")

if __name__ == "__main__":
    test_connection()
