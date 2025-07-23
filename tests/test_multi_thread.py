#!/usr/bin/env python3
import os
import sys
sys.path.append('..')
from multi_thread import multi_thread, generate_random_string

def main():
    # Create test database configuration
    class TestDB:
        def __init__(self):
            self.host = "localhost"
            self.port = 5432
            self.database = "benchbase"      
            self.user = "postgres"          
            self.password = "123456"     
    
    # Create test workload file if it doesn't exist
    workload_path = "../olap_workloads/tpch_1.wg"
    
    # Create database instance
    db = TestDB()
    
    # Create logs directory
    os.makedirs("test_logs", exist_ok=True)
    log_path = f"test_logs/test_run_{generate_random_string()}.log"
    
    # Create and run multi_thread instance
    print("Starting multi-thread database test...")
    print(f"Workload file: {workload_path}")
    print(f"Log file: {log_path}")
    
    try:
        # Initialize multi_thread
        mt = multi_thread(
            db=db,
            workload_path=workload_path,
            thread_num=2,
            log_path=log_path
        )
        
        # Prepare data
        print("Preparing workload data...")
        mt.data_pre()
        
        # Run the workload
        print(f"Running workload with {mt.thread_num} threads...")
        results = mt.run()
        
        print("\n=== Test Results ===")
        print(f"Performance metrics: {results}")
        print(f"Check log file for details: {log_path}")
        
        # Show log contents
        if os.path.exists(log_path):
            print("\n=== Log File Contents ===")
            with open(log_path, 'r') as f:
                print(f.read())
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
