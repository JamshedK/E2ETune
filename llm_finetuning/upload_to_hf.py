import argparse
import os
from huggingface_hub import HfApi, create_repo

def upload_model(model_path, repo_name, token=None):
    api = HfApi(token=token)
    
    try:
        user_info = api.whoami()
        username = user_info["name"]
    except Exception as e:
        print("Error: Not logged in. Please run 'huggingface-cli login' or provide a token.")
        return

    repo_id = f"{username}/{repo_name}"
    
    print(f"Preparing to upload to {repo_id}...")
    
    # Create repo if it doesn't exist
    try:
        create_repo(repo_id, repo_type="model", exist_ok=True, token=token)
        print(f"Repository {repo_id} is ready.")
    except Exception as e:
        print(f"Error creating/accessing repo: {e}")
        return

    if not os.path.exists(model_path):
        print(f"Error: Model path '{model_path}' does not exist.")
        return

    print(f"Uploading contents of {model_path}...")
    try:
        api.upload_folder(
            folder_path=model_path,
            repo_id=repo_id,
            repo_type="model"
        )
        print(f"\nSuccess! Model uploaded to: https://huggingface.co/{repo_id}")
    except Exception as e:
        print(f"Error during upload: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload a model to Hugging Face Hub")
    parser.add_argument("--model_path", type=str, required=True, help="Path to the local model folder")
    parser.add_argument("--repo_name", type=str, required=True, help="Name of the repository to create/use on HF")
    parser.add_argument("--token", type=str, help="Hugging Face token (optional if logged in via CLI)")
    
    args = parser.parse_args()
    upload_model(args.model_path, args.repo_name, args.token)
