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

   Or 
   ```bash
   sudo apt install -y postgresql-common
   sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh
   sudo apt install postgresql-12
   sudo systemctl enable postgresql
   sudo systemctl start postgresql
   ```
   - to check that the server started
   ```bash
   sudo systemctl status postgresql
   ```
   - to stop when finsihed
   ```bash
   sudo systemctl stop postgresql
   ```

4. Install Java JDK 21:
   - On Ubuntu: `sudo apt install openjdk-21-jdk`

## Database setup

1. Create a database for your benchmark in Postgres:
   ```bash
   psql -U <your_user>
   CREATE DATABASE <benchmark_db>;
   ```

   OR

   ```bash
   sudo -u postgres createuser myuser
   sudo -u postgres createdb mydb -O myuser
   psql -U myuser -d mydb
   ```

2. Load benchmark data as needed.

## Loading up the database

1. Go to the `scripts` folder.
2. Install BenchBase for your database:
   ```bash
   sh install_benchbase.sh <database>
   # Example:
   sh install_benchbase.sh postgres
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

We use LLaMA-Factory to fine-tune a Qwen2.5-1.5B-Instruct model using LoRA. All fine-tuning related files are located in the `llm_finetuning/` directory.

### 1. Setup Environment
Create a new environment for fine-tuning (separate from the main E2ETune environment):

```bash
conda create -n DBfinetuning python=3.10
conda activate DBfinetuning
pip install torch transformers peft datasets
```

Install LLaMA-Factory:
```bash
cd llm_finetuning
git clone https://github.com/hiyouga/LLaMA-Factory.git
cd LLaMA-Factory
pip install -e .
cd ..
```

### 2. Prepare Data
Process the collected surrogate model data and existing training data into the format required for fine-tuning. This script normalizes knob values into percentage buckets and creates train/test splits.

```bash
python process_data.py
```
This generates `db_tuning_train.json` and `db_tuning_test.json`.

### 3. Configure Training
Run the setup script to copy the data to LLaMA-Factory and generate the training script.

```bash
python setup_finetuning.py
```

### 4. Run Fine-tuning
Execute the generated shell script to start training. This script is optimized for a single GPU with ~12GB VRAM (Batch size 1, Gradient Accumulation 16).

```bash
./run_finetune.sh
```
The fine-tuned adapter will be saved in `llm_finetuning/LLaMA-Factory/saves/Qwen2.5-1.5B/lora/sft`.

### 5. Evaluation
To evaluate the model on the test set without running a database:

```bash
python evaluate_on_test_set.py
```
This script compares the JSON output of the baseline model vs. the fine-tuned model against the ground truth in `db_tuning_test.json`.

### 6. Export Model (Optional)
To merge the LoRA adapter with the base model for easier inference:

```bash
cd LLaMA-Factory
llamafactory-cli export \
    --model_name_or_path Qwen/Qwen2.5-1.5B-Instruct \
    --adapter_name_or_path saves/Qwen2.5-1.5B/lora/sft \
    --template qwen \
    --finetuning_type lora \
    --export_dir ../finetuned_model \
    --export_size 2 \
    --export_device cpu \
    --export_legacy_format False
```




