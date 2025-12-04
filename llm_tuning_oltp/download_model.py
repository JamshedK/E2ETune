from huggingface_hub import snapshot_download
import os

# Download model to local directory
model_path = "./local_model"
os.makedirs(model_path, exist_ok=True)

print("Downloading model...")
snapshot_download(
    repo_id="Mark237/db-tuning-randomdata-qwen2.5-1.5b",
    local_dir=model_path,
    local_dir_use_symlinks=False,
)
print(f"Model downloaded to {model_path}")