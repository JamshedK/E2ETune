# Setup

## Env setup

1. Create a conda environment with Python 3.8.20:
   ```bash
   conda create -n e2etune python=3.8.20
   conda activate e2etune
   ```
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Download and install Postgres 12.2:
   - Follow instructions at https://www.postgresql.org/download/linux/
   - Start the Postgres server after installation.
4. Install Java JDK 21:
   - On Ubuntu: `sudo apt install openjdk-21-jdk`

## Database setup

1. Create a database for your benchmark in Postgres:
   ```bash
   psql -U <your_user>
   CREATE DATABASE <benchmark_db>;
   ```
2. Load benchmark data as needed.

## Loading up the database

1. Go to the `scripts` folder.
2. Install BenchBase for Postgres:
   ```bash
   sh install_benchbase_postgres.sh
   ```
3. Edit the config file for your workload:
   - Open `benchbase/target/benchbase-postgres/config/postgres/<workload-config>.xml`
   - Update with your database and workload info.
4. Build and run the benchmark:
   ```bash
   sh build_benchmark.sh <database> <benchmark>
   # Example:
   sh build_benchmark.sh postgres tpch
   ```

## Collecting training data

1. Edit the `config/config.ini` file:
   - Update the `[database_config]` section with your database connection details (host, user, password, database name, etc).

2. Set your workload type and workload directory in `main.py` (lines 20-21):
   - Change `workload_type = 'tpch'` to your desired workload type.
   - Change `all = os.listdir('./olap_workloads')` to point to the correct workload directory

3. Run the main script to start data collection:
   ```bash
   python main.py --host <your_host> --database <database_name>
   ```
   - Example:
   ```bash
   python main.py --host localhost --database benchbase
   ```

---

This process will:
- Collect data for a single workload type and 13 workloads (interactions) within that type.
- For each workload, internal metrics will be collected and saved to `internal_metrics/<workload_name>_internal_metrics`.
- SMAC optimization will run for 100 tuning iterations, saving the runhistory to `smac_his/<workload_name>_smac.json`.
- For each runhistory, the best configuration will be selected as the output for that workload.
- Repeat for as many workload types as needed, with 13 workloads per type.

## Train LLM on database output

1. Create a new virtual environment (recommended: conda or venv)
2. Install requirements from `requirements_llm.txt`:
   ```bash
   pip install -r requirements_llm.txt
   ```
3. Follow project scripts to train LLM on database output.

## Running fine-tuned models

1. Download the fine-tuned 7B Mistral model:
   ```bash
   python download_model.py
   ```
   This will download and store the model locally.

2. Run `LLM_Tuning.py` to generate prompts:
   ```bash
   python LLM_Tuning.py --host <your_host> --database <database_name>
   ```
   This script will:
   - Run a given workload and collect internal metrics
   - Generate query plans and workload summary statistics
   - Create a comprehensive prompt combining all this information
   - Save the prompt to `<workload_name>_prompt.txt`

3. Run `llm_inference.py` to generate inference results:
   ```bash
   python llm_inference.py
   ```
   This will generate 8 different configuration samples and save them as `response_1.json` through `response_8.json`.

4. Test the generated configurations:
   ```bash
   python model_output_test.py
   ```
   This will test each of the 8 generated configurations on the database to evaluate their performance.

## Fine-tuning the LLM

### Data Preparation
1. Prepare the training data using the collected configurations and results from the previous steps.
2. The original repository contains code for data preparation - edit accordingly to format your data for fine-tuning.

### Fine-tuning Setup
1. Install LLaMA-Factory following the instructions at: https://github.com/hiyouga/LLaMA-Factory

2. Fine-tune the language model using the following command:
   ```bash
   deepspeed --include localhost:0,1,2,3,4,5,6,7 --master_port=12333 src/train.py \
       --deepspeed ds_config.json \
       --stage sft \
       --model_name_or_path /nvme/shared_ckpt/mistral-7b-instruct-v0.2 \
       --do_train \
       --dataset PO \
       --template mistral \
       --finetuning_type full \
       --output_dir /nvme/yzh/LLaMA-Factory/random \
       --overwrite_cache \
       --per_device_train_batch_size 1 \
       --gradient_accumulation_steps 4 \
       --lr_scheduler_type cosine \
       --report_to wandb \
       --logging_steps 1 \
       --save_strategy 'epoch' \
       --learning_rate 2e-5 \
       --num_train_epochs 10.0 \
       --plot_loss \
       --max_length 8192 \
       --cutoff_len 8192 \
       --bf16
   ```

   **Note:** Adjust the paths (`model_name_or_path`, `output_dir`) and GPU configuration (`--include localhost:0,1,2,3,4,5,6,7`) according to your setup.



