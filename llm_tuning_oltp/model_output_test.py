import os 
import sys
import json
import argparse
import configparser

# Change to project root directory so all relative paths work
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)
sys.path.insert(0, project_root)

from knob_config.parse_knob_config import get_knobs
from Database import Database
from workload_executor import workload_executor
import utils


def load_config(config_path='llm_tuning_oltp/llm_config.ini'):
    """Load configuration from ini file."""
    config = configparser.ConfigParser()
    config.read(config_path)
    
    # Convert to dict format expected by Database and workload_executor
    return {
        'database_config': dict(config['database']),
        'tuning_config': dict(config['tuning']),
        'benchmark_config': dict(config['benchmark']),
        'llm_config': dict(config['llm']), 
        'surrogate_config': dict(config['surrogate_config'])
    }


# Updated label mapper to match training data format
label_mapper_s1 = {
    '0-10%': 0,
    '10-20%': 1,
    '20-30%': 2,
    '30-40%': 3,
    '40-50%': 4,
    '50-60%': 5,
    '60-70%': 6,
    '70-80%': 7,
    '80-90%': 8,
    '90-100%': 9
}

rename = {
    "autovacuum_delay": "autovacuum_vacuum_cost_delay",
    "autovacuum_limit": "autovacuum_vacuum_cost_limit",
    "autovacuum_page_dirty": "vacuum_cost_page_dirty",
    "autovacuum_page_hit": "vacuum_cost_page_hit",
    "autovacuum_page_miss": "vacuum_cost_page_miss",
    "autovacuum_max_wal_senders": "max_wal_senders",
}

def convert_labels_to_numeric(knobs_detail, config_dict ):

    # rename the keys in config_dict according to rename dict
    for old_name, new_name in rename.items():
        if old_name in config_dict:
            config_dict[new_name] = config_dict.pop(old_name)
    out = {}
    
    for index, knob_name in enumerate(config_dict.keys()):
        if knob_name not in knobs_detail:
            print(f"Warning: {knob_name} not found in knob details, skipping...")
            continue
        detail = knobs_detail[knob_name]

        label_value = config_dict[knob_name]

        # compute s1_length and s2_length by dividing the range into 10 and 9 equal parts
        s1_length = (detail['max'] - detail['min']) / 10

        # if s1_length is 0, set the value to default
        if s1_length == 0:
            out[knob_name] = detail['default']
        
        else: 
            # convert the label to numeric 
            numeric = s1_length * (label_mapper_s1[label_value]) + s1_length / 2 

            # if the type is integer, convert to int
            if detail['type'] == 'integer':
                numeric = int(numeric + detail['min'])
            else:
                numeric = float(numeric + detail['min'])
            out[knob_name] = numeric
        print(f"Converted {knob_name}: {label_value} to {numeric}")
    
    return out

def default_run(workload_file, db, executor):
        """Run the default configuration"""

        print(f"Running default configuration for workload")

        # remove auto_conf from the database
        db.remove_auto_conf() 

        # reset inner metrics
        print("Resetting inner metrics...")
        db.reset_inner_metrics()

        # run the workload with default configuration
        qps = executor.run_config(config=None, workload_file=workload_file)
        print(f"Default configuration run complete for workload")
        
        print(f"-----------------Default QPS: {qps}--------------------")
        return qps

def apply_configuration_and_get_metrics(config, workload_file, db, executor):
    # reset the configuration 
    db.remove_auto_conf()

    # recreate the database 
    db.recreate_from_template()

    # run config 
    qps = executor.run_config(config=config, workload_file=workload_file)

    print(f"-----------------QPS: {qps}--------------------")
    return qps


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, default='llm_tuning_oltp/llm_config.ini', help='config file path')
    cmd = parser.parse_args()
    
    # Load config from ini file
    args = load_config(cmd.config)
    
    # Full workload path
    workload_file = os.path.join('oltp_workloads', args['benchmark_config']['workload_file'])
    
    knobs_detail = get_knobs(args['tuning_config']['knob_config'])

    db = Database(config=args, path=args['tuning_config']['knob_config'])
    executor = workload_executor(args, utils.get_logger(args['tuning_config']['log_path']), "training_records.log", internal_metrics=None)

    qps_list = []

    # run default configuration
    qps = default_run(workload_file, db, executor)
    qps_list.append(("default", qps))
    print("Default configuration run complete.")

    # get each json file in the responses folder
    responses_folder = args['llm_config']['responses_folder']
    files = os.listdir(responses_folder)
    files = [f for f in files if f.endswith('.json')]
    print(f"Found {len(files)} response files in {responses_folder}")

    # convert each file to numeric and run
    for file in files:
        with open(os.path.join(responses_folder, file), 'r') as f:
            try:
                config_dict = json.load(f)
                print(f"\nProcessing file: {file}")
                out = convert_labels_to_numeric(knobs_detail, config_dict)
                # run configuration and get the metrics
                metric = apply_configuration_and_get_metrics(out, workload_file, db, executor)
                qps_list.append((file, metric))
            except json.JSONDecodeError as e:
                print(f"Error parsing {file}: {e}")
                continue
            except Exception as e:
                print(f"Error processing {file}: {e}")
                continue
    
    # sort the qps_list by file name
    qps_list = sorted(qps_list, key=lambda x: x[0])

    # save the qps_list to a file
    output_file = 'llm_tuning_oltp/model_output_qps.txt'
    with open(output_file, 'w') as f:
        for file, qps in qps_list:
            f.write(f"{file}: {qps}\n")
    
    print(f"\n{'='*50}")
    print("Results Summary:")
    print(f"{'='*50}")
    for file, qps in qps_list:
        print(f"  {file}: {qps}")
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()