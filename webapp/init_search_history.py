#!/usr/bin/env python3
"""Initialize search_history table in the database."""
from webapp.database import init_db

print("Initializing database tables...")
init_db()
print("Database initialized successfully!")
print("search_history table is now ready to use.")
