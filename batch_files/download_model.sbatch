#!/bin/bash
### Some common partitions
##SBATCH --partition=gpu_a100
##SBATCH --partition=sooner_gpu_test_ada
##SBATCH --partition=sooner_gpu_test
##SBATCH --partition=gpu
#SBATCH --partition=debug_gpu # This partition is currently selected.
#
#SBATCH --gres=gpu:1
##SBATCH --cpus-per-task=64
#SBATCH --cpus-per-task=20
##SBATCH --mem=32G
#SBATCH --mem=16G
##SBATCH --time=12:00:00
##SBATCH --time=00:20:00
#SBATCH --time=00:20:00
#SBATCH --job-name=download_model
##SBATCH --mail-user=jamshed.k@ou.edu
##SBATCH --mail-type=ALL
#SBATCH --chdir=/scratch/cs529314/E2ETune/
#SBATCH --output=results/download_model_%j.out
#SBATCH --error=results/download_model_%j.err

#################################################

## NOTE, make sure you change your directory!

export MAMBA_ROOT_PREFIX="/home/cs529314/micromamba"
MM="/home/cs529314/micromamba/bin/micromamba"
eval "$("$MM" shell hook -s bash)"

echo "Activating environment..."
micromamba activate e2e_env

echo "Python version:"
python -V

echo "Starting model download..."
python download_model.py

echo "Done."
