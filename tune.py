import time
import json
import json
from knob_config import parse_knob_config
import utils
import numpy as np
from Database import Database
from smac.configspace import ConfigurationSpace
from smac.runhistory.runhistory import RunHistory
# from smac.tae.execute_ta_run import Status
from smac.facade.smac_hpo_facade import SMAC4HPO
from smac.scenario.scenario import Scenario
from ConfigSpace.hyperparameters import CategoricalHyperparameter, \
    UniformFloatHyperparameter, UniformIntegerHyperparameter
from test_workload_and_config import test_config

def tune(workload_file, args):
    """Just run SMAC optimization!"""
    
    # Run SMAC (this generates your training data)
    tuner_instance = tuner(args, workload_file)
    best_config = tuner_instance.tune()

    print(f"SMAC optimization complete for {workload_file}")
    return best_config

class tuner:
    def __init__(self, args, workload_file):
        self.workload_file = workload_file
        self.inner_metric_sample = args['tuning_config']['inner_metric_sample']
        self.knobs_detail = parse_knob_config.get_knobs(args['tuning_config']['knob_config'])
        self.logger = utils.get_logger(args['tuning_config']['log_path'])
        self.last_point = []
        ## FIXME: this function call needs to be fixed
        self.stt = test_config(args)

    def tune(self):
        self.SMAC()

    def SMAC(self):

        def objective_function(config_dict):
            """SMAC objective function - returns negative performance (SMAC minimizes)"""
            performance = test_config(self, config_dict)
            return -performance  # Negate because SMAC minimizes

        
        cs = ConfigurationSpace()
        print("Beginning SMAC optimization")
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

        runhistory = RunHistory()
        
        save_workload = self.wl_id.split('olap_workloads/')[1]
        save_workload = save_workload.split('.wg')[0]
        
        scenario = Scenario({"run_obj": "quality",   # {runtime,quality}
                        "runcount-limit": 75,   # max. number of function evaluations; for this example set to a low number
                        "cs": cs,               # configuration space
                        "deterministic": "true",
                        "output_dir": f"./{save_workload}_smac_output",  
                        "save_model": "true",
                        "local_results_path": f"./models/{save_workload}"
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

        with open(f"smac_his/{save_workload}_{self.warmup}.json", "w") as f:
            f.write(runhistory_to_json(runhistory))
