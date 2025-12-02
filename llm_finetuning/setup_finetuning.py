import json
import os
import shutil
import random

def setup_llama_factory():
    # 1. Define paths
    workspace_root = os.getcwd()
    llama_factory_dir = os.path.join(workspace_root, "LLaMA-Factory")
    data_dir = os.path.join(llama_factory_dir, "data")
    source_data = os.path.join(workspace_root, "training_data.json")
    
    # Check if LlamaFactory exists
    if not os.path.exists(llama_factory_dir):
        print("Error: LLaMA-Factory directory not found. Please clone it first:")
        print("git clone https://github.com/hiyouga/LLaMA-Factory.git")
        return

    # 2. Copy training data
    train_file = "db_tuning_train.json"
    test_file = "db_tuning_test.json"
    
    if os.path.exists(train_file) and os.path.exists(test_file):
        print(f"Found pre-processed data: {train_file} and {test_file}")
        shutil.copy(train_file, os.path.join(data_dir, train_file))
        shutil.copy(test_file, os.path.join(data_dir, test_file))
        print(f"Copied {train_file} and {test_file} to {data_dir}")
    elif os.path.exists(source_data):
        print(f"Reading data from {source_data}...")
        with open(source_data, 'r') as f:
            all_data = json.load(f)
        
        # Shuffle data to ensure random distribution
        random.seed(42) # Fixed seed for reproducibility
        random.shuffle(all_data)
        
        # Split 90% Train, 10% Test
        split_idx = int(len(all_data) * 0.9)
        train_data = all_data[:split_idx]
        test_data = all_data[split_idx:]
        
        with open(os.path.join(data_dir, train_file), 'w') as f:
            json.dump(train_data, f, indent=2)
            
        with open(os.path.join(data_dir, test_file), 'w') as f:
            json.dump(test_data, f, indent=2)
            
        print(f"Split data into {len(train_data)} training and {len(test_data)} testing examples.")
    else:
        print(f"Error: Could not find {train_file}/{test_file} or {source_data}")
        return

    # 3. Update dataset_info.json
    dataset_info_path = os.path.join(data_dir, "dataset_info.json")
    
    with open(dataset_info_path, 'r') as f:
        dataset_info = json.load(f)
        
    # Add our dataset definitions
    dataset_info["db_tuning_train"] = {
        "file_name": train_file,
        "columns": {
            "prompt": "instruction",
            "query": "input",
            "response": "output"
        }
    }
    
    dataset_info["db_tuning_test"] = {
        "file_name": test_file,
        "columns": {
            "prompt": "instruction",
            "query": "input",
            "response": "output"
        }
    }
    
    with open(dataset_info_path, 'w') as f:
        json.dump(dataset_info, f, indent=2)
        
    print("Updated dataset_info.json with 'db_tuning_train' and 'db_tuning_test' datasets.")
    
    # 4. Create a training script for 1B models
    create_training_script(workspace_root)

def create_training_script(root_dir):
    script_content = """#!/bin/bash

# Example: Fine-tune Qwen2.5-1.5B-Instruct (Open alternative to Llama-3.2)
# Make sure you are inside the LLaMA-Factory directory

if ! command -v llamafactory-cli &> /dev/null
then
    echo "Error: llamafactory-cli not found."
    echo "Please install LLaMA-Factory in editable mode first:"
    echo "  cd LLaMA-Factory"
    echo "  pip install -e ."
    exit 1
fi

MODEL_NAME="Qwen/Qwen2.5-1.5B-Instruct"

llamafactory-cli train \\
    --stage sft \\
    --do_train \\
    --model_name_or_path $MODEL_NAME \\
    --dataset db_tuning_train \\
    --eval_dataset db_tuning_test \\
    --template qwen \\
    --finetuning_type lora \\
    --lora_target all \\
    --output_dir saves/Qwen2.5-1.5B/lora/sft \\
    --overwrite_output_dir \\
    --per_device_train_batch_size 1 \\
    --per_device_eval_batch_size 1 \\
    --gradient_accumulation_steps 16 \\
    --learning_rate 1e-4 \\
    --num_train_epochs 3.0 \\
    --logging_steps 10 \\
    --save_steps 100 \\
    --eval_strategy steps \\
    --eval_steps 50 \\
    --plot_loss \\
    --fp16
"""
    script_path = os.path.join(root_dir, "run_finetune.sh")
    with open(script_path, 'w') as f:
        f.write(script_content)
    os.chmod(script_path, 0o755)
    print(f"Created training script at {script_path}")
    print("\\nIMPORTANT: You must install LLaMA-Factory before running the script:")
    print("  cd LLaMA-Factory")
    print("  pip install -e .")

if __name__ == "__main__":
    setup_llama_factory()
