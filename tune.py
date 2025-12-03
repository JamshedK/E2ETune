import os
import time
import json
import json
from knob_config import parse_knob_config
import numpy as np
from Database import Database
from smac.configspace import ConfigurationSpace
from smac.runhistory.runhistory import RunHistory
# from smac.tae.execute_ta_run import Status
from smac.facade.smac_hpo_facade import SMAC4HPO
from smac.scenario.scenario import Scenario
from ConfigSpace.hyperparameters import CategoricalHyperparameter, \
    UniformFloatHyperparameter, UniformIntegerHyperparameter
from workload_executor import workload_executor
import utils



def tune(workload_file, args, use_surrogate=False):
    """Just run SMAC optimization!"""

    # running default configuration 
    internal_metrics = default_run(workload_file, args)
    
    print(f"Starting tuning for workload: {workload_file}")
    if use_surrogate:
        print("Using SURROGATE MODEL for fast evaluation")
    else:
        print("Using REAL EXECUTION for evaluation")
    
    # Run SMAC (this generates your training data)
    tuner_instance = tuner(args, workload_file, internal_metrics, use_surrogate=use_surrogate)
    best_config = tuner_instance.tune()

    print(f"SMAC optimization complete for {workload_file}")
    return best_config

def default_run(workload_file, args):
    """Run the default configuration to generate initial training data."""

    print(f"Running default configuration for workload")
    # create a database instance
    db = Database(config=args, path=args['tuning_config']['knob_config'])
    # create an instance of workload_executor
    executor = workload_executor(args, utils.get_logger(args['tuning_config']['log_path']), "training_records.log", internal_metrics=None)

    # remove auto_conf from the database
    db.remove_auto_conf()

    # reset inner metrics
    print("Resetting inner metrics...")
    db.reset_inner_metrics()

    # run the workload with default configuration
    executor.run_config(config=None, workload_file=workload_file)
    print(f"Default configuration run complete for workload")

    # get the internal metrics
    internal_metrics = db.fetch_inner_metrics()
    print(f"Internal metrics collected: {internal_metrics}")
    
    # Get benchmark name from config
    benchmark_name = args['benchmark_config']['benchmark']
    
    # save the internal metrics to a file
    if benchmark_name in ['tpcc', 'ycsb', 'smallbank', 'wikipedia', 'twitter']:
        # For TPCC: use benchmark subdirectory and full XML filename
        workload_name = os.path.splitext(os.path.basename(workload_file))[0]  # e.g., "sample_tpcc_config0"
        metrics_dir = f"internal_metrics/{benchmark_name}"
        os.makedirs(metrics_dir, exist_ok=True)
        metrics_file = f"{metrics_dir}/{workload_name}_internal_metrics.json"
    elif benchmark_name == 'tpch':
        # For other benchmarks: use old structure
        metrics_file = f"internal_metrics/{workload_file.split('.wg')[0]}_internal_metrics.json"
    
    with open(metrics_file, "w") as f:
        json.dump(internal_metrics, f, indent=4)
    print(f"Internal metrics saved to: {metrics_file}")
    
    return internal_metrics

class tuner:
    def __init__(self, args, workload_file, internal_metrics, use_surrogate=False):
        self.args = args  # Store args for later use
        self.workload_file = workload_file
        self.knobs_detail = parse_knob_config.get_knobs(args['tuning_config']['knob_config'])
        self.logger = utils.get_logger(args['tuning_config']['log_path'])
        self.internal_metrics = internal_metrics
        self.use_surrogate = use_surrogate
        self.last_point = []
        ## FIXME: this function call needs to be fixed
        self.stt = workload_executor(args, self.logger, "training_records.log", self.internal_metrics)

    def tune(self):
        self.SMAC(self.workload_file)

    def SMAC(self, workload_file):

        def objective_function(config):
            """SMAC objective function - returns negative performance (SMAC minimizes)"""
            config_dict = dict(config)  # Convert Configuration to dict first
            print(f"Evaluating configuration: {config_dict}")
            
            if self.use_surrogate:
                # Use surrogate model for fast prediction
                performance = self.stt.run_config_surrogate(config_dict, workload_file)
            else:
                # Use real execution
                performance = self.stt.run_config(config_dict, workload_file)
            
            if performance > 0:
                performance = -performance
            print(f"Performance (QPS): {performance}")
            return performance

        
        cs = ConfigurationSpace()
        print("Beginning SMAC optimization")
        print(f"Length of knobs: {len(self.knobs_detail)}")
        for name in self.knobs_detail.keys():
            detail = self.knobs_detail[name]
            if detail['type'] == 'integer':
                if detail['max'] == detail['min']: detail['max'] += 1
                knob = UniformIntegerHyperparameter(name, detail['min'],\
                                                     detail['max'], default_value=detail['default'])
            elif detail['type'] == 'float':
                knob = UniformFloatHyperparameter(name, detail['min'],\
                                                     detail['max'], default_value=detail['default'])
            cs.add_hyperparameter(knob)
        
        print("Initialized configuration space with knobs.")
        runhistory = RunHistory()
        
        print(f"Workload file: {self.workload_file}")
        
        # Handle both TPCC (.xml) and OLAP (.wg) files
        if '.xml' in self.workload_file:
            # TPCC: use just the filename without extension
            save_workload = os.path.splitext(os.path.basename(self.workload_file))[0]  # sample_tpcc_config0
        else:
            # OLAP: use existing logic
            save_workload = self.workload_file.split('.wg')[0]

        print(f"Save workload identifier: {save_workload}")

        print("Starting SMAC scenario setup.")
        
        # Get benchmark name for organized directories
        benchmark_name = self.args['benchmark_config']['benchmark']
        
        # Create directories if they don't exist
        os.makedirs(f"./{benchmark_name}", exist_ok=True)
        os.makedirs(f"./models/{benchmark_name}", exist_ok=True)
        os.makedirs("smac_his", exist_ok=True)
        
        scenario = Scenario({"run_obj": "quality",   # {runtime,quality}
                        "runcount-limit": 100,   # max. number of function evaluations; for this example set to a low number
                        "cs": cs,               # configuration space
                        "deterministic": "true",
                        "output_dir": f"./{benchmark_name}/{save_workload}_smac_output",  
                        "save_model": "true",
                        "local_results_path": f"./models/{benchmark_name}/{save_workload}"
                        })
        
        smac = SMAC4HPO(scenario=scenario, rng=np.random.RandomState(42),tae_runner=objective_function, runhistory=runhistory)
        incumbent = smac.optimize()  
        print('finish')
        print(type(incumbent))
        print(incumbent)
        # print(objective_function(incumbent))
        runhistory = smac.runhistory
        print(runhistory.data)

        def runhistory_to_json(runhistory):
            data_to_save = {}
            for run_key in runhistory.data.keys():
                config_id, instance_id, seed, budget = run_key
                run_value = runhistory.data[run_key]
                data_to_save[str(run_key)] = {
                    "cost": run_value.cost,
                    "time": run_value.time,
                    "status": run_value.status.name,
                    "additional_info": run_value.additional_info
                }
            return json.dumps(data_to_save, indent=4)

        with open(f"smac_his/{save_workload}_smac.json", "w") as f:
            f.write(runhistory_to_json(runhistory))
