#!/bin/bash
### Some common partitions
##SBATCH --partition=gpu_a100
##SBATCH --partition=sooner_gpu_test_ada
##SBATCH --partition=sooner_gpu_test
#SBATCH --partition=gpu
##SBATCH --partition=debug_gpu # This partition is currently selected.
#
#SBATCH --gres=gpu:1
##SBATCH --cpus-per-task=64
#SBATCH --cpus-per-task=20
##SBATCH --mem=32G
#SBATCH --mem=32G
##SBATCH --time=12:00:00
##SBATCH --time=00:20:00
#SBATCH --time=00:20:00
#SBATCH --job-name=llm_inference
#SBATCH --mail-user=jamshed.k@ou.edu
#SBATCH --mail-type=ALL
#SBATCH --chdir=/scratch/cs529314/E2ETune/
#SBATCH --output=results/llm_inference_%j.out
#SBATCH --error=results/llm_inference_%j.err

#################################################

# Exit on any error
set -e

export MAMBA_ROOT_PREFIX="/scratch/cs529314/micromamba"
MM="/scratch/cs529314/micromamba/bin/micromamba"
eval "$("$MM" shell hook -s bash)"

echo "Activating environment..."
micromamba activate e2e_env

echo "Python version:"
python -V

echo "Starting inference..."
python llm_inference.py

echo "Done."