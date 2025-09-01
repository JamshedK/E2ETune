import argparse
from config import parse_config
import os
from tune import tune

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=str, default='localhost', help='the database host')
    parser.add_argument('--database', type=str, default='benchbase', help='workload file')
    cmd = parser.parse_args()

    # Load configuration file
    args = parse_config.parse_args("config/config.ini")
    # print(args)
    # args['benchmark_config']['workload_path'] = 'SuperWG/res/gpt_workloads/' + cmd.workload
    args['database_config']['database'] = cmd.database
    args['tuning_config']['offline_sample'] += cmd.host
    print(args)

    all = os.listdir('./olap_workloads')
    workload_type = 'tpch'
    workloads = [i for i in all if i.startswith(workload_type)]

    for idx in range(0, 1):
        print("Begin tuning for workload: ", idx)
        args['benchmark_config']['workload_path'] = './olap_workloads/' + workloads[idx]
        try:
            tune(workload_file=workloads[idx], args=args)
            break
            # print(f'train surrogate model for {workloads[idx]}')
        except Exception as e:
            print(f'occur {e}')
            continue
        break
    