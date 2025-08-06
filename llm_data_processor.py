import json

label_mapper = {
    0: "00% to 10%",
    1: "10% to 20%",
    2: "20% to 30%",
    3: "30% to 40%",
    4: "40% to 50%",
    5: "50% to 60%",
    6: "60% to 70%",
    7: "70% to 80%",
    8: "80% to 90%",
    9: "90% to 100%",
}


def format_single_query_plan(node):
    # type
    formatted = f"{node['Node Type'].lower()}"
    # check child
    if "Plans" in node:
        child_formats = []
        for child in node["Plans"]:
            child_format = format_single_query_plan(child)
            child_formats.append(child_format)
        cost = node["Total Cost"] - node["Startup Cost"]
        if cost < 1000:
            cost = format(cost, ".1f")
        elif cost > 1000 and cost < 1000000:
            cost = f"{int(cost/1000)}k"
        elif cost >= 1000000:
            cost = f"{int(cost/1000000)} million"
        formatted += f"({', '.join(child_formats)}, {cost})"
        print(formatted)

    return formatted


query_plan_location = "query_plans/tpch.json"

# Load query plans from external file
query_plan_location = "query_plans/tpch.json"
all_formatted_plans = []

with open(query_plan_location, "r") as f:
    external_plans = json.load(f)

for plan in external_plans:
    if "Plan" in plan:
        formatted_plans = format_single_query_plan(plan["Plan"]["Plan"])
        all_formatted_plans.append(formatted_plans)
print(all_formatted_plans[0])


setting = 4
results = []


results.append(
    {
        "database": line["database"],
        "workload": line["workload_name"],
        "instruction": 'You are an expert in database, you are to optimize the parameters of database, please output in json format, for each field, output one of "00% to 10%", "10% to 20%", "20% to 30%", "40% to 50%", "50% to 60%", "60% to 70%", "70% to 80%", "80% to 90%", "90% to 100%". The follow information of workloads are offered for you: features, query plans and inner metrics. Every SQL in the workload corresponds to a query plan tree and the query plan tree is represented using parentheses, where each node is followed by a pair of parentheses containing its child nodes, with sub-nodes separated by parentheses, recursively showing the entire tree\'s hierarchical structure. Additionally, each node carries a cost value estimated by PostgreSQL.',
        "input": f"workload features: {feature_descrip} query plans in workload: {'; '.join(all_formatted_plans)}; inner metrics: {inner_metrics}",
        "output": json.dumps(output, ensure_ascii=False),
    }
)
