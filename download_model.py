from huggingface_hub import snapshot_download
import os

# Download model to local directory
model_path = "./local_model"
os.makedirs(model_path, exist_ok=True)

print("Downloading model...")
snapshot_download(
    repo_id="springhxm/E2ETune",
    local_dir=model_path,
    local_dir_use_symlinks=False,
    ignore_patterns=["*.bin"],  # Skip pytorch_model.bin files
)
print(f"Model downloaded to {model_path}")