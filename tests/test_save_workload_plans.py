#!/usr/bin/env python3
"""
Test file for Database.save_workload_plans method - tests extracting and saving query plans
"""

import os
import sys
import re
sys.path.append('..')
from Database import Database


def main():
    print("Testing Database.save_workload_plans method...")
    
    # UPDATE THESE DATABASE CREDENTIALS
    config = {
        'database_config': {
            'host': 'localhost',
            'port': 5432,
            'database': 'benchbase',        
            'user': 'postgres',            
            'password': '123456',        
            'data_path': '/var/lib/postgresql/data'
        }
    }
    
    # Create minimal knob config file if it doesn't exist
    knob_config_path = "../knob_config/knob_config.json"
    
    # Set workload path
    workload_path = "../olap_workloads/tpch_1.wg" 
    
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
        
        # Read and parse workload file
        print(f"Reading workload file: {workload_path}")
        if not os.path.exists(workload_path):
            print(f"✗ ERROR: Workload file {workload_path} does not exist!")
            return
        
        with open(workload_path, 'r') as f:
            wg_file = f.read()
        
        # Split queries similar to multi_thread.py
        sql_list = re.split(r'[;\n]+', wg_file)
        for i, it in enumerate(sql_list):
            sql_list[i] += ";"
        
        # Remove empty last element if it exists
        if sql_list[-1] == ";":
            sql_list = sql_list[0:-1]
        
        # Limit to first few queries for testing
        if len(sql_list) > 5:
            sql_list = sql_list[:5]
            print(f"Limited to first 5 queries for testing")
        
        print(f"✓ Found {len(sql_list)} queries in workload file")
        
        # Test save_workload_plans function
        print("Testing save_workload_plans()...")
        workload_name = "tpch"
        plans = db.save_workload_plans(sql_list, workload_name)
        
        print(f"✓ save_workload_plans() completed successfully!")
        print(f"✓ Extracted and saved {len(plans)} query plans")
        
        # Check if the output file was created
        output_file = os.path.join("../query_plans", workload_name)
        if os.path.exists(output_file):
            print(f"✓ Query plans saved to: {output_file}")
            
            # Show file size
            file_size = os.path.getsize(output_file)
            print(f"✓ Output file size: {file_size} bytes")
        else:
            print(f"✗ Output file not found: {output_file}")
        
        print("\n✓ SUCCESS: save_workload_plans test completed!")
        
    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
