import copy
import time
from multi_thread import multi_thread
import Database

class workload_executor:
    def __init__(self, args, logger, records_log):
        self.benchmark_config = args['benchmark_config']
        self.sur_config = args['surrogate_config']
        self.logger = logger
        self.db = Database.Database(config=args)
        self.records_log = records_log

    def run_config(self, config):
        """
        Test a single configuration on OLAP workload
        Returns: performance score (QPS)
        """
        
        # Step 1: Apply configuration (KEEP existing)
        self.db.change_knob(config)
        
        # Step 2: Run OLAP workload 
        workload_path = self.benchmark_config['workload_path']
        log_file = self.benchmark_config['log_path']
        performance = self.test_by_dwg(workload_path, log_file)
        
        # test_by_dwg returns [negative_avg_time, qps]
        qps = performance[1]  # Use QPS as our performance metric
        
        # Step 3: Collect internal metrics AFTER workload
        inner_metrics = self.db.fetch_inner_metric()
        
        # Step 4: Create clean data record
        data_record = {
            'workload': workload_path,
            'configuration': config,
            'performance_qps': qps,
            'inner_metrics': inner_metrics,
            'timestamp': time.time()
        }
        
        # Step 5: Save to single clean file
        self.save_training_data(data_record)
        
        return qps

    
    def test_by_dwg(self, workload_path, log_file):
        mh = multi_thread(self.db, workload_path, int(self.benchmark_config['thread']), log_file)

        mh.data_pre()
        return mh.run()
