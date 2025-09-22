import torch
import transformers
from transformers import AutoTokenizer

class E2ETuneBot:
    def __init__(self, model_path):
        self.model_id = model_path
        
        # Check if CUDA is available
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using device: {device}")
        
        if device == "cuda":
            print(f"GPU: {torch.cuda.get_device_name(0)}")
            print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
        
        # Configure model kwargs based on device
        model_kwargs = {
            "torch_dtype": torch.float16 if device == "cuda" else torch.float32,
            "low_cpu_mem_usage": True
        }
        
                # Add quantization for GPU
        if device == "cuda":
            from transformers import BitsAndBytesConfig
            
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,  # Match your model dtype
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4"
            )
            model_kwargs["quantization_config"] = quantization_config
            model_kwargs["device_map"] = "auto"
        
        self.pipeline = transformers.pipeline(
            "text-generation",
            model=self.model_id,
            model_kwargs=model_kwargs,
            trust_remote_code=True,
        )
        
        # Set up tokenizer
        if self.pipeline.tokenizer.pad_token is None:
            self.pipeline.tokenizer.pad_token = self.pipeline.tokenizer.eos_token
        
        self.terminators = [
            self.pipeline.tokenizer.eos_token_id,
        ]
  
    def get_response(self, query, max_tokens=4096, temperature=1.0, top_p=0.95):
        outputs = self.pipeline(
            query,
            max_new_tokens=max_tokens,
            eos_token_id=self.terminators,
            temperature=temperature,
            pad_token_id=self.pipeline.tokenizer.pad_token_id
        )
        response = outputs[0]["generated_text"]
        return response
    
    def single_prompt(self, prompt=None):
        if prompt is None:
            # Read prompt from file or use default
            try:
                with open("llm_prompt.txt", "r") as f:
                    prompt = f.read().strip()
                print(f"Loaded prompt: {prompt[:100]}..." if len(prompt) > 100 else f"Loaded prompt: {prompt}")
            except FileNotFoundError:
                print("llm_prompt.txt not found, using default prompt")
                prompt = "You are an expert in database; optimize database parameters for performance..."
        
        print("\nSending prompt to model...")
        response = self.get_response(prompt)
        print("\nGenerated response:")
        print(response)

        # strip the prompt from the response if it was included
        if response.startswith(prompt):
            response = response[len(prompt):].strip()
        
        # save the response to a file 
        with open("temp_response.txt", "w") as f:
            f.write(response)
        return response

def main():
    model_name = "springhxm/E2ETune"
    bot = E2ETuneBot(model_name)
    bot.single_prompt()

if __name__ == "__main__":
    main()