import os
import sys

# Change to project root directory so all relative paths work
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)

# Add parent directory to path for imports
sys.path.insert(0, project_root)

from Database import Database
from workload_executor import workload_executor
import utils
import json

inner_names = ["xact_commit", "xact_rollback", "blks_read", "blks_hit", "tup_returned", "tup_fetched", "tup_inserted", "conflicts", "tup_updated", "tup_deleted", "disk_read_count", "disk_write_count", "disk_read_bytes", "disk_write_bytes"]

# Hardcoded configuration
CONFIG = {
    'database_config': {
        'host': 'localhost',
        'port': '5432',
        'user': 'postgres',
        'password': '123456',
        'database': 'tpcc',
        'data_path': '/var/lib/postgresql/14/main'
    },
    'tuning_config': {
        'knob_config': 'knob_config/knob_config_pg14.json',
        'log_path': 'llm_tuning_oltp/oltp.log'
    },
    'benchmark_config': {
        'benchmark': 'tpcc',
        'tool': 'benchbase',
        'type': 'oltp',
        'benchbase_jar': '/home/karimnazarovj/E2ETune/benchbase/target/benchbase-postgres/benchbase.jar',
        'workload_path': 'oltp_workloads/tpcc',
        'thread': '4',
        'log_path': 'llm_tuning_oltp/oltp.log'
    },
    'surrogate_config': {
        'model_name': 'random_forest',
        'model_path': '/home/karimnazarovj/E2ETune/surrogate_model/surrogate.pkl',
        'feature_path': 'SuperWG/feature.json'
    }
}

class LLMTuning: 

    def __init__(self, workload_file, workload_name, database=None):
        self.args = CONFIG.copy()
        if database:
            self.args['database_config']['database'] = database
        
        self.workload_file = workload_file
        # Full path for workload (from project root)
        self.full_workload_path = os.path.join('oltp_workloads', workload_file)
        
        self.db = Database(config=self.args, path=self.args['tuning_config']['knob_config'])
        self.executor = workload_executor(self.args, utils.get_logger(self.args['tuning_config']['log_path']), "training_records.log", internal_metrics=None)
        self.workload_name = workload_name

        # Read workload file content (now from project root)
        with open(self.full_workload_path, 'r') as f:
            self.workload_content = f.read()

    def default_run(self, workload_file, args):
        """Run the default configuration"""

        print(f"Running default configuration for workload")

        # remove auto_conf from the database
        self.db.remove_auto_conf() 

        # reset inner metrics
        print("Resetting inner metrics...")
        self.db.reset_inner_metrics()

        # run the workload with default configuration
        qps = self.executor.run_config(config=None, workload_file=workload_file)
        print(f"Default configuration run complete for workload")

        # get the internal metrics
        internal_metrics = self.db.fetch_inner_metrics()
        print(f"Internal metrics collected: {internal_metrics}")
        
        # save the internal metrics to a file
        benchmark_name = self.args['benchmark_config']['benchmark']
        workload_name = os.path.splitext(os.path.basename(workload_file))[0]  # e.g., "sample_tpcc_config0"
        metrics_dir = f"llm_tuning_oltp/internal_metrics"
        os.makedirs(metrics_dir, exist_ok=True)
        metrics_file = f"{metrics_dir}/{workload_name}_internal_metrics.json"
        
        with open(metrics_file, "w") as f:
            json.dump(internal_metrics, f, indent=4)
        print(f"Internal metrics saved to: {metrics_file}")
        
        return {"internal_metrics": internal_metrics, "qps": qps}

    def format_inner_metrics(self, internal_metrics):
        """Format internal metrics in human-readable format."""
        inner_metrics_string = ''
        for name in inner_names:
            value = internal_metrics.get(name, 0)
            if value > 0 and value < 1:
                if value < 0.3333: inner_metrics_string += f'{name}: low; '
                elif value < 0.66667: inner_metrics_string += f'{name}: middle; '
                else: inner_metrics_string += f'{name}: high; '
            elif value > 0 and value < 1000:
                inner_metrics_string += f'{name}: {(int(value * 100)) / 100.0}; '
            elif value < 1000000:
                inner_metrics_string += f'{name}: {(int(value/ 1000))}k; '
            elif value >= 1000000: 
                inner_metrics_string += f'{name}: {(int(value/ 100000)) / 10} million; '
        return inner_metrics_string

    def generate_prompt(self):
        database = 'PostgreSQL'

        # get internal metrics (use full path from project root)
        res = self.default_run(self.full_workload_path, self.args)
        internal_metrics = res['internal_metrics']
        qps = res['qps']
        inner_metrics_json = self.format_inner_metrics(internal_metrics)

        # Create structured prompt matching training data format
        prompt_data = {
            "system": "You are an expert database tuning assistant. Your task is to analyze internal database metrics and select the optimal configuration buckets (percentage ranges) for various knobs to maximize performance.",
            "instruction": "Based on the provided internal metrics, predict the best configuration knobs. You MUST output the result as a valid JSON object. The keys should be the database configuration knobs, and the values should be the recommended percentage ranges (e.g., '10-20%'). Do not provide any explanations or additional text.",
            "input": inner_metrics_json,
            "meta": {
                "database": self.args['database_config']['database'],
                "workload_name": self.workload_name,
                "qps": qps
            } 
        }
        
        # Create prompts folder if it doesn't exist
        os.makedirs('llm_tuning_oltp/prompts', exist_ok=True)
        
        # Save as JSON file
        with open(f"llm_tuning_oltp/prompts/{self.workload_name}_prompt.json", "w") as f:
            json.dump(prompt_data, f, indent=2)
        
        print(f"Prompt saved to: llm_tuning_oltp/prompts/{self.workload_name}_prompt.json")
        return prompt_data

if __name__ == "__main__":
    # Just provide the workload file name (include subdirectory for OLTP benchmarks)
    workload_file = 'tpcc/sample_tpcc_config13.xml'
    
    # Derive workload name from file (remove .xml extension and path)
    workload_name = os.path.basename(workload_file).replace('.xml', '')
    
    # create a LLMTuning instance
    llm_tuner = LLMTuning(workload_file, workload_name, database='tpcc_50')

    llm_tuner.generate_prompt()