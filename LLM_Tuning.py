import argparse
from config import parse_config
import os

from Database import Database
from workload_executor import workload_executor
import utils
import json
from data_processing.format_query_plans import format_query_plans

feature_names = ['size of workload', 'read ratio', 'group by ratio', 'order by ratio', 'aggregation ratio', 'average predicate num per SQL']
inner_names = ["xact_commit", "xact_rollback", "blks_read", "blks_hit", "tup_returned", "tup_fetched", "tup_inserted", "conflicts", "tup_updated", "tup_deleted", "disk_read_count", "disk_write_count", "disk_read_bytes", "disk_write_bytes"]

class LLMTuning: 

    def __init__(self, args, workload_file, workload_name):
        self.args = args
        self.workload_file = workload_file
        self.db = Database(config=args, path=args['tuning_config']['knob_config'])
        self.executor = workload_executor(args, utils.get_logger(args['tuning_config']['log_path']), "training_records.log", internal_metrics=None)
        self.workload_name = workload_name
        self.query_plan_location = "query_plans/tpch.json"

        # Read workload file content - add '.olap_workloads/' 
        workload_file = os.path.join('./olap_workloads', workload_file)
        with open(workload_file, 'r') as f:
            self.workload_content = f.read()

    def default_run(self, workload_file, args):
        """Run the default configuration"""

        print(f"Running default configuration for workload")

        # remove auto_conf from the database
        self.db.remove_auto_conf()

        # run the workload with default configuration
        qps = self.executor.run_config(config=None, workload_file=workload_file)
        print(f"Default configuration run complete for workload")

        # get the internal metrics
        internal_metrics = self.db.fetch_inner_metrics()
        print(f"Internal metrics collected: {internal_metrics}")
        # save the internal metrics to a file
        with open(f"internal_metrics/{workload_file.split('.wg')[0]}_internal_metrics.json", "w") as f:
            json.dump(internal_metrics, f, indent=4)
        
        return {"internal_metrics": internal_metrics, "qps": qps}

    def format_inner_metrics(self, internal_metrics):
        inner_metrics_string = ''
        inner = internal_metrics
        for idx, name in enumerate(inner_names):
            value = inner[idx]
            if value > 0 and value < 1:
                if value < 0.3333: inner_metrics_string += f'{name}: low; '
                elif value < 0.66667: inner_metrics_string += f'{name}: middle; '
                else: inner_metrics_string += f'{name}: high; '
            elif value > 0 and value < 1000:
                inner_metrics_string += f'{name}: {(int(value * 100)) / 100.0}; '
            elif value < 1000000:
                inner_metrics_string += f'{name}: {(int(value/ 1000))}k; '
            elif value >= 1000000: inner_metrics_string += f'{name}: {(int(value/ 100000)) / 10} million; '
        return inner_metrics_string
    
    def get_query_plans(self):
        """Get query plans for the workload"""

        plans = self.db.save_workload_plans(self.workload_file, self.workload_name)
        print(f"Query plans collected for workload")
        
        # format the query plans 
        formatted_plans = format_query_plans(self.query_plan_location)
        print(f"Query plans formatted for workload")
        return formatted_plans

    def get_workload_statistics(self):
        # Clean and normalize the text
        workload_text = self.workload_content.upper()

        # Split into SQL statements (by semicolon)
        sql_statements = [stmt.strip() for stmt in workload_text.split(';') if stmt.strip()]
        total_statements = len(sql_statements)

        # 1. Size of workload
        size_of_workload = total_statements

        # 2. Read ratio (SELECT vs INSERT/UPDATE/DELETE)
        select_count = len([stmt for stmt in sql_statements if stmt.strip().upper().startswith('SELECT')])
        read_ratio = select_count / total_statements

        # 3. Group by ratio
        group_by_count = workload_text.count('GROUP BY')
        group_by_ratio = group_by_count / total_statements
        
        # 4. Order by ratio
        order_by_count = workload_text.count('ORDER BY')
        order_by_ratio = order_by_count / total_statements
        
        # 5. Aggregation ratio
        agg_functions = ['SUM(', 'COUNT(', 'AVG(', 'MAX(', 'MIN(']
        # check if any aggregation function is present in the statement
        agg_count =0
        for stmt in sql_statements:
            # if any aggregation function is present in the statement, just count once
            for func in agg_functions:
                if func in stmt:
                    agg_count += 1
                    break
        aggregation_ratio = agg_count / total_statements
        
        # 6. Average predicate number per SQL
        total_predicates = 0
        for sql in sql_statements:
            sql_upper = sql.upper()
            # Count WHERE clauses
            where_count = sql_upper.count('WHERE')
            # Count AND/OR operators (additional conditions)
            and_count = sql_upper.count(' AND ')
            or_count = sql_upper.count(' OR ')
            # Total predicates for this SQL
            predicates = where_count + and_count + or_count
            total_predicates += predicates
        
        avg_predicate_num = total_predicates / total_statements                

        feature_values = [size_of_workload, read_ratio, group_by_ratio, order_by_ratio, aggregation_ratio, avg_predicate_num]
        print(f"Workload statistics: {feature_values}")
        return feature_values

    def format_workload_statistics(self, feature_values):
        feature_descrip = ''
        for idx, name in enumerate(feature_names):
            value = feature_values[idx]
            feature_descrip += f'{name}: {round(value, 2)}; '
        return feature_descrip

    def generate_prompt(self):
        database = 'PostgreSQL'

        # get the workload statistics
        feature_values = self.get_workload_statistics()
        feature_descrip = self.format_workload_statistics(feature_values)
        print(f"Workload statistics collected: {feature_descrip}")

        # get the query plans
        all_formatted_plans = self.get_query_plans()
        print(f"Query plans collected: {'; '.join(all_formatted_plans)}")

        # # get internal metrics
        res = self.default_run(self.workload_file, self.args)
        internal_metrics = res['internal_metrics']
        qps = res['qps']
        inner_metrics_str = self.format_inner_metrics(internal_metrics)

        prompt = f"""You are an expert in database, you are to optimize the parameters of database, please output in json format, for each field, output one of "00% to 10%", "10% to 20%", "20% to 30%", "30% to 40%", "40% to 50%", "50% to 60%", "60% to 70%", "70% to 80%", "80% to 90%", "90% to 100%". The follow information of workloads are offered for you: features, query plans and inner metrics. Every SQL in the workload corresponds to a query plan tree and the query plan tree is represented using parentheses, where each node is followed by a pair of parentheses containing its child nodes, with sub-nodes separated by parentheses, recursively showing the entire tree's hierarchical structure. Additionally, each node carries a cost value estimated by PostgreSQL.
                workload features: {feature_descrip} query plans in workload: {'; '.join(all_formatted_plans)}; inner metrics: {inner_metrics_str}"""
        # save prompt to self.workload_name_prompt.txt
        with open(f"{self.workload_name}_prompt.txt", "w") as f:
            f.write(prompt)
        return prompt

if __name__ == "__main__":
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

    # create a LLMTuning instance
    llm_tuner = LLMTuning(args, 'tpch_2.wg', 'tpch_2')

    llm_tuner.generate_prompt()