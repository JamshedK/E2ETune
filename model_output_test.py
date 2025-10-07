from knob_config.parse_knob_config import get_knobs
import os 
import json

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
        




def main():
    knobs_detail = get_knobs('knob_config/knob_config.json')

    inference_results_folder = 'inference_results/tpch1/'

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
    


if __name__ == "__main__":
    main()