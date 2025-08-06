#!/usr/bin/env python3
"""
Simple test to check if Database class works and fetch_inner_metric runs without errors
"""

import os
import sys
sys.path.append('..')
from Database import Database


def main():
    print("Testing Database class and fetch_inner_metric...")
    
    # UPDATE THESE DATABASE CREDENTIALS
    config = {
        'database_config': {
            'host': 'localhost',
            'port': 5432,
            'database': 'benchbase',        # Change to your database name
            'user': 'postgres',            # Change to your username
            'password': '123456',        # Change to your password
            'data_path': '/var/lib/postgresql/data'
        }
    }
    
    # Create minimal knob config file if it doesn't exist
    knob_config_path = "../knob_config/knob_config.json"
    if not os.path.exists(knob_config_path):
        os.makedirs("knob_config", exist_ok=True)
        with open(knob_config_path, "w") as f:
            f.write('{"shared_buffers": {"type": "integer", "min": 128, "max": 1024, "default": 128}}')
    
    try:
        # Create Database instance
        print("Creating Database instance...")
        db = Database(config, knob_config_path)
        print("✓ Database instance created successfully")
        
        # Test database connection
        print("Testing database connection...")
        conn = db.get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT current_database();")
        current_db = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        print(f"✓ Connected to database: {current_db}")
        
        # Test fetch_inner_metric function
        print("Testing fetch_inner_metric()...")
        metrics = db.fetch_inner_metric()
        print(f"✓ fetch_inner_metric() completed successfully!")
        print(f"✓ Returned {len(metrics)} metrics")
        
        # Show the metrics
        print("\nMetrics returned:")
        for i, value in enumerate(metrics):
            print(f"  {i+1}. {value}")
        
        print("\n✓ SUCCESS: Everything works!")
        
    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
