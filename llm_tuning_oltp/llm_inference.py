import torch
import transformers
import json
import os

class E2ETuneBot:
    def __init__(self, model_path):
        print(f"Initializing E2ETuneBot with model: {model_path}")
        self.model_id = model_path
        
        # Check if CUDA is available
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using device: {device}")
        
        if device == "cuda":
            print(f"GPU: {torch.cuda.get_device_name(0)}")
            print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
        
        print("Setting up model configuration...")
        # Configure model kwargs based on device
        model_kwargs = {
            "torch_dtype": torch.float16 if device == "cuda" else torch.float32,
            "low_cpu_mem_usage": True
        }
        
        # Add device map for GPU
        if device == "cuda":
            model_kwargs["device_map"] = "auto"

        print("Loading transformers pipeline... (this may take several minutes)")
        try:
            self.pipeline = transformers.pipeline(
                "text-generation",
                model=self.model_id,
                model_kwargs=model_kwargs,
                trust_remote_code=True,
                use_fast=False,
            )
            print("✓ Pipeline loaded successfully!")
        except Exception as e:
            print(f"✗ Pipeline loading failed: {e}")
            raise
        
        print("Setting up tokenizer...")
        # Set up tokenizer
        if self.pipeline.tokenizer.pad_token is None:
            self.pipeline.tokenizer.pad_token = self.pipeline.tokenizer.eos_token
        
        self.terminators = [
            self.pipeline.tokenizer.eos_token_id,
        ]

    def format_qwen_prompt(self, prompt_data):
        """Format prompt using Qwen chat template."""
        system = prompt_data.get("system", "")
        instruction = prompt_data.get("instruction", "")
        input_data = prompt_data.get("input", "")
        
        prompt = ""
        if system:
            prompt += f"<|im_start|>system\n{system}<|im_end|>\n"
        prompt += f"<|im_start|>user\n{instruction}\n{input_data}<|im_end|>\n<|im_start|>assistant\n"
        
        return prompt

    def get_samples(self, query, num_samples=8, max_tokens=2048, temperature=1.0, top_p=0.95, workload_name="output"):
        """Generate multiple diverse samples via sampling."""
        samples = []
        for i in range(num_samples):
            print(f"Generating sample {i + 1}/{num_samples}...")
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
            
            # Save with workload name
            # make a directory for the workload if not exists
            os.makedirs("responses", exist_ok=True)
            output_file = os.path.join("responses", f"{workload_name}_response_{i + 1}.json")
            with open(output_file, "w") as f:
                f.write(text)
            print(f"  Saved to: {output_file}")
            samples.append(text)

        return samples

    def run_prompt(self, prompt_file, num_samples=1):
        """Load JSON prompt file, apply Qwen template, and run inference."""
        
        # Load JSON prompt
        try:
            with open(prompt_file, "r") as f:
                prompt_data = json.load(f)
            print(f"Loaded prompt from {prompt_file}")
        except FileNotFoundError:
            print(f"{prompt_file} not found!")
            return None
        except json.JSONDecodeError:
            print(f"{prompt_file} is not valid JSON!")
            return None
        
        # Get workload name from meta or filename
        workload_name = prompt_data.get("meta", {}).get("workload_name", 
                                                          os.path.basename(prompt_file).replace("_prompt.json", ""))
        print(f"Workload: {workload_name}")
        
        # Format with Qwen chat template
        formatted_prompt = self.format_qwen_prompt(prompt_data)
        print(f"Formatted prompt preview: {formatted_prompt[:200]}...")
        
        # Generate samples
        print(f"\nGenerating {num_samples} response(s)...")
        responses = self.get_samples(formatted_prompt, num_samples=num_samples, 
                                      temperature=1.0, workload_name=workload_name)
        
        return responses


def main():
    model_name = "./local_model"
    bot = E2ETuneBot(model_name)
    
    # Run with JSON prompt file
    prompt_file = "prompts/sample_tpcc_config13_prompt.json"
    bot.run_prompt(prompt_file, num_samples=2)


if __name__ == "__main__":
    main()