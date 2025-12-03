#!/bin/bash

# Export TinyLlama-1.1B-Chat model
# This script merges the LoRA adapter with the base model

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR/LLaMA-Factory" || exit

if ! command -v llamafactory-cli &> /dev/null
then
    echo "Error: llamafactory-cli not found."
    echo "Please activate your environment (conda activate DBfinetuning)"
    exit 1
fi

MODEL_NAME="TinyLlama/TinyLlama-1.1B-Chat-v1.0"
ADAPTER_PATH="saves/TinyLlama-1.1B/lora/sft"
EXPORT_DIR="../finetuned_model_TinyLlama"

echo "Exporting model..."
echo "Base Model: $MODEL_NAME"
echo "Adapter: $ADAPTER_PATH"
echo "Output Dir: $EXPORT_DIR"

llamafactory-cli export \
    --model_name_or_path $MODEL_NAME \
    --adapter_name_or_path $ADAPTER_PATH \
    --template llama2 \
    --finetuning_type lora \
    --export_dir $EXPORT_DIR \
    --export_size 2 \
    --export_device cpu \
    --export_legacy_format False

echo "Export complete! Model saved to $EXPORT_DIR"
