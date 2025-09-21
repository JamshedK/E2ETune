from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

# Force CPU usage
device = "cpu"
torch.set_num_threads(4)  # Optimize CPU usage

# Load model and tokenizer for CPU
model_name = "springhxm/E2ETune"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float32,  # Use float32 for CPU
    device_map=None,  # Don't use device mapping
    low_cpu_mem_usage=True  # Optimize CPU memory usage
)

# Move model to CPU explicitly
model = model.to(device)

# Set pad token if not exists
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

def generate_response(prompt, max_length=1024, temperature=0.7):
    """Generate response using CPU only"""
    
    print("Tokenizing input...")
    # Tokenize input
    inputs = tokenizer(
        prompt, 
        return_tensors="pt", 
        truncation=True, 
        max_length=1024,  # Smaller for CPU
        padding=True
    )
    
    # Ensure tensors are on CPU
    inputs = {k: v.to(device) for k, v in inputs.items()}
    
    print("Generating response (this may take a while on CPU)...")
    # Generate response
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_length=max_length,
            temperature=temperature,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
            num_return_sequences=1,
            early_stopping=True
        )
    
    # Decode response
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    # Remove the input prompt from response
    # response = response[len(prompt):].strip()
    
    return response

def main():
    """Main inference function for CPU"""
    
    print("Running inference on CPU...")
    print(f"PyTorch is using {torch.get_num_threads()} CPU threads")
    
    # Read prompt from file
    try:
        with open('temp_prompt.txt', 'r', encoding='utf-8') as f:
            prompt = f.read().strip()
        print("Loaded prompt from temp_prompt.txt")
    except FileNotFoundError:
        print("temp_prompt.txt not found! Creating example prompt...")
        
    print(f"Prompt length: {len(prompt)} characters")
    print("\n" + "="*50)
    print("PROMPT:")
    print("="*50)
    print(prompt[:200] + "..." if len(prompt) > 200 else prompt)
    print("\n" + "="*50)
    print("GENERATING RESPONSE (CPU mode - this will be slower)...")
    print("="*50)
    
    # Generate response
    try:
        response = generate_response(prompt, max_length=2000)  # Smaller for CPU
        
        print("RESPONSE:")
        print("="*50)
        print(response)
        print("="*50)
        
        # Save response
        with open('llm_response.txt', 'w') as f:
            f.write(response)
        print("\nResponse saved to llm_response.txt")
        
    except Exception as e:
        print(f"Error during generation: {e}")
        print("CPU inference can be slow and memory intensive")

if __name__ == "__main__":
    main()