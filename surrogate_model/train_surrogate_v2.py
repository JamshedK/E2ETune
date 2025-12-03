"""
Surrogate model training with workload-level cross-validation.

Goal: Predict performance on UNSEEN workloads.
Method: Hold out entire workloads for testing (not random samples).
"""

from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, VotingRegressor
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score
import json
import jsonlines
import joblib
import numpy as np
from collections import defaultdict


def load_data_by_workload(jsonl_path, knob_config_path):
    """Load data grouped by workload."""
    knobs = json.load(open(knob_config_path))
    
    data = defaultdict(list)  # workload -> [(x, y), ...]
    
    with jsonlines.open(jsonl_path, 'r') as f:
        for record in f:
            x = []
            # Normalized knob values
            for key in record.keys():
                if key in ('y', 'workload', 'tps', 'inner_metrics', 'config_id'):
                    continue
                detail = knobs[key]
                if detail['max'] - detail['min'] != 0:
                    x.append((record[key] - detail['min']) / (detail['max'] - detail['min']))
            
            # Add inner metrics
            x += record['inner_metrics']
            
            y_val = record['y'][0]  # throughput
            data[record['workload']].append((x, y_val))
    
    return data


def train_surrogate():
    print('Loading data...')
    data = load_data_by_workload('collected_samples.jsonl', '../knob_config/knob_config_pg14.json')
    
    workloads = list(data.keys())
    n_workloads = len(workloads)
    total_samples = sum(len(data[wl]) for wl in workloads)
    n_features = len(data[workloads[0]][0][0])
    
    print(f'Loaded {total_samples} samples from {n_workloads} workloads, {n_features} features')
    
    # Collect all y values for global stats
    all_y = []
    for wl in workloads:
        all_y.extend([sample[1] for sample in data[wl]])
    y_min, y_max = min(all_y), max(all_y)
    print(f'y range: [{y_min:.2f}, {y_max:.2f}]')
    
    # Workload-level K-fold CV
    # With 62 workloads, 10-fold means ~6 workloads held out per fold
    n_folds = 10
    kf = KFold(n_splits=n_folds, shuffle=True, random_state=42)
    scores = []
    
    print(f'\nRunning {n_folds}-fold workload-level CV (~{n_workloads//n_folds} workloads per test fold)...')
    
    for fold, (train_idx, test_idx) in enumerate(kf.split(workloads)):
        train_workloads = [workloads[i] for i in train_idx]
        test_workloads = [workloads[i] for i in test_idx]
        
        X_train, y_train = [], []
        X_test, y_test = [], []
        
        # Gather training data
        for wl in train_workloads:
            for x, y in data[wl]:
                X_train.append(x)
                # Global normalization (same scale for all workloads)
                y_train.append((y - y_min) / (y_max - y_min))
        
        # Gather test data
        for wl in test_workloads:
            for x, y in data[wl]:
                X_test.append(x)
                y_test.append((y - y_min) / (y_max - y_min))
        
        X_train, y_train = np.array(X_train), np.array(y_train)
        X_test, y_test = np.array(X_test), np.array(y_test)
        
        # Train model
        model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        model.fit(X_train, y_train)
        
        y_pred = model.predict(X_test)
        score = r2_score(y_test, y_pred)
        scores.append(score)
        
        print(f'Fold {fold+1}/{n_folds}: train={len(train_workloads)} wl ({len(X_train)} samples), '
              f'test={len(test_workloads)} wl ({len(X_test)} samples), R²={score:.4f}')
    
    print(f'\nMean R²: {np.mean(scores):.4f} (+/- {np.std(scores):.4f})')
    
    # Train final model on all data
    print('\nTraining final model on all data...')
    X_all, y_all = [], []
    for wl in workloads:
        for x, y in data[wl]:
            X_all.append(x)
            y_all.append((y - y_min) / (y_max - y_min))
    
    X_all, y_all = np.array(X_all), np.array(y_all)
    
    final_model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
    final_model.fit(X_all, y_all)
    
    # Save model and normalization params
    joblib.dump({
        'model': final_model,
        'y_min': y_min,
        'y_max': y_max
    }, 'surrogate.pkl')
    print('Saved to surrogate.pkl')
    
    return scores


if __name__ == "__main__":
    train_surrogate()
