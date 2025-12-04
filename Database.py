import paramiko
import psycopg2
from knob_config.parse_knob_config import get_knobs
import os
import json
import subprocess
import time

class Database:
    def __init__(self, config, path):
        self.host = config['database_config']['host']
        self.port = int(config['database_config']['port'])
        self.database = config['database_config']['database']
        self.user = config['database_config']['user']
        self.password = config['database_config']['password']
        self.data_path = config['database_config']['data_path']
        self.knobs = get_knobs(path)

    def get_conn(self, max_retries=3):
        print(f"Connecting to PostgreSQL at {self.host}:{self.port} with database {self.database}")
        """Get PostgreSQL connection with retry logic"""
        for attempt in range(max_retries):
            try:
                conn = psycopg2.connect(
                    database=self.database,
                    user=self.user,
                    password=self.password,
                    host=self.host,
                    port=int(self.port),
                    connect_timeout=10  # Add timeout
                )
                if attempt > 0:
                    print(f"Connection successful on attempt {attempt + 1}")
                return conn
                
            except psycopg2.OperationalError as e:
                print(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    print(f"Retrying in 2 seconds... ({attempt + 2}/{max_retries})")
                    time.sleep(2)
            # Don't raise here - let it continue to auto.conf removal
                
            except Exception as e:
                print(f"Unexpected error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    print(f"Retrying in 2 seconds... ({attempt + 2}/{max_retries})")
                    time.sleep(2)
            # Don't raise here - let it continue to auto.conf removal
    
        # If we reach here, all 3 attempts failed
        print(f"All {max_retries} connection attempts failed. Removing auto.conf and trying once more...")
        self.remove_auto_conf()

        # wait for 2 seconds
        time.sleep(2)
        
        # Try one more time after removing auto.conf
        try:
            print("Attempting final connection after removing auto.conf...")
            conn = psycopg2.connect(
                database=self.database,
                user=self.user,
                password=self.password,
                host=self.host,
                port=int(self.port),
                connect_timeout=10
            )
            print("✅ Connection successful after removing auto.conf!")
            return conn
        except Exception as e:
            print(f"❌ Final connection attempt failed even after removing auto.conf: {e}")
            raise Exception(f"Could not establish database connection after {max_retries + 1} attempts and auto.conf removal: {e}")

    def fetch_knob(self):
        conn = self.get_conn()
        knobs = {}
        cursor = conn.cursor()
        for knob in self.knobs:
            sql = "SELECT name, setting FROM pg_settings WHERE name='{}'".format(knob)
            cursor.execute(sql)
            result = cursor.fetchall()
            for s in result:
                knobs[knob] = float(s[1])
        cursor.close()
        conn.close()
        return knobs

    def fetch_knob(self):
        conn = self.get_conn()
        knobs = {}
        cursor = conn.cursor()
        for knob in self.knobs:
            sql = "SELECT name, setting FROM pg_settings WHERE name='{}'".format(knob)
            cursor.execute(sql)
            result = cursor.fetchall()
            for s in result:
                knobs[knob] = float(s[1])
        cursor.close()
        conn.close()
        return knobs
    
    def extract_query_plans(self, workload_queries):
        """
        Extract query plans for a list of SQL queries
        """
        conn = self.get_conn()
        cursor = conn.cursor()
        plans = []
        for i, query in enumerate(workload_queries):
            try:
                print(f"Processing query {i+1}/{len(workload_queries)}")

                # Add EXPLAIN (FORMAT JSON) to get the plan
                explain_query = f"EXPLAIN (FORMAT JSON) {query}"
                cursor.execute(explain_query)
                result = cursor.fetchone()
                
                # Extract the plan from EXPLAIN output
                # EXPLAIN returns [{"Plan": {...}}]
                plan_json = result[0][0]  
                
                # Store in format expected by bin_data.py
                plans.append({
                    "Plan": plan_json,
                    "query": query.strip(),
                    "query_id": i
                })
                
            except Exception as e:
                print(f"Error processing query {i+1}: {e}")
                print(f"Query: {query[:100]}...")  # Show first 100 chars
                continue
        
        cursor.close()
        conn.close()
        
        print(f"Successfully extracted {len(plans)} query plans")
        return plans
        

    def save_workload_plans(self, workload_queries, workload_name):
        # Extract query plans and save them in a JSON file
        plans = self.extract_query_plans(workload_queries)
        
        if plans:
            os.makedirs("query_plans", exist_ok=True)
            # create an output file with workload_name
            output_file = os.path.join("query_plans", f"{workload_name}.json")
            with open(output_file, 'w') as f:
                json.dump(plans, f, indent=2)
            print(f"Saved {len(plans)} query plans to {output_file}")
        else:
            print("No plans to save")
        
        return plans

    def reset_inner_metrics(self):
        """
        Reset internal metrics in PostgreSQL
        """
        conn = self.get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT pg_stat_reset();")
            cursor.execute("SELECT pg_stat_reset_shared('bgwriter');")  # Reset background writer stats
            conn.commit()
            print("Internal metrics reset successfully.")
        except Exception as e:
            print(f"Error resetting internal metrics: {e}")
        finally:
            cursor.close()
            conn.close()
            
    
    def fetch_inner_metrics(self):
        """
        Fetch internal metrics from PostgreSQL as a JSON dictionary
        """
        metrics = {}
        conn = self.get_conn()
        cursor = conn.cursor()

        try:
            # Standard database metrics
            database_stats_sql = """
            SELECT 
                COALESCE(SUM(xact_commit), 0),
                COALESCE(SUM(xact_rollback), 0),
                COALESCE(SUM(blks_read), 0),
                COALESCE(SUM(blks_hit), 0),
                COALESCE(SUM(tup_returned), 0),
                COALESCE(SUM(tup_fetched), 0),
                COALESCE(SUM(tup_inserted), 0),
                COALESCE(SUM(conflicts), 0),
                COALESCE(SUM(tup_updated), 0),
                COALESCE(SUM(tup_deleted), 0)
            FROM pg_stat_database 
            WHERE datname = %s;
            """
        
            cursor.execute(database_stats_sql, (self.database,))
            result = cursor.fetchone()
            
            # Map results to meaningful names
            metrics.update({
                "xact_commit": float(result[0]),
                "xact_rollback": float(result[1]),
                "blks_read": float(result[2]),
                "blks_hit": float(result[3]),
                "tup_returned": float(result[4]),
                "tup_fetched": float(result[5]),
                "tup_inserted": float(result[6]),
                "conflicts": float(result[7]),
                "tup_updated": float(result[8]),
                "tup_deleted": float(result[9])
            })
            
            # Disk read count (accurate)
            disk_read_sql = """
            SELECT 
                COALESCE(SUM(
                    COALESCE(heap_blks_read, 0) +
                    COALESCE(idx_blks_read, 0) +
                    COALESCE(toast_blks_read, 0) +
                    COALESCE(tidx_blks_read, 0)
                ), 0) as disk_read_count
            FROM pg_statio_all_tables;
            """
            
            cursor.execute(disk_read_sql)
            result = cursor.fetchone()
            metrics["disk_read_count"] = float(result[0])
            
            # Disk write count (from background writer)
            bgwriter_sql = """
            SELECT 
                buffers_checkpoint + buffers_clean + buffers_backend as disk_write_count
            FROM pg_stat_bgwriter;
            """
            
            cursor.execute(bgwriter_sql)
            result = cursor.fetchone()
            metrics["disk_write_count"] = float(result[0])
            
            # Calculate bytes from block counts
            metrics["disk_read_bytes"] = metrics["disk_read_count"] * 8192  # 8KB per block
            metrics["disk_write_bytes"] = metrics["disk_write_count"] * 8192  # 8KB per block
            
            print(f"Fetched {len(metrics)} internal metrics")
            print("Internal metrics:", metrics)
            
        except Exception as e:
            print(f"Error fetching internal metrics: {e}")
            # Return empty metrics with default values
            metrics = {
                "xact_commit": 0.0, "xact_rollback": 0.0, "blks_read": 0.0, "blks_hit": 0.0,
                "tup_returned": 0.0, "tup_fetched": 0.0, "tup_inserted": 0.0, "conflicts": 0.0,
                "tup_updated": 0.0, "tup_deleted": 0.0, "disk_read_count": 0.0, "disk_write_count": 0.0,
                "disk_read_bytes": 0.0, "disk_write_bytes": 0.0
            }
        
        finally:
            cursor.close()
            conn.close()
        
        return metrics
    
    def change_knob(self, knobs):
        """
        Apply knob changes without SSH - PostgreSQL only
        """
        print('Change knob function called...')
        flag = True
        conn = self.get_conn()
        cursor = conn.cursor()
        # enable autocommit
        conn.autocommit = True
        try:
            for knob in knobs:
                val = knobs[knob]
                
                # Convert value to appropriate type
                if self.knobs[knob]['type'] == 'integer':
                    val = int(val)
                elif self.knobs[knob]['type'] == 'real':
                    val = float(val)
                
                try:
                    # Use ALTER SYSTEM to change configuration
                    sql = "ALTER SYSTEM SET {} = %s;".format(knob)
                    cursor.execute(sql, (val,))
                    print(f"Set {knob} = {val}")
                    
                except Exception as error:
                    print(f"Error setting {knob} = {val}: {error}")
                    flag = False
            
            # Reload configuration
            
            
            if flag:
                print('Applied knobs successfully!')
                restart_success = self.restart_db()
                if restart_success:
                    print('Database restarted successfully after applying knobs.')
                else:
                    print('Failed to restart database after applying knobs.')
            else:
                print('Some knobs failed to apply')
                
        except Exception as error:
            print(f"Error applying knobs: {error}")
            flag = False
        finally:
            cursor.close()
            conn.close()
        
        return flag
    
    def restart_db(self):
        """
        Simple restart of PostgreSQL 14 using pg_ctlcluster
        """
        try:
            print("Stopping PostgreSQL 14...")
            subprocess.run(['sudo', 'pg_ctlcluster', '14', 'main', 'stop'], 
                        check=True, timeout=30)
            
            time.sleep(2)  # Wait a moment
            
            print("Starting PostgreSQL 14...")
            result = subprocess.run(['sudo', 'pg_ctlcluster', '14', 'main', 'start'], 
                                capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                print("Start failed, removing auto.conf and retrying...")
                # Remove auto.conf file
                self.remove_auto_conf()

                # wait for 1 second
                time.sleep(1)

                # Try starting again
                subprocess.run(['sudo', 'pg_ctlcluster', '14', 'main', 'start'], 
                            check=True, timeout=30)
            
            print("PostgreSQL 14 restarted successfully!")
            return True
            
        except Exception as e:
            print(f"Failed to restart PostgreSQL: {e}")
            return False
        
    def remove_auto_conf(self):
        auto_conf_path = "/var/lib/postgresql/14/main/postgresql.auto.conf"
        try:
            # Use -f flag to force removal (no error if file doesn't exist)
            subprocess.run(['sudo', 'rm', '-f', auto_conf_path], check=True)
            print("Removed postgresql.auto.conf file (if it existed).")
        except subprocess.CalledProcessError as e:
            print(f"Error removing postgresql.auto.conf: {e}")
            raise e

    def get_all_pg_knobs(self):
        """Get all knob details from PostgreSQL"""
        conn = self.get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name, vartype, min_val, max_val, boot_val
            FROM pg_settings
        """)
        
        knob_details = {}
        for name, vartype, min_val, max_val, boot_val in cursor.fetchall():
            knob_details[name] = {
                "max": max_val,
                "min": min_val,
                "type": vartype,
                "default": boot_val
            }
        
        cursor.close()
        conn.close()
        
        # Save to knob_config directory
        filepath = "knob_config/all_pg14_knobs_part2.json"
        with open(filepath, 'w') as f:
            json.dump(knob_details, f, indent=4)
        
        print(f"All PostgreSQL knobs saved to {filepath}")
        return knob_details

    def recreate_from_template(self):
        """Recreate database from template using the copy_db script"""
        try:
            print(f"Recreating database {self.database} from template...")
            result = subprocess.run(['bash', 'scripts/copy_db_from_template.sh', self.database], text=True, timeout=240)
            
            # Print the shell script output to capture it in nohup log
            if result.stdout:
                print(result.stdout, end='')  # end='' to avoid extra newlines
            if result.stderr:
                print(result.stderr, end='')
            
            if result.returncode == 0:
                print(f"Database {self.database} recreated successfully from template")
                time.sleep(2)  # Give PostgreSQL time to settle
                return True
            else:
                print(f"Failed to recreate database: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"Error recreating database from template: {e}")
            return False


