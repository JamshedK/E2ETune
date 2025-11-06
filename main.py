from config import parse_config
import os
from tune import tune

if __name__ == '__main__':
    # Load configuration file
    args = parse_config.parse_args("config/config.ini")
    print(args)

    # Get workload path from config
    workload_base_path = args['benchmark_config']['workload_path']
    workload_type = args['benchmark_config']['benchmark']
    benchmark_type = args['benchmark_config']['type']
    
    all = os.listdir('./' + workload_base_path + '/')
    
    # Filter based on benchmark type
    if benchmark_type == 'oltp':
        workloads = sorted([i for i in all if i.startswith(f'sample_{workload_type}_config') and i.endswith('.xml') and i != f'sample_{workload_type}_config.xml'])
    else:
        workloads = sorted([i for i in all if i.startswith(workload_type)])

    for idx in range(0, 1):
        print("Begin tuning for workload:", idx)
        full_workload_path = os.path.join('./', workload_base_path, workloads[idx])
        print(f'tune for workload: {full_workload_path}')
        try:
            tune(workload_file=full_workload_path, args=args)
            break
        except Exception as e:
            print(f'occur {e}')
            continue
        break
