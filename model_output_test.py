from knob_config.parse_knob_config import get_knobs
import os 
import json
import argparse
from config import parse_config
import os
from Database import Database
from workload_executor import workload_executor
import utils

label_mapper_s1 = {
    '00% to 10%': 0,
    '10% to 20%': 1,
    '20% to 30%': 2,
    '30% to 40%': 3,
    '40% to 50%': 4,
    '50% to 60%': 5,
    '60% to 70%': 6,
    '70% to 80%': 7,
    '80% to 90%': 8,
    '90% to 100%': 9
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

def apply_configuration_and_get_metrics(config, db, executor):
    # reset the configuration 
    db.remove_auto_conf()

    # run config 
    qps = executor.run_config(config=config, workload_file='tpch_2.wg')

    print(f"-----------------QPS: {qps}--------------------")
    return qps



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=str, default='localhost', help='the database host')
    parser.add_argument('--database', type=str, default='benchbase', help='workload file')
    cmd = parser.parse_args()
    # Load configuration file
    args = parse_config.parse_args("config/config.ini")
    # print(args)
    # args['benchmark_config']['workload_path'] = 'SuperWG/res/gpt_workloads/' + cmd.workload
    args['database_config']['database'] = cmd.database
    args['tuning_config']['offline_sample'] += cmd.host
    knobs_detail = get_knobs('knob_config/knob_config.json')

    db = Database(config=args, path=args['tuning_config']['knob_config'])
    executor = workload_executor(args, utils.get_logger(args['tuning_config']['log_path']), "training_records.log", internal_metrics=None)

    inference_results_folder = 'inference_results/tpch1/'

    qps_list = []

    # run default configuration
    qps = default_run('tpch_2.wg', db, executor)
    qps_list.append(("default", qps))
    print("Default configuration run complete.")

    # get each json file in the folder
    files = os.listdir(inference_results_folder)
    files = [f for f in files if f.endswith('.json')]
    print(f"Found {len(files)} files in {inference_results_folder}")

    # convert each file to numeric 
    for file in files:
        # convert the json file to a dict
        with open(os.path.join(inference_results_folder, file), 'r') as f:
            config_dict = json.load(f)
            print(f"Processing file: {file}")
            out = convert_labels_to_numeric(knobs_detail, config_dict)
            # run configuration and get the metrics
            metric = apply_configuration_and_get_metrics(out, db, executor)
            qps_list.append((file, metric))
    
    # sort the qps_list by file name
    qps_list = sorted(qps_list, key=lambda x: x[0])

    # save the qps_list to a file
    with open('model_output_qps.txt', 'w') as f:
        for file, qps in qps_list:
            f.write(f"{file}: {qps}\n")
    


if __name__ == "__main__":
    main()