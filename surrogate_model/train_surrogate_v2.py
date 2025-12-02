from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score
import json
import jsonlines
import joblib
import numpy as np


def load_data(jsonl_path, knob_config_path):
    """Load and prepare data for training."""
    knobs = json.load(open(knob_config_path))
    
    X, y = [], []
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
            
            X.append(x)
            y.append(record['y'][0])  # throughput
    
    return np.array(X), np.array(y)


def train_surrogate():
    print('Loading data...')
    X, y = load_data('collected_samples.jsonl', '../knob_config/knob_config_pg14.json')
    print(f'Loaded {len(X)} samples, {X.shape[1]} features')
    
    # Normalize y globally (optional - can comment out)
    y_min, y_max = y.min(), y.max()
    # y_norm = (y - y_min) / (y_max - y_min)
    # print(f'y range: [{y_min:.2f}, {y_max:.2f}]')
    y_norm = y  # No normalization
    
    # Model
    model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
    
    # Standard 10-fold CV
    kf = KFold(n_splits=10, shuffle=True, random_state=42)
    scores = []
    
    print('\nRunning 10-fold cross-validation...')
    for fold, (train_idx, test_idx) in enumerate(kf.split(X)):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y_norm[train_idx], y_norm[test_idx]
        
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        score = r2_score(y_test, y_pred)
        scores.append(score)
        print(f'Fold {fold+1}/10: R² = {score:.4f}')
    
    print(f'\nMean R²: {np.mean(scores):.4f} (+/- {np.std(scores):.4f})')
    
    # Train final model on all data
    print('\nTraining final model on all data...')
    model.fit(X, y_norm)
    joblib.dump(model, 'surrogate.pkl')
    print('Saved to surrogate.pkl')
    
    return scores


if __name__ == "__main__":
    train_surrogate()
