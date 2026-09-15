#!/usr/bin/env python3
import os
import sqlite3
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from easyprent_accounting.db import initialize_database
from tests.fixtures.demo_data import seed_demo_data

def main():
    if len(sys.argv) != 2:
        print("Usage: scripts/seed_demo_data.py <database_path>")
        sys.exit(1)
    
    db_path = Path(sys.argv[1])
    if db_path.exists():
        print(f"Error: Database {db_path} already exists.")
        sys.exit(1)
        
    print(f"Initializing database at {db_path}...")
    initialize_database(db_path)
    
    print("Seeding demo data...")
    connection = sqlite3.connect(db_path)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        seed_demo_data(connection)
        connection.commit()
    finally:
        connection.close()
        
    print("Done.")

if __name__ == "__main__":
    main()
