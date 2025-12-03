from config import parse_config
import os
import subprocess
import time
from tune import tune

def recreate_database(database_name):
    # Recover postgres and recreate database from template
    subprocess.run(['bash', 'scripts/recover_postgres.sh'])
    subprocess.run(['bash', 'scripts/copy_db_from_template.sh', database_name])
    
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

    # print start time in unix seconds
    print("Start time (unix seconds):", int(time.time()))
    # for idx in range(4, 13):
    #     print("Begin tuning for workload:", idx)
    #     full_workload_path = os.path.join('./', workload_base_path, workloads[idx])
    #     print(f'tune for workload: {full_workload_path}')
    #     try:
    #         # print the star time for each workload
    #         print("Start time for workload (unix seconds):", int(time.time()))
    #         recreate_database(args['database_config']['database'])
    #         tune(workload_file=full_workload_path, args=args)
    #         # print the end time for each workload
    #         print("End time for workload (unix seconds):", int(time.time()))
    #     except Exception as e:
    #         print(f'occur {e}')
    #         continue
    # using the surrogate model to tune the remaining of the workloads
    use_surrogate = True
    for idx in range(13, 100):
        print("Begin tuning for workload with surrogate model:", idx)
        full_workload_path = os.path.join('./', workload_base_path, workloads[idx])
        print(f'tune for workload: {full_workload_path}')
        try:
            # print the star time for each workload
            print("Start time for workload (unix seconds):", int(time.time()))
            # recreate_database(args['database_config']['database'])
            tune(workload_file=full_workload_path, args=args, use_surrogate=use_surrogate)
            # print the end time for each workload
            print("End time for workload (unix seconds):", int(time.time()))
        except Exception as e:
            print(f'occur {e}')
            continue

    
    # print end time in unix seconds
    print("End time (unix seconds):", int(time.time()))