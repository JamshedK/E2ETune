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

def format_query_plans(query_plan_location):

    all_formatted_plans = []

    with open(query_plan_location, "r") as f:
        external_plans = json.load(f)

    for plan in external_plans:
        if "Plan" in plan:
            formatted_plans = format_single_query_plan(plan["Plan"]["Plan"])
            all_formatted_plans.append(formatted_plans)
    return all_formatted_plans
