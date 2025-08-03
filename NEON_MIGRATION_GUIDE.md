# Neon Database Migration Guide

## Overview
Your Worker Booking System has been successfully migrated from Supabase to Neon PostgreSQL database.

## What Changed

### 1. Database Connection
- **Before**: Supabase client with API keys
- **After**: Direct PostgreSQL connection using psycopg2

### 2. Dependencies
- **Removed**: `supabase` package
- **Added**: `psycopg2-binary` package

### 3. Query Structure
- **Before**: Supabase ORM-style queries (`supabase.table('users').select('*')`)
- **After**: Raw SQL queries with parameterized statements

## Setup Instructions

### Step 1: Create Neon Database
1. Go to [Neon Console](https://console.neon.tech/)
2. Create a new project or use existing one
3. Note down your connection details

### Step 2: Configure Database Connection
1. Copy `.env.example` to `.env`
2. Replace the `DATABASE_URL` with your actual Neon connection string
3. Format: `postgresql://username:password@endpoint/database?sslmode=require`

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Test Connection
```bash
python test_neon.py
```

### Step 5: Run Application
```bash
python app.py
```

## Database Schema

The application will automatically create these tables:

### Users Table
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    address TEXT
);
```

### Workers Table
```sql
CREATE TABLE workers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    profession VARCHAR(255),
    hourly_charge DECIMAL(10,2),
    city VARCHAR(255)
);
```

### Bookings Table
```sql
CREATE TABLE bookings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    worker_id INTEGER REFERENCES workers(id),
    booking_date DATE,
    booking_time TIME,
    status VARCHAR(50) DEFAULT 'Pending'
);
```

## Key Improvements

1. **Better Error Handling**: Added try-catch blocks for database operations
2. **Connection Management**: Using context managers for proper connection handling
3. **SQL Injection Protection**: Using parameterized queries
4. **Join Queries**: Optimized queries using SQL JOINs instead of multiple requests
5. **Environment Variables**: Database credentials stored in environment variables

## Migration Benefits

- **Performance**: Direct PostgreSQL connection is faster than API calls
- **Cost**: No API rate limits or usage costs
- **Control**: Full control over database schema and queries
- **Scalability**: Better performance for complex queries
- **Security**: Environment-based configuration

## Troubleshooting

### Connection Issues
- Verify your Neon connection string is correct
- Check if your IP is whitelisted in Neon console
- Ensure SSL mode is enabled

### Table Creation Issues
- The app automatically creates tables on first run
- If tables don't exist, check database permissions

### Migration from Existing Data
If you have existing data in Supabase, you'll need to:
1. Export data from Supabase
2. Import data into Neon using SQL scripts
3. Ensure data types match the new schema

## Support
For issues with Neon database, visit [Neon Documentation](https://neon.tech/docs)
