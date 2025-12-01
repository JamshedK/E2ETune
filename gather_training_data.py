import os
import json
import glob

def load_knob_config(path):
    with open(path, 'r') as f:
        return json.load(f)

def normalize_value(value, min_val, max_val):
    if max_val == min_val:
        return 0.0
    # Ensure value is within bounds
    value = max(min_val, min(value, max_val))
    return (value - min_val) / (max_val - min_val)

def normalize_config(config, knob_limits):
    normalized = {}
    for knob, value in config.items():
        if knob in knob_limits:
            limits = knob_limits[knob]
            min_val = limits.get('min')
            max_val = limits.get('max')
            
            if min_val is not None and max_val is not None:
                norm_val = normalize_value(value, min_val, max_val)
                # Convert to percentage string as requested "0-10%"
                # Or maybe just keep as float 0-1? 
                # The prompt says "convert configurations numbers into 0-10% etc"
                # Let's store as percentage value (0-100) for now, or maybe 0.0-1.0
                # If I look at "0-10%", it implies a range or bucket.
                # Let's stick to 0-1 float for ML, or formatted string if for NLP text.
                # Since it's for Llama factory, text is good.
                # "autovacuum_analyze_scale_factor: 10%"
                normalized[knob] = f"{norm_val * 100:.2f}%"
            else:
                normalized[knob] = value
        else:
            normalized[knob] = value
    return normalized

def get_best_config(runhistory_path):
    with open(runhistory_path, 'r') as f:
        data = json.load(f)
    
    runs = data['data']
    configs = data['configs']
    
    best_cost = float('inf')
    best_config_id = None
    
    for run in runs:
        # run structure: [[conf_id, ...], [cost, ...]]
        conf_id = str(run[0][0])
        cost = run[1][0]
        
        if cost < best_cost:
            best_cost = cost
            best_config_id = conf_id
            
    if best_config_id and best_config_id in configs:
        return configs[best_config_id]
    return None

def process_workloads(data_dir, metrics_dir, knob_config):
    training_data = []
    
    # List all workload directories
    workload_dirs = [d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d))]
    
    for workload_dir in workload_dirs:
        if not workload_dir.endswith('_smac_output'):
            continue
            
        # Construct paths
        runhistory_path = os.path.join(data_dir, workload_dir, 'run_1608637542', 'runhistory.json') # Note: run_ID might vary?
        # Check if run directory exists, it might not be hardcoded
        # Find the run directory inside workload_dir
        runs = glob.glob(os.path.join(data_dir, workload_dir, 'run_*'))
        if not runs:
            print(f"No run directory found in {workload_dir}")
            continue
        # Assuming one run per workload folder for now, or take the first one
        runhistory_path = os.path.join(runs[0], 'runhistory.json')
        
        if not os.path.exists(runhistory_path):
            print(f"Runhistory not found: {runhistory_path}")
            continue
            
        # Construct metrics file path
        # sample_ycsb_config0_smac_output -> sample_ycsb_config0_internal_metrics.json
        base_name = workload_dir.replace('_smac_output', '')
        metrics_file = f"{base_name}_internal_metrics.json"
        metrics_path = os.path.join(metrics_dir, metrics_file)
        
        if not os.path.exists(metrics_path):
            print(f"Metrics file not found: {metrics_path}")
            continue
            
        # Get best config
        best_config = get_best_config(runhistory_path)
        if not best_config:
            print(f"No best config found for {workload_dir}")
            continue
            
        # Normalize config
        norm_config = normalize_config(best_config, knob_config)
        
        # Read metrics
        with open(metrics_path, 'r') as f:
            metrics = json.load(f)
            
        # Create training example
        # Format for Llama factory / NLP
        # Input: Internal metrics
        # Output: Best configuration
        
        input_text = json.dumps(metrics, indent=2)
        output_text = json.dumps(norm_config, indent=2)
        
        training_data.append({
            "instruction": "Predict the best database configuration based on the internal metrics.",
            "input": input_text,
            "output": output_text
        })
        
    return training_data

def main():
    base_dir = '/home/mark/projects/E2ETune'
    knob_config_path = os.path.join(base_dir, 'knob_config', 'knob_config_pg14.json')
    output_file = os.path.join(base_dir, 'training_data.json')
    
    knob_config = load_knob_config(knob_config_path)
    
    all_training_data = []
    
    # Define workloads to process
    workloads = [
        {'data_dir': 'ycsb_data', 'metrics_subdir': 'ycsb'},
        {'data_dir': 'tpcc_data', 'metrics_subdir': 'tpcc'}
    ]
    
    for workload in workloads:
        data_dir = os.path.join(base_dir, workload['data_dir'])
        metrics_dir = os.path.join(base_dir, 'internal_metrics', workload['metrics_subdir'])
        
        if os.path.exists(data_dir) and os.path.exists(metrics_dir):
            print(f"Processing {workload['data_dir']}...")
            data = process_workloads(data_dir, metrics_dir, knob_config)
            all_training_data.extend(data)
        else:
            print(f"Skipping {workload['data_dir']} - directory not found")
    
    with open(output_file, 'w') as f:
        json.dump(all_training_data, f, indent=2)
        
    print(f"Generated {len(all_training_data)} training examples in {output_file}")

if __name__ == "__main__":
    main()
