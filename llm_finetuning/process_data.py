import json
import os
import random

# Configuration
KNOB_CONFIG_PATH = '../knob_config/knob_config_pg14.json'
COLLECTED_SAMPLES_PATH = '../surrogate_model/collected_samples.jsonl'
EXISTING_TRAINING_DATA_PATH = 'training_data.json'
OUTPUT_TRAIN_PATH = 'db_tuning_train.json'
OUTPUT_TEST_PATH = 'db_tuning_test.json'

SYSTEM_PROMPT = "You are an expert database tuning assistant. Your task is to analyze internal database metrics and select the optimal configuration buckets (percentage ranges) for various knobs to maximize performance."

INSTRUCTION_TEXT = "Based on the provided internal metrics, predict the best configuration knobs. You MUST output the result as a valid JSON object. The keys should be the database configuration knobs, and the values should be the recommended percentage ranges (e.g., '10-20%'). Do not provide any explanations or additional text."

INNER_NAMES = [
    "xact_commit", "xact_rollback", "blks_read", "blks_hit", "tup_returned", 
    "tup_fetched", "tup_inserted", "conflicts", "tup_updated", "tup_deleted", 
    "disk_read_count", "disk_write_count", "disk_read_bytes", "disk_write_bytes"
]

def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)

def load_jsonl(path):
    data = []
    with open(path, 'r') as f:
        for line in f:
            data.append(json.loads(line))
    return data

def get_label(value, min_val, max_val):
    if max_val == min_val:
        return "0-10%" # Default or handle as error?
    
    # Normalize
    normalized = (value - min_val) / (max_val - min_val)
    normalized = max(0.0, min(1.0, normalized)) # Clip
    
    # Binning
    if normalized < 0.1: return "0-10%"
    if normalized < 0.2: return "10-20%"
    if normalized < 0.3: return "20-30%"
    if normalized < 0.4: return "30-40%"
    if normalized < 0.5: return "40-50%"
    if normalized < 0.6: return "50-60%"
    if normalized < 0.7: return "60-70%"
    if normalized < 0.8: return "70-80%"
    if normalized < 0.9: return "80-90%"
    return "90-100%"

def process_collected_samples(samples, knob_config):
    processed_data = []
    
    for sample in samples:
        # Create Input
        input_dict = {}
        if "inner_metrics" in sample:
            metrics = sample["inner_metrics"]
            if len(metrics) == len(INNER_NAMES):
                for i, name in enumerate(INNER_NAMES):
                    input_dict[name] = metrics[i]
            else:
                print(f"Warning: inner_metrics length mismatch. Expected {len(INNER_NAMES)}, got {len(metrics)}")
                continue
        else:
            continue
            
        # Create Output
        output_dict = {}
        for knob, config in knob_config.items():
            if knob in sample:
                val = sample[knob]
                label = get_label(val, config['min'], config['max'])
                output_dict[knob] = label
        
        # Meta
        meta = {}
        if "workload" in sample:
            # Example: "./oltp_workloads/ycsb/sample_ycsb_config104.xml"
            parts = sample["workload"].split('/')
            if len(parts) >= 3:
                meta["database"] = parts[-2] # ycsb
                meta["workload_name"] = parts[-1].replace('.xml', '')
        
        processed_sample = {
            "system": SYSTEM_PROMPT,
            "instruction": INSTRUCTION_TEXT,
            "input": json.dumps(input_dict, indent=2),
            "output": json.dumps(output_dict, indent=2),
            "meta": meta
        }
        processed_data.append(processed_sample)
        
    return processed_data

def main():
    print("Loading knob config...")
    knob_config = load_json(KNOB_CONFIG_PATH)
    
    print("Loading collected samples...")
    collected_samples = load_jsonl(COLLECTED_SAMPLES_PATH)
    print(f"Loaded {len(collected_samples)} collected samples.")
    
    print("Processing collected samples...")
    new_data = process_collected_samples(collected_samples, knob_config)
    print(f"Processed {len(new_data)} samples.")
    
    print("Loading existing training data...")
    if os.path.exists(EXISTING_TRAINING_DATA_PATH):
        existing_data = load_json(EXISTING_TRAINING_DATA_PATH)
        print(f"Loaded {len(existing_data)} existing samples.")
        # Update instruction for existing data
        for item in existing_data:
            item["system"] = SYSTEM_PROMPT
            item["instruction"] = INSTRUCTION_TEXT
    else:
        existing_data = []
        print("No existing training data found.")
        
    # Combine
    all_data = existing_data + new_data
    print(f"Total samples: {len(all_data)}")
    
    # Shuffle
    random.seed(42)
    random.shuffle(all_data)
    
    # Split
    split_idx = int(len(all_data) * 0.9) # 90% train, 10% test
    train_data = all_data[:split_idx]
    test_data = all_data[split_idx:]
    
    print(f"Train set size: {len(train_data)}")
    print(f"Test set size: {len(test_data)}")
    
    # Save
    print(f"Saving to {OUTPUT_TRAIN_PATH}...")
    with open(OUTPUT_TRAIN_PATH, 'w') as f:
        json.dump(train_data, f, indent=2)
        
    print(f"Saving to {OUTPUT_TEST_PATH}...")
    with open(OUTPUT_TEST_PATH, 'w') as f:
        json.dump(test_data, f, indent=2)
        
    print("Done!")

if __name__ == "__main__":
    main()
