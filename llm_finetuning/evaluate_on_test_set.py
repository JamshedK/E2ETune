import argparse
import json
import os
import sys
import torch
import numpy as np
from tqdm import tqdm
from transformers import AutoTokenizer, AutoModelForCausalLM
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

# Define label mapper
label_mapper = {
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
# Inverse mapper for display
id2label = {v: k for k, v in label_mapper.items()}

def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate fine-tuned model on DB tuning test set")
    parser.add_argument("--model_path", type=str, default="/home/mark/projects/E2ETune/llm_finetuning/finetuned_model_Qwen2.5-1.5B", help="Path to the model or adapter")
    parser.add_argument("--test_data", type=str, default="db_tuning_test.json", help="Path to test data JSON")
    parser.add_argument("--batch_size", type=int, default=8, help="Batch size for inference")
    return parser.parse_args()

def load_model(model_path):
    print(f"Loading model from {model_path}...")
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    
    # Ensure padding side is left for batch generation
    tokenizer.padding_side = "left"
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_path, 
            device_map="auto", 
            torch_dtype=torch.float16,
            trust_remote_code=True
        )
    except Exception as e:
        print(f"Could not load with device_map='auto': {e}")
        print("Falling back to manual device placement...")
        model = AutoModelForCausalLM.from_pretrained(
            model_path, 
            torch_dtype=torch.float16,
            trust_remote_code=True
        )
        if torch.cuda.is_available():
            model = model.to("cuda")
            
    return tokenizer, model

def batch_generate(model, tokenizer, prompts):
    inputs = tokenizer(prompts, return_tensors="pt", padding=True, truncation=True)
    if torch.cuda.is_available():
        inputs = inputs.to("cuda")
        
    with torch.no_grad():
        outputs = model.generate(
            **inputs, 
            max_new_tokens=1024, 
            temperature=0.1,
            top_p=0.9,
            do_sample=True,
            pad_token_id=tokenizer.pad_token_id
        )
    
    # Decode only the new tokens
    responses = []
    for i, output in enumerate(outputs):
        response = tokenizer.decode(output[inputs.input_ids.shape[1]:], skip_special_tokens=True)
        responses.append(response.strip())
    return responses

def parse_json_response(response_text):
    try:
        start = response_text.find('{')
        end = response_text.rfind('}')
        if start != -1 and end != -1:
            json_str = response_text[start:end+1]
            return json.loads(json_str)
    except:
        pass
    return None

def evaluate_model(model_path, test_data_path, batch_size=8):
    if not os.path.exists(test_data_path):
        print(f"Test file {test_data_path} not found!")
        return

    with open(test_data_path, 'r') as f:
        test_data = json.load(f)

    tokenizer, model = load_model(model_path)
    
    y_true = []
    y_pred = []
    
    print(f"\nEvaluating {len(test_data)} samples with batch size {batch_size}...")
    
    valid_samples = 0
    parse_errors = 0
    
    # Process in batches
    for i in tqdm(range(0, len(test_data), batch_size), desc="Evaluating"):
        batch_items = test_data[i:i+batch_size]
        prompts = []
        true_configs = []
        
        for item in batch_items:
            system = item.get("system", "")
            instruction = item.get("instruction", "")
            input_data = item.get("input", "")
            true_output_str = item.get("output", "")
            
            # Construct prompt
            prompt = ""
            if system:
                prompt += f"<|im_start|>system\n{system}<|im_end|>\n"
            prompt += f"<|im_start|>user\n{instruction}\n{input_data}<|im_end|>\n<|im_start|>assistant\n"
            prompts.append(prompt)
            
            try:
                true_configs.append(json.loads(true_output_str))
            except:
                true_configs.append(None)
                print(f"Sample {i}: Error parsing ground truth JSON")

        # Generate for batch
        batch_responses = batch_generate(model, tokenizer, prompts)
        
        for j, pred_response in enumerate(batch_responses):
            true_config = true_configs[j]
            if true_config is None:
                continue
                
            pred_config = parse_json_response(pred_response)
            
            if pred_config:
                valid_samples += 1
                # Compare knob by knob
                for knob, true_label in true_config.items():
                    if knob in pred_config:
                        pred_label = pred_config[knob]
                        
                        if true_label in label_mapper and pred_label in label_mapper:
                            y_true.append(label_mapper[true_label])
                            y_pred.append(label_mapper[pred_label])
                        else:
                            if valid_samples <= 5:
                                print(f"DEBUG: Label mismatch for {knob}. True: '{true_label}', Pred: '{pred_label}'")
                    else:
                        if valid_samples <= 5:
                            print(f"DEBUG: Missing knob {knob} in prediction")
            else:
                parse_errors += 1
                if (i + j) < 5: # Print first few errors
                    print(f"Sample {i+j}: Failed to parse prediction: {pred_response[:100]}...")

    print(f"\nEvaluation Complete.")
    print(f"Valid JSON Responses: {valid_samples}/{len(test_data)}")
    print(f"Parse Errors: {parse_errors}")
    
    if len(y_true) > 0:
        print("\n=== Classification Report ===")
        target_names = [id2label[i] for i in range(len(label_mapper))]
        # Note: labels in y_true might not cover all classes, so we should be careful
        unique_labels = sorted(list(set(y_true) | set(y_pred)))
        target_names_subset = [id2label[i] for i in unique_labels]
        
        print(classification_report(y_true, y_pred, labels=unique_labels, target_names=target_names_subset))
        
        print("\n=== Confusion Matrix ===")
        cm = confusion_matrix(y_true, y_pred, labels=unique_labels)
        print(cm)
        
        acc = accuracy_score(y_true, y_pred)
        print(f"\nOverall Accuracy: {acc:.4f}")
    else:
        print("No valid comparisons found.")

    # Cleanup
    del model
    del tokenizer
    torch.cuda.empty_cache()

def main():
    args = parse_args()
    evaluate_model(args.model_path, args.test_data, args.batch_size)

if __name__ == "__main__":
    main()
