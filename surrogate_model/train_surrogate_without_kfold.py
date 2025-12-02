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