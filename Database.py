import paramiko
import psycopg2
from knob_config.parse_knob_config import get_knobs
import os
import json

class Database:
    def __init__(self, config, path):
        self.host = config['database_config']['host']
        self.port = int(config['database_config']['port'])
        self.database = config['database_config']['database']
        self.user = config['database_config']['user']
        self.password = config['database_config']['password']
        self.data_path = config['database_config']['data_path']
        self.knobs = get_knobs(path)

    def get_conn(self):
        conn = psycopg2.connect(database=self.database,
                                user=self.user,
                                password=self.password,
                                host=self.host,
                                port=int(self.port))
        return conn

    def get_ssh(self, config):
        if self.ssh is not None:
            return self.ssh
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(hostname=config['ssh_config']['host'],
                         port=int(config['ssh_config']['port']),
                         username=config['ssh_config']['user'],
                         password=config['ssh_config']['password']
                         )
        print("connect to the database host...")

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
    
    def get_conn(self):
        return psycopg2.connect(
            database=self.database,
            user=self.user,
            password=self.password,
            host=self.host,
            port=self.port
        )

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

    def fetch_inner_metric(self):
        state_list = []
        conn = self.get_conn()
        cursor = conn.cursor()

        # 1: Cache hit rate
        cache_hit_rate_sql = "select blks_hit / (blks_read + blks_hit + 0.001) " \
                             "from pg_stat_database " \
                             "where datname = '{}';".format("benchbase")

        # 2: Concurrent user count
        concurrent_users = """
        SELECT
            count(DISTINCT usename)
        AS
            concurrent_users
        FROM
            pg_stat_activity
        WHERE
            state = 'active';
        """

        # 3: Lock wait count
        lock = """
        SELECT
            count(*) AS lock_wait_count
        FROM
            pg_stat_activity
        WHERE waiting = true;
        """

        # 4: Error rate
        error_rate = """
        SELECT
            (sum(xact_rollback) + sum(conflicts) + sum(deadlocks)) / (sum(xact_commit) + sum(xact_rollback) + sum(conflicts) + sum(deadlocks)) AS error_rate
        FROM
            pg_stat_database;
        """

        # 5-6: Logical reads per second and physical reads per second
        read = """
        SELECT
            logical_reads / (extract(epoch from now() - stats_reset)) AS logical_reads_per_second,
            physical_reads / (extract(epoch from now() - stats_reset)) AS physical_reads_per_second
        FROM (
            SELECT
                sum(tup_returned + tup_fetched) AS logical_reads,
                sum(blks_read) AS physical_reads,
                max(stats_reset) AS stats_reset
            FROM
                pg_stat_database
            ) subquery;
        """

        # 7: Active session count
        active_session = """
        SELECT
            count(*) AS active_session
        FROM
            pg_stat_activity;
        """

        # 8: Transactions committed per second
        transactions_per_second = """
        SELECT
            total_commits / (extract(epoch from now() - max_stats_reset)) AS transactions_per_second
        FROM (
            SELECT
            sum(xact_commit) AS total_commits,
            max(stats_reset) AS max_stats_reset
        FROM
            pg_stat_database
            ) subquery;
        """

        # 9-11: Rows scanned, updated, and deleted per second
        tup = """
        SELECT
            rows_scanned / (extract(epoch from now() - max_stats_reset)) AS rows_scanned_per_second,
            rows_updated / (extract(epoch from now() - max_stats_reset)) AS rows_updated_per_second,
             rows_deleted / (extract(epoch from now() - max_stats_reset)) AS rows_deleted_per_second
        FROM (
            SELECT
            sum(tup_returned) AS rows_scanned,
            sum(tup_updated) AS rows_updated,
            sum(tup_deleted) AS rows_deleted,
            max(stats_reset) AS max_stats_reset
            FROM
             pg_stat_database
            ) subquery;
        """

        try:
            # Execute 1: Cache hit rate
            cursor.execute(cache_hit_rate_sql)
            result = cursor.fetchall()
            for s in result:
                state_list.append(float(s[0]))
            # print('cache_hit_rate_sql: ', state_list)

            # Execute 2: Concurrent user count
            cursor.execute(concurrent_users)
            result = cursor.fetchall()
            state_list.append(float(result[0][0]))
            # print('Concurrent user count: ', state_list)

            # Execute 3: Lock wait count (commented out)
            # cursor.execute(lock)
            # result = cursor.fetchall()
            # state_list.append(float(result[0][0]))
            # print('Lock wait count: ', state_list)

            # Execute 4: Error rate
            cursor.execute(error_rate)
            result = cursor.fetchall()
            state_list.append(float(result[0][0]))
            # print('Error rate: ', state_list)

            # Execute 5: Logical reads and physical reads per second
            cursor.execute(read)
            result = cursor.fetchall()
            # print(result)
            for i in result[0]:
                state_list.append(float(i))
            # print('Logical and physical reads: ', state_list)

            # Execute 6: Active session count
            cursor.execute(active_session)
            result = cursor.fetchall()
            # print(result)
            state_list.append(float(result[0][0]))
            # print('Active sessions: ', state_list)

            # Execute 7: Transactions committed per second
            cursor.execute(transactions_per_second)
            result = cursor.fetchall()
            # print(result)
            state_list.append(float(result[0][0]))
            # print('Transactions per second: ', state_list)

            # Execute 8: Rows scanned, updated, and deleted per second
            cursor.execute(tup)
            result = cursor.fetchall()
            for i in result[0]:
                state_list.append(float(i))

            cursor.close()
            conn.close()
        except Exception as error:
            print(error)
        for i in range(len(state_list)):
            # print(i)
            state_list[i] = float(state_list[i])
        return state_list

    def change_knob(self, knobs):
        """
        Apply knob changes without SSH - PostgreSQL only
        """
        flag = True
        conn = self.get_conn()
        cursor = conn.cursor()
        
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
            
            # Commit the changes
            conn.commit()
            
            # Reload configuration
            cursor.execute("SELECT pg_reload_conf();")
            conn.commit()
            
            if flag:
                print('Applied knobs successfully!')
            else:
                print('Some knobs failed to apply')
                
        except Exception as error:
            print(f"Error applying knobs: {error}")
            flag = False
        finally:
            cursor.close()
            conn.close()
        
        return flag