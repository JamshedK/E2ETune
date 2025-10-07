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
        
                # Add quantization for GPU - cleaner version
        if device == "cuda":
            model_kwargs["quantization_config"] = {
                "load_in_4bit": True,
                "bnb_4bit_compute_dtype": torch.float16, 
            }
            model_kwargs["device_map"] = "auto"

        self.pipeline = transformers.pipeline(
            "text-generation",
            model=self.model_id,
            model_kwargs=model_kwargs,
            trust_remote_code=True,
            use_fast=False,  # Add this line to avoid tiktoken conversion
        )
        
        # Set up tokenizer
        if self.pipeline.tokenizer.pad_token is None:
            self.pipeline.tokenizer.pad_token = self.pipeline.tokenizer.eos_token
        
        self.terminators = [
            self.pipeline.tokenizer.eos_token_id,
        ]
  

    def get_samples(self, query, num_samples=8, max_tokens=4096, temperature=1.0, top_p=0.95):
        """Generate multiple diverse samples via sampling."""
        samples = []
        for _ in range(num_samples):
            print(f"Generating sample {_ + 1}/{num_samples}...")
            outputs = self.pipeline(
                query,
                max_new_tokens=max_tokens,
                eos_token_id=self.terminators,
                temperature=temperature,
                top_p=top_p,
                do_sample=True,
                pad_token_id=self.pipeline.tokenizer.pad_token_id,
                length_penalty=1.0,  
                early_stopping=False,
            )
            text = outputs[0]["generated_text"]
            if text.startswith(query):
                text = text[len(query):].strip()
            
            # save the text into response_i.json file
            with open(f"response_{_ + 1}.json", "w") as f:
                f.write(text)
            samples.append(text)

        return samples

    def single_prompt(self, promptFile=None, num_samples=1):
        # Load prompt from a file if provided (default to llm_prompt.txt)
        if promptFile is None:
            promptFile = "llm_prompt.txt"

        try:
            with open(promptFile, "r") as f:
                prompt = f.read().strip()
            print(f"Loaded prompt from {promptFile}: {prompt[:100]}..." if len(prompt) > 100 else f"Loaded prompt from {promptFile}: {prompt}")
        except FileNotFoundError:
            print(f"{promptFile} not found, using default prompt")
            prompt = "You are an expert in database; optimize database parameters for performance..."

        if num_samples > 1:
            print(f"\nSampling {num_samples} responses (temperature=1.0)...")
            responses = self.get_samples(prompt, num_samples=num_samples, temperature=1.0)

            return responses


def main():
    model_name = "./local_model"
    bot = E2ETuneBot(model_name)
    bot.single_prompt(num_samples=8, promptFile='tpch_1_prompt.txt') 
    # bot.single_prompt(num_samples=8, promptFile='tpch_2_prompt.txt')

if __name__ == "__main__":
    main()