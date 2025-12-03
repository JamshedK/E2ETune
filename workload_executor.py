import copy
import time
import os
from multi_thread import multi_thread
from benchbase_runner import BenchBaseRunner
import Database
import json
import joblib

class workload_executor:
    def __init__(self, args, logger, records_log, internal_metrics):
        self.args = args
        self.benchmark_config = args['benchmark_config']
        self.sur_config = args['surrogate_config']
        self.logger = logger
        self.db = Database.Database(config=args, path=args['tuning_config']['knob_config'])
        self.records_log = records_log
        self.internal_metrics = internal_metrics
        
        # Load knob config for normalization
        self.knob_config_path = args['tuning_config']['knob_config']
        with open(self.knob_config_path, 'r') as f:
            self.knobs = json.load(f)
        
        # Load surrogate model if available
        self.surrogate_model = None
        self.y_min = None
        self.y_max = None
        surrogate_path = self.sur_config.get('model_path', 'surrogate_model/surrogate.pkl')
        if os.path.exists(surrogate_path):
            saved = joblib.load(surrogate_path)
            # Handle both old format (just model) and new format (dict with model + normalization)
            if isinstance(saved, dict):
                self.surrogate_model = saved['model']
                self.y_min = saved['y_min']
                self.y_max = saved['y_max']
            else:
                self.surrogate_model = saved
            print(f"Loaded surrogate model from {surrogate_path}")

    def run_config(self, config, workload_file):
        """
        Test a single configuration on OLAP workload
        Returns: performance score (QPS)
        """
        print("Workload executor is called")
        
        # Step 0: For OLTP workloads, recreate database from template first
        tool = self.benchmark_config.get('tool', 'dwg').lower()
        if tool == 'benchbase':
            print("Step 0: Recreating database from template for clean OLTP benchmark...")
            if not self.db.recreate_from_template():
                print("Warning: Failed to recreate database from template, continuing anyway...")
        
        print(f"Step 1: Change the database knobs")
        temp_config = copy.deepcopy(config)
        # Step 1: Apply configuration
        if config is not None:
            print(f"Appling configuration")
            self.db.change_knob(temp_config)
        
        # Step 2: Run workload based on tool configuration
        log_file = self.benchmark_config['log_path']
        
        if tool == 'benchbase':
            print(f"Step 2: Run OLTP workload using BenchBase")
            workload_path = workload_file
            print(f"Workload path: {workload_path}")
            performance = self.test_by_benchbase(workload_path, log_file)
            qps = performance  # BenchBase returns throughput directly
        else:
            print(f"Step 2: Run OLAP workload using DWG")
            workload_path = workload_file
            print(f"Workload path: {workload_path}")
            performance = self.test_by_dwg(workload_path, log_file)
            # test_by_dwg returns [negative_avg_time, qps]
            qps = performance[1]  # Use QPS as our performance metric 

        # negate qps
        if qps > 0:
            qps = -qps
        if config:
            # Step 4: Save the data
            with open('smac_his/offline_sample.jsonl', 'a') as f:
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

    def test_by_benchbase(self, workload_path, log_file):
        # Test the database performance using benchbase
        benchbase_runner = BenchBaseRunner(self.args, self.logger)
        return benchbase_runner.run_benchmark(workload_path, log_file)

    def run_config_surrogate(self, config, workload_file):
        """
        Predict performance using surrogate model instead of real execution.
        Much faster - milliseconds vs minutes.
        Returns: predicted performance score (negative QPS, since SMAC minimizes)
        """
        if self.surrogate_model is None:
            raise ValueError("Surrogate model not loaded. Train it first or check model_path in config.")
        
        if self.internal_metrics is None:
            raise ValueError("Internal metrics not available. Run default_run first to collect them.")
        
        # Build feature vector - same as training
        x = []
        
        # Normalize knob values (same order as training)
        for key in config.keys():
            if key in self.knobs:
                detail = self.knobs[key]
                if detail['max'] - detail['min'] != 0:
                    normalized = (config[key] - detail['min']) / (detail['max'] - detail['min'])
                    x.append(normalized)
        
        # Add inner metrics (as list, same as training)
        if isinstance(self.internal_metrics, dict):
            x += list(self.internal_metrics.values())
        else:
            x += self.internal_metrics
        
        # Predict (model outputs normalized values)
        pred_normalized = self.surrogate_model.predict([x])[0]
        
        # Denormalize to actual throughput if normalization params are available
        if self.y_min is not None and self.y_max is not None:
            predicted_qps = pred_normalized * (self.y_max - self.y_min) + self.y_min
        else:
            predicted_qps = pred_normalized
        
        # Negate for SMAC (it minimizes, so negative QPS)
        if predicted_qps > 0:
            predicted_qps = -predicted_qps
        
        print(f"Surrogate prediction for config: {predicted_qps:.2f} QPS")
        return predicted_qps
