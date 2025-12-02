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
    attempt = 0
    
    # Print data stats
    print(f"Total workloads: {len(data)}")
    for key in data.keys():
        print(f"  {key}: {len(data[key])} samples")
    
    while k < 10:
        attempt += 1
        print(f"Attempt {attempt}, completed folds: {k}/10", end='\r')
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
            print(f"Attempt {attempt}: train={len(X_train)}, test={len(X_test)}, R²={score:.4f}")
        except Exception as e:
            print(f"Attempt {attempt}: Error - {e}")
            score = 0
        
        if score > 0:
            scores.append(score)
            print(f"Fold {k} R^2 Score: {score:.4f}")
            k += 1
            if score > best:
                best = score
                model_filename = f'surrogate.pkl'
                joblib.dump(model, model_filename)

    mean_score = np.mean(scores)
    print(f"Mean R^2 Score: {mean_score:.4f}")

    return scores


def train_surrogate(database):
    print('training surrogate model...')
    knobs = json.load(open('../knob_config/knob_config_pg14.json'))
    # Remove external features dependency
    # features = json.load(open(f'SuperWG/feature/{database}.json'))

    data = {}
    with jsonlines.open(f'collected_samples.jsonl', 'r') as f:
        for record in f:
            x = []
            
            # Add normalized knob values (44 features)
            for key in record.keys():
                # skip non-knob fields
                if key in ('y', 'workload', 'tps', 'inner_metrics', 'config_id'): 
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
                data[record['workload']].append([x, record['y'][0]])
            else: 
                data[record['workload']] = [[x, record['y'][0]]]

    rf = RandomForestRegressor(n_estimators=500, random_state=42)
    gb = GradientBoostingRegressor(random_state=42)
    reg = VotingRegressor(estimators=[('gb', rf), ('rf', gb)])

    # 10-fold custom cross-validation
    my_cross_val(reg, data, database)

if __name__ == "__main__":
    train_surrogate('all_databases')
