from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, VotingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import cross_val_score, train_test_split, KFold
from sklearn.metrics import r2_score
import json
import jsonlines
import joblib
import random
import numpy as np


def my_cross_val(model, data, database):
    scores = []
    k = 0
    best = 0
    while k < 10:
        X_train = []; X_test = []; y_train = []; y_test = []
        # Randomly select 3 workloads for testing
        test = random.sample(data.keys(), 3)

        for key in data.keys():
            tmp = data[key]
            if len(tmp) <= 10:  # Remove features dependency
                continue
            
            # normalizing qps 
            l = max([i[1] for i in tmp]) # best qps for this workload
            r = min([i[1] for i in tmp]) # worst qps for this workload
            
            if key not in test:
                X_train += [i[0] for i in tmp]  # Remove feature concatenation
                y_train += [((i[1] - r) / (l - r)) for i in tmp]
            else:
                X_test += [i[0] for i in tmp]   # Remove feature concatenation
                y_test += [((i[1] - r) / (l - r)) for i in tmp]
        
        try: 
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            score = r2_score(y_true=y_test, y_pred=y_pred)
        except: 
            score = 0
        
        if score > 0:
            scores.append(score)
            print(f"Fold {k} R^2 Score: {score:.4f}")
            k += 1
            if score > best:
                best = score
                model_filename = f'surrogate/{database}.pkl'
                joblib.dump(model, model_filename)

    mean_score = np.mean(scores)
    print(f"Mean R^2 Score: {mean_score:.4f}")

    return scores


def train_surrogate(database):
    print('training surrogate model...')
    knobs = json.load(open('knob_config/knob_config.json'))
    # Remove external features dependency
    # features = json.load(open(f'SuperWG/feature/{database}.json'))

    data = {}
    with jsonlines.open(f'offline_sample/offline_sample_{database}.jsonl', 'r') as f:
        for record in f:
            x = []
            
            # Add normalized knob values (44 features)
            for key in record.keys():
                if key == 'y' or key == 'workload' or key == 'tps' or key == 'inner_metrics': 
                    continue
                else:
                    detail = knobs[key]
                    if detail['max'] - detail['min'] != 0:
                        x.append((record[key] - detail['min']) / (detail['max'] - detail['min']))
                    else: 
                        continue
            
            # Add inner metrics (14 features)
            x += record['inner_metrics']
            
            # Total features: 44 knobs + 14 inner metrics = 58 features
            if record['workload'] in data.keys(): 
                data[record['workload']].append([x, record['y']])
            else: 
                data[record['workload']] = [[x, record['y']]]

    rf = RandomForestRegressor(n_estimators=500, random_state=42)
    gb = GradientBoostingRegressor(random_state=42)
    reg = VotingRegressor(estimators=[('gb', rf), ('rf', gb)])

    # 10-fold custom cross-validation
    my_cross_val(reg, data, database)

def train_surrogate_without_k_fold():

    print('training surrogate model...')
    knobs = json.load(open('knob_config/knob_config.json'))
    
    data = {}
    with jsonlines.open(f'smac_his/offline_sample_tpch.jsonl', 'r') as f:
        for record in f:
            x = []
            for key in record.keys():
                if key == 'y' or key == 'workload' or key == 'tps' or key == 'inner_metrics': 
                    continue
                else:
                    detail = knobs[key]
                    if detail['max'] - detail['min'] != 0:
                        x.append((record[key] - detail['min']) / (detail['max'] - detail['min']))
            
            x += record['inner_metrics']  # Add inner metrics
            tps = record['y'][0] 
            if record['workload'] in data.keys(): 
                data[record['workload']].append([x, tps])
            else: 
                data[record['workload']] = [[x, tps]]

    # Simple train/test split within the single workload
    all_data = []
    for key in data.keys():
        tmp = data[key]
        if len(tmp) <= 10:
            continue
        all_data += tmp
    print(f"Total samples: {len(all_data)}")

    X = [i[0] for i in all_data]
    y = [i[1] for i in all_data]

    print(f"Feature dimension: {len(X[0])}")
    
    # Normalize y values
    y_min, y_max = min(y), max(y)
    y_normalized = [(val - y_min) / (y_max - y_min) for val in y]
    
    # Simple 80/20 split
    split_idx = int(0.8 * len(X))
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y_normalized[:split_idx], y_normalized[split_idx:]

    print(f"Training samples: {len(X_train)}, Testing samples: {len(X_test)}")
    
    # Train model
    rf = RandomForestRegressor(n_estimators=500, random_state=42)
    gb = GradientBoostingRegressor(random_state=42)
    reg = VotingRegressor(estimators=[('gb', rf), ('rf', gb)])
    
    reg.fit(X_train, y_train)
    
    # Evaluate
    y_pred = reg.predict(X_test)
    score = r2_score(y_test, y_pred)
    print(f"R^2 Score: {score:.4f}")
    
    # Save model
    joblib.dump(reg, f'surrogate/tpch.pkl')


if __name__ == '__main__':
    train_surrogate_without_k_fold()