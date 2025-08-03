# api/index.py
from app import app as application

# Vercel expects the variable "application" to be the entry point.
# This simply imports your Flask "app" from app.py.
