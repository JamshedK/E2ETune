import os
import logging
import time
import json
import shutil

class BenchBaseRunner:
    def __init__(self, args, logger=None):
        self.benchmark_config = args['benchmark_config']
        self.database_config = args['database_config']
        self.logger = logger or logging.getLogger(__name__)
    
    def run_benchmark(self, workload_path, log_file):
        # Run BenchBase benchmark and return throughput
        # Get benchmark name from config.ini
        benchmark_name = self.benchmark_config.get('benchmark', 'tpcc')
        
        # Extract workload name from file (e.g., "sample_tpcc_config.xml" -> "sample_tpcc_config")
        workload_name = os.path.splitext(os.path.basename(workload_path))[0]
        
        # Create results directory structure: stress_test_results/tpcc_results/sample_tpcc_config/
        results_base = "stress_test_results"
        workload_base_dir = os.path.join(results_base, f"{benchmark_name}_results")
        workload_results_dir = os.path.join(workload_base_dir, workload_name)
        os.makedirs(workload_results_dir, exist_ok=True)
        
        # Convert to absolute path to avoid permission issues
        workload_results_dir = os.path.abspath(workload_results_dir)
        
        # Copy config to BenchBase directory and get the new path
        benchbase_config, benchbase_dir = self.copy_config_to_benchbase(workload_path, benchmark_name)
        
        # Use run_benchmark.sh script with results going to our directory
        script_path = os.path.abspath('run_benchmark.sh')
        timestamp = int(time.time())
        
        # The script expects: BENCHNAME TIMESTAMP OUTPUTDIR OUTPUTLOG
        command = f'bash {script_path} {benchmark_name.lower()} {timestamp} {workload_results_dir} {workload_results_dir}'
        
        self.logger.info(f'Running BenchBase with benchmark: {benchmark_name}')
        self.logger.info(f'Command: {command}')
        self.logger.info(f'Results will be saved to: {workload_results_dir}')
        
        state = os.system(command)
        
        # Cleanup - remove the copied config file
        # self.cleanup_config(benchbase_config)
        
        if state == 0:
            self.logger.info('BenchBase running success')
        else:
            self.logger.error(f'BenchBase running error - exit code: {state}')
            return 0.0
        
        # Clean up results and find summary.json
        summary_path = self.clean_and_find_summary(workload_results_dir)
        if not summary_path:
            self.logger.error('No summary.json found in results')
            return 0.0
        
        # Parse throughput from summary.json
        throughput = self.parse_summary_json(summary_path)
        self.logger.info(f'BenchBase {benchmark_name} throughput: {throughput}')
        
        return throughput
    
    def clean_and_find_summary(self, results_dir):
        """Clean up results directory and find .summary.json file."""
        summary_path = None
        
        # Find .summary.json file and remove others
        for file in os.listdir(results_dir):
            file_path = os.path.join(results_dir, file)
            if file.endswith('.summary.json'):
                summary_path = file_path
            else:
                # Remove non-.summary.json files
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                except Exception as e:
                    self.logger.warning(f'Could not remove file {file_path}: {e}')
        
        return summary_path
    
    def parse_summary_json(self, summary_path):
        """Parse throughput from summary.json file."""
        try:
            with open(summary_path, 'r') as f:
                data = json.load(f)
            
            # Get throughput from metrics section
            throughput = data["Throughput (requests/second)"]
            
            self.logger.info(f'Parsed throughput from summary.json: {throughput}')
            return throughput
            
        except Exception as e:
            self.logger.error(f'Error parsing summary.json: {e}')
            return 0.0
    
    def update_config_file(self, config_file, benchmark_name):
        # Update BenchBase XML config with database settings using string replacement to preserve comments
        try:
            # Read the file as text
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Update database connection values
            host = self.database_config.get('host', 'localhost')
            port = self.database_config.get('port', '5432')
            database = self.database_config.get('database', 'benchbase')
            username = self.database_config.get('user', 'postgres')
            password = self.database_config.get('password', '')
            
            new_url = f"jdbc:postgresql://{host}:{port}/{database}?sslmode=disable&amp;ApplicationName={benchmark_name}&amp;reWriteBatchedInserts=true"
            
            # Use regex to replace values while preserving XML structure and comments
            import re
            
            # Update URL
            content = re.sub(r'<url>.*?</url>', f'<url>{new_url}</url>', content)
            
            # Update username
            content = re.sub(r'<username>.*?</username>', f'<username>{username}</username>', content)
            
            # Update password
            content = re.sub(r'<password>.*?</password>', f'<password>{password}</password>', content)
            
            # Update terminals
            content = re.sub(r'<terminals>.*?</terminals>', '<terminals>8</terminals>', content)
            
            # Write back to file
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.logger.info(f'Updated config file: {config_file} (preserving comments)')
            
        except Exception as e:
            self.logger.error(f'Error updating config file {config_file}: {e}')
    
    def copy_config_to_benchbase(self, workload_path, benchmark_name):
        # Copy config file to BenchBase config directory and update it
    
        # Get BenchBase directory and config path
        benchbase_jar = self.benchmark_config.get('benchbase_jar', './benchbase/target/benchbase-postgres/benchbase.jar')
        benchbase_dir = os.path.dirname(os.path.dirname(benchbase_jar))  # Go up two levels from jar to benchbase root
        
        # Create the config directory path: target/benchbase-postgres/config/postgres
        config_dir = os.path.join(benchbase_dir, 'target', 'benchbase-postgres', 'config', 'postgres')
        os.makedirs(config_dir, exist_ok=True)
        
        # Copy config file to the correct config directory
        original_config = os.path.abspath(workload_path)
        config_filename = os.path.basename(workload_path)
        benchbase_config = os.path.join(config_dir, config_filename)
        
        shutil.copy2(original_config, benchbase_config)
        self.logger.info(f"Copied config to BenchBase config directory: {benchbase_config}")
        
        # Update the copied config file with database settings
        self.update_config_file(benchbase_config, benchmark_name)
        
        return benchbase_config, benchbase_dir
    
    def cleanup_config(self, config_file):
        # Remove the temporary config file
        try:
            os.remove(config_file)
            self.logger.info(f"Cleaned up config file: {config_file}")
        except Exception as e:
            self.logger.warning(f"Could not cleanup config file {config_file}: {e}")
    

