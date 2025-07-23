from datetime import datetime
import threading
import psycopg2
import time
import re

class key:
    def __init__(self, value, type):
        self.value = value
        self.type = type
def generate_random_string(length=None):
    # chars = string.ascii_letters + string.digits
    # return ''.join(random.sample(chars, length))

    now = datetime.now()
    timestamp_str = now.strftime("%m%d_%H_%M_%S")
    return timestamp_str

def connect_og(database_name, user_name, password, host, port):
    connection = psycopg2.connect(database=database_name,
                                  user=user_name,
                                  password=password,
                                  host=host,
                                  port=port)
    cur = connection.cursor()
    return connection, cur

class one_thread_given_queries(threading.Thread):
    def __init__(self, wg, log_path, connection, cur, thread_id, time_stamp) -> None:
        threading.Thread.__init__(self)
        self.wg = wg
        self.log_path = log_path
        self.connection = connection
        self.cur = cur
        self.thread_id = thread_id
        self.time_stamp = time_stamp

    def run(self):
        try:
            sql_list = self.wg
            with open(self.log_path, 'w') as f:
                print(f"Thread {self.thread_id} log file start. Tot sql num : {len(sql_list)}")
                f.write(f"Thread {self.thread_id} log file start. Tot sql num : {len(sql_list)}\n")
                start_time = time.time()
                for i, it in enumerate(sql_list):
                    # print(it)
                    error_info = it
                    self.cur.execute(it)
                    self.connection.commit()
                    # print(f"Thread {self.thread_id} sql id {i}")
                    # if i % 200 == 0:
                    f.write(f"Thread {self.thread_id} {i} sqls has been processed successfully.\n")
                    print(f"Thread {self.thread_id} {i} sqls has been processed successfully.\n")
                    end_time = time.time()
                    elapsed_time = end_time - start_time
                    f.write(f"Thread {self.thread_id} processed time: {elapsed_time} seconds.\n")
                    print(f"Thread {self.thread_id} processed time: {elapsed_time} seconds.\n")

                end_time = time.time()
                self.time_stamp[self.thread_id] = key(len(sql_list), end_time - start_time)

        except Exception as e:
            print("Error: ", e)
            print('error_info:', error_info)

class multi_thread:
    def __init__(self, db, workload_path, thread_num, log_path):
        self.wg_file = None
        self.id = generate_random_string(10)
        self.workload_name = workload_path
        self.thread_num = thread_num
        # self.wg_path = 'olap_workloads/tpch_1.wg'
        # self.wg_path = "workloads/" + workload_path + "_workload" + ".wg"
        self.db = db
        self.wg_path = workload_path
        self.log_path = log_path
        self.sql_list_idx = dict()

    def data_pre(self):
        connection, cur = connect_og(
            database_name=self.db.database,
            user_name=self.db.user,
            password=self.db.password,
            host=self.db.host,
            port=self.db.port
        )

        connection.close()

        with open(self.wg_path, 'r') as f:
            self.wg_file = f.read()

        sql_list = re.split(r'[;\n]+', self.wg_file)
        for i, it in enumerate(sql_list):
            sql_list[i] += ";"

        if sql_list[-1] == ";":
            sql_list = sql_list[0:-1]

        if len(sql_list) > 3000:
            sql_list = sql_list[:3000]

        self.sql_list_idx = dict()

        for i in range(self.thread_num):
            self.sql_list_idx[i] = []

        for i in range(len(sql_list)):
            self.sql_list_idx[i % self.thread_num].append(sql_list[i])

    def run(self):
        connection, cur = connect_og(
            database_name=self.db.database,
            user_name=self.db.user,
            password=self.db.password,
            host=self.db.host,
            port=self.db.port
        )
        threads = []
        time_stamp = dict()

        for i in range(self.thread_num):
            thread = one_thread_given_queries(
                wg=self.sql_list_idx[i],
                log_path=self.log_path,
                connection=connection,
                cur=cur,
                thread_id=i,
                time_stamp=time_stamp
            )
            threads.append(thread)

        start_time = time.time()
        for it in threads:
            it.start()
        for it in threads:
            it.join()
        end_time = time.time()

        with open(self.log_path, 'w') as f:
            f.write(f"total sql num : {len(self.wg_file)}\n")
            f.write(f"total time consumed : {end_time - start_time}\n")
            for i in range(self.thread_num):
                f.write(f"\tthread {i} processed sql num : {time_stamp[i].value}\n")
                f.write(f"\tthread {i} using time : {time_stamp[i].type}\n")
        connection.close()
        print('length of sql list: ',len(self.sql_list_idx[0]))
        print('total time: ',end_time - start_time)
        return [ -(end_time - start_time) / (len(self.sql_list_idx[0]) * self.thread_num),\
                len(self.sql_list_idx[0]) / (end_time - start_time) * self.thread_num]

## Uncomment below to run as a standalone script, this main file is designed to test the multi_thread class which essentially
# runs a workload on a PostgreSQL database using multiple threads. Adjust TestDb class and workload_path as needed.
# if __name__ == "__main__":
#     import os
    
#     # Create test database configuration
#     class TestDB:
#         def __init__(self):
#             self.host = "localhost"
#             self.port = 5432
#             self.database = "benchbase"      
#             self.user = "postgres"          
#             self.password = "123456"     
    
#     # Create test workload file if it doesn't exist
#     workload_path = "olap_workloads/tpch_1.wg"
    
#     # Create database instance
#     db = TestDB()
    
#     # Create logs directory
#     os.makedirs("test_logs", exist_ok=True)
#     log_path = f"test_logs/test_run_{generate_random_string()}.log"
    
#     # Create and run multi_thread instance
#     print("Starting multi-thread database test...")
#     print(f"Workload file: {workload_path}")
#     print(f"Log file: {log_path}")
    
#     try:
#         # Initialize multi_thread
#         mt = multi_thread(
#             db=db,
#             workload_path=workload_path,
#             thread_num=2,
#             log_path=log_path
#         )
        
#         # Prepare data
#         print("Preparing workload data...")
#         mt.data_pre()
        
#         # Run the workload
#         print(f"Running workload with {mt.thread_num} threads...")
#         results = mt.run()
        
#         print("\n=== Test Results ===")
#         print(f"Performance metrics: {results}")
#         print(f"Check log file for details: {log_path}")
        
#         # Show log contents
#         if os.path.exists(log_path):
#             print("\n=== Log File Contents ===")
#             with open(log_path, 'r') as f:
#                 print(f.read())
        
#     except Exception as e:
#         print(f"Test failed: {e}")
#         import traceback
#         traceback.print_exc()    