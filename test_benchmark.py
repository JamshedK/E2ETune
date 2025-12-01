#!/usr/bin/env python3

import json
import subprocess
import time
from config.parse_config import parse_args
from Database import Database
import os

def run_benchmark_script():
    """Run the benchmark script and return throughput"""
    # Hardcoded config - adjust as needed
    workload = "sample_twitter_config0.xml"
    benchmark = "twitter"
    timestamp = int(time.time())
    output_dir = os.path.abspath(f"./tmp/test_results_{timestamp}")  # Use absolute path
    
    # Create output directory with proper permissions
    os.makedirs(output_dir, exist_ok=True)
    os.chmod(output_dir, 0o755)  # Set proper permissions
    
    # Run benchmark
    cmd = [
        'bash', 'run_benchmark.sh', 
        benchmark, 
        str(timestamp), 
        output_dir, 
        output_dir,
        workload
    ]
    
    print(f"Running: {' '.join(cmd)}")
    print(f"Output directory: {output_dir}")  # Debug info
    
    # Make sure we're in the right directory when running the script
    result = subprocess.run(cmd, capture_output=True, text=True, cwd='.')
    
    if result.returncode != 0:
        print(f"Benchmark failed: {result.stderr}")
        print(f"Stdout: {result.stdout}")  # Also print stdout for debugging
        return 0.0
    
    # Parse throughput from summary.json (BenchBase creates files like twitter_2025-11-21_02-23-45.summary.json)
    try:
        import glob
        summary_files = glob.glob(f"{output_dir}/*.summary.json")
        if not summary_files:
            print(f"No summary.json files found in {output_dir}")
            return 0.0
        
        summary_file = summary_files[0]  # Take the first (should be only one)
        print(f"Reading summary from: {summary_file}")
        
        with open(summary_file, 'r') as f:
            data = json.load(f)
        throughput = data["Throughput (requests/second)"]
        print(f"Throughput: {throughput}")
        return throughput
    except Exception as e:
        print(f"Failed to parse results: {e}")
        # List files in output directory for debugging
        try:
            files = os.listdir(output_dir)
            print(f"Files in {output_dir}: {files}")
        except:
            pass
        return 0.0

def main():
    print("=== Database Benchmark Test ===")
    
    # Load config
    args = parse_args("config/config.ini")
    db = Database(config=args, path=args['tuning_config']['knob_config'])
    
    # Reset the db with recover_script 
    print("Resetting database to default state...")
    subprocess.run(['bash', 'scripts/recover_postgres.sh'])

    # Test 1: Default configuration
    print("\n--- Test 1: Default Configuration ---")
    default_throughput = run_benchmark_script()

    # Recreate database to reset state
    print("Recreating database to reset state...")
    # run copy_db_from_template.sh script
    subprocess.run(['bash', 'scripts/copy_db_from_template.sh'])

    
    # Test 2: Apply custom configuration
    print("\n--- Test 2: Custom Configuration ---")
    
    # Hardcoded test config - adjust these values as needed
    test_config = {
      "autovacuum_analyze_scale_factor": 34.5752265304327,
      "autovacuum_analyze_threshold": 221734212,
      "autovacuum_max_workers": 137,
      "autovacuum_naptime": 2014535,
      "autovacuum_vacuum_cost_delay": 86,
      "autovacuum_vacuum_cost_limit": 2440,
      "autovacuum_vacuum_scale_factor": 63.13391551375389,
      "autovacuum_vacuum_threshold": 549732732,
      "backend_flush_after": 35,
      "bgwriter_delay": 1280,
      "bgwriter_flush_after": 213,
      "bgwriter_lru_maxpages": 698,
      "bgwriter_lru_multiplier": 9,
      "checkpoint_completion_target": 0.20311132818460464,
      "checkpoint_flush_after": 233,
      "checkpoint_timeout": 154,
      "commit_delay": 85778,
      "commit_siblings": 626,
      "cursor_tuple_fraction": 0.5486789308488369,
      "deadlock_timeout": 288268658,
      "default_statistics_target": 2087,
      "effective_cache_size": 1026516310,
      "effective_io_concurrency": 173,
      "from_collapse_limit": 1255906656,
      "geqo_effort": 4,
      "geqo_generations": 983228638,
      "geqo_pool_size": 563748478,
      "geqo_seed": 0.5149009339511395,
      "geqo_threshold": 1900724310,
      "join_collapse_limit": 177235542,
      "maintenance_work_mem": 1893545695,
      "max_connections": 2879,
      "max_wal_senders": 44,
      "shared_buffers": 3737568,
      "temp_buffers": 172125454,
      "temp_file_limit": 1082288005,
      "vacuum_cost_delay": 7,
      "vacuum_cost_limit": 8532,
      "vacuum_cost_page_dirty": 9824,
      "vacuum_cost_page_hit": 5570,
      "vacuum_cost_page_miss": 8752,
      "wal_buffers": 4368,
      "wal_writer_delay": 7964,
      "work_mem": 1295626727
    }
    
    print(f"Applying config: {test_config}")
    success = db.change_knob(test_config)
    
    if success:
        print("Configuration applied, waiting 5 seconds...")
        time.sleep(5)
        custom_throughput = run_benchmark_script()
        
        # Results
        print("\n=== RESULTS ===")
        print(f"Default throughput:  {default_throughput:.2f}")
        print(f"Custom throughput:   {custom_throughput:.2f}")
        improvement = ((custom_throughput - default_throughput) / default_throughput) * 100
        print(f"Improvement:         {improvement:.2f}%")
    else:
        print("Failed to apply custom configuration")

if __name__ == "__main__":
    main()
