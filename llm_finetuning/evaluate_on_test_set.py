import json
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from knob_config.parse_knob_config import get_knobs

# Define label mapper
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

def load_model(model_path):
    print(f"Loading model from {model_path}...")
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    
    # Try loading with device_map="auto" first (requires accelerate)
    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_path, 
            device_map="auto", 
            torch_dtype=torch.float16,
            trust_remote_code=True
        )
    except Exception as e:
        print(f"Could not load with device_map='auto' (likely missing accelerate): {e}")
        print("Falling back to manual device placement...")
        model = AutoModelForCausalLM.from_pretrained(
            model_path, 
            torch_dtype=torch.float16,
            trust_remote_code=True
        )
        if torch.cuda.is_available():
            model = model.to("cuda")
            
    return tokenizer, model

def generate_response(model, tokenizer, instruction, input_data, expected_keys=None):
    # Construct prompt based on Qwen template or the one used in training
    # The training data has "instruction", "input", "output"
    # LLaMA-Factory with 'qwen' template usually formats it as:
    # <|im_start|>user\n{instruction}\n{input}<|im_end|>\n<|im_start|>assistant\n
    
    # We use the exact prompt format from training to ensure best performance
    prompt = f"<|im_start|>user\n{instruction}\n{input_data}<|im_end|>\n<|im_start|>assistant\n"
    
    inputs = tokenizer(prompt, return_tensors="pt")
    if torch.cuda.is_available():
        inputs = inputs.to("cuda")
        
    with torch.no_grad():
        outputs = model.generate(
            **inputs, 
            max_new_tokens=1024, 
            temperature=0.1, # Lower temperature for more deterministic output
            top_p=0.9,
            do_sample=True
        )
        
    response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
    
    return response.strip()

def parse_json_response(response_text):
    try:
        # Find the first '{' and last '}'
        start = response_text.find('{')
        end = response_text.rfind('}')
        if start != -1 and end != -1:
            json_str = response_text[start:end+1]
            return json.loads(json_str)
    except:
        pass
    return None

def calculate_mae(pred_config, true_config, knobs_detail):
    # Convert both to numeric
    # Note: convert_labels_to_numeric expects the config dict to have keys matching the knob names
    # and values as labels (e.g., "00% to 10%")
    
    # We need to handle potential key mismatches or missing keys
    
    # Helper to get numeric value directly
    def get_val(knob, label):
        if knob not in knobs_detail:
            return None
        detail = knobs_detail[knob]
        s1_length = (detail['max'] - detail['min']) / 10
        if s1_length == 0:
            return detail['default']
        
        if label not in label_mapper_s1:
            return None
            
        numeric = s1_length * (label_mapper_s1[label]) + s1_length / 2 
        if detail['type'] == 'integer':
            numeric = int(numeric + detail['min'])
        else:
            numeric = float(numeric + detail['min'])
        return numeric

    total_error = 0
    count = 0
    
    for knob, true_label in true_config.items():
        if knob in pred_config:
            pred_label = pred_config[knob]
            
            true_val = get_val(knob, true_label)
            pred_val = get_val(knob, pred_label)
            
            if true_val is not None and pred_val is not None:
                # Normalize error by range to make it comparable across knobs?
                # Or just raw difference. Let's do normalized error (0-1 scale)
                detail = knobs_detail[knob]
                rng = detail['max'] - detail['min']
                if rng > 0:
                    error = abs(pred_val - true_val) / rng
                    total_error += error
                    count += 1
            else:
                # Debugging: why is it None?
                # print(f"Skipping {knob}: true_val={true_val}, pred_val={pred_val}, true_label={true_label}, pred_label={pred_label}")
                pass
    
    if count == 0:
        print("Warning: No valid knobs compared found in prediction.")
        return 1.0 # Return max error if no valid knobs found
        
    return total_error / count

def evaluate_model(model_path, test_data, knobs_detail):
    tokenizer, model = load_model(model_path)
    
    total_mae = 0
    valid_samples = 0
    
    print(f"\nEvaluating {len(test_data)} samples...")
    
    for i, item in enumerate(test_data):
        instruction = item["instruction"]
        input_data = item["input"]
        true_output_str = item["output"]
        
        true_config = json.loads(true_output_str)
        
        pred_response = generate_response(model, tokenizer, instruction, input_data, expected_keys=knobs_detail.keys())
        pred_config = parse_json_response(pred_response)
        
        if pred_config:
            # Debug: print first sample's prediction
            if i == 0:
                print(f"Sample 1 Prediction Keys: {list(pred_config.keys())[:5]}...")
                print(f"Sample 1 Prediction Values: {list(pred_config.values())[:5]}...")
            
            mae = calculate_mae(pred_config, true_config, knobs_detail)
            print(f"Sample {i+1}: MAE = {mae:.4f}")
            total_mae += mae
            valid_samples += 1
        else:
            print(f"Sample {i+1}: Failed to parse JSON response")
            print(f"RAW RESPONSE: {pred_response[:500]}...") # Print first 500 chars
            
    avg_mae = total_mae / valid_samples if valid_samples > 0 else float('inf')
    print(f"Average MAE: {avg_mae:.4f}")
    print(f"Valid Samples: {valid_samples}/{len(test_data)}")
    
    # Cleanup
    del model
    del tokenizer
    torch.cuda.empty_cache()
    
    return avg_mae, valid_samples

def main():
    # Load test data
    test_file = "db_tuning_test.json"
    if not os.path.exists(test_file):
        print(f"Test file {test_file} not found!")
        return
        
    with open(test_file, 'r') as f:
        test_data = json.load(f)
        
    # Load knob details
    knobs_detail = get_knobs('../knob_config/knob_config_pg14.json')
    
    print("=== Evaluating Baseline Model ===")
    baseline_mae, baseline_valid = evaluate_model("Qwen/Qwen2.5-1.5B-Instruct", test_data, knobs_detail)
    
    print("\n=== Evaluating Fine-tuned Model ===")
    finetuned_mae, finetuned_valid = evaluate_model("finetuned_model", test_data, knobs_detail)
    
    print("\n=== Final Comparison ===")
    print(f"Baseline: MAE={baseline_mae:.4f}, Valid={baseline_valid}/{len(test_data)}")
    print(f"Fine-tuned: MAE={finetuned_mae:.4f}, Valid={finetuned_valid}/{len(test_data)}")
    
    if finetuned_valid == 0 and baseline_valid == 0:
        print("Both models failed to generate valid JSON output. The fine-tuning might need more epochs or a different learning rate.")
    elif baseline_mae == 0:
        print(f"Baseline MAE is 0. Cannot calculate percentage improvement.")
    elif finetuned_mae < baseline_mae:
        print(f"Improvement: {(baseline_mae - finetuned_mae) / baseline_mae * 100:.2f}%")
    else:
        print(f"Degradation: {(finetuned_mae - baseline_mae) / baseline_mae * 100:.2f}%")

if __name__ == "__main__":
    main()
