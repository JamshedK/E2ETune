import copy
import time
from multi_thread import multi_thread
import Database
import json

class workload_executor:
    def __init__(self, args, logger, records_log, internal_metrics):
        self.benchmark_config = args['benchmark_config']
        self.sur_config = args['surrogate_config']
        self.logger = logger
        self.db = Database.Database(config=args, path=args['tuning_config']['knob_config'])
        self.records_log = records_log
        self.internal_metrics = internal_metrics

    def run_config(self, config, workload_file):
        """
        Test a single configuration on OLAP workload
        Returns: performance score (QPS)
        """
        print("Workload executor is called")
        print(f"Step 1: Change the database knobs")
        temp_config = copy.deepcopy(config)
        # Step 1: Apply configuration
        if config is not None:
            print(f"Appling configuration")
            self.db.change_knob(temp_config)
        
        # Step 2: Run OLAP workload 
        print(f"Step 2: Run OLAP workload")
        workload_path = './olap_workloads/' + workload_file
        print(f"Workload path: {workload_path}")
        log_file = self.benchmark_config['log_path']
        performance = self.test_by_dwg(workload_path, log_file)
        
        # test_by_dwg returns [negative_avg_time, qps]
        qps = performance[1]  # Use QPS as our performance metric 

        # negate qps
        if qps > 0:
            qps = -qps
        if config:
            # Step 4: Save the data
            with open('smac_his/offline_sample_tpch.jsonl', 'a') as f:
                temp_config['y'] = [qps, 1/(qps)]  # Multiple performance values
                temp_config['inner_metrics'] = self.internal_metrics  # Database metrics
                temp_config['workload'] = workload_path  # Full workload path
                f.write(json.dumps(temp_config) + '\n')


        print(f"Configuration: {config}, QPS: {qps}")
        
        return qps 

    
    def test_by_dwg(self, workload_path, log_file):
        mh = multi_thread(self.db, workload_path, int(self.benchmark_config['thread']), log_file)

        mh.data_pre()
        return mh.run()
