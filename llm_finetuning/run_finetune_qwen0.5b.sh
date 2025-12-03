#!/bin/bash

# Example: Fine-tune Qwen2.5-0.5B-Instruct
# This script automatically navigates to the LLaMA-Factory directory

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR/LLaMA-Factory" || exit

if ! command -v llamafactory-cli &> /dev/null
then
    echo "Error: llamafactory-cli not found."
    echo "Please install LLaMA-Factory in editable mode first:"
    echo "  cd LLaMA-Factory"
    echo "  pip install -e ."
    exit 1
fi

MODEL_NAME="Qwen/Qwen2.5-0.5B-Instruct"

llamafactory-cli train \
    --stage sft \
    --do_train \
    --model_name_or_path $MODEL_NAME \
    --dataset db_tuning_train \
    --eval_dataset db_tuning_test \
    --template qwen \
    --finetuning_type lora \
    --lora_target all \
    --output_dir saves/Qwen2.5-0.5B/lora/sft \
    --overwrite_output_dir \
    --per_device_train_batch_size 2 \
    --per_device_eval_batch_size 2 \
    --gradient_accumulation_steps 8 \
    --learning_rate 1e-4 \
    --num_train_epochs 3.0 \
    --logging_steps 10 \
    --save_steps 100 \
    --eval_strategy steps \
    --eval_steps 50 \
    --plot_loss \
    --fp16
