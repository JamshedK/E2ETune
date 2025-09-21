import json

# Load the knob config
with open('knob_config/knob_config.json', 'r') as f:
    knob_config = json.load(f)

# Load the temp response
with open('temp_response.json', 'r') as f:
    temp_response = json.load(f)

# Find knobs in config but not in response
missing_in_response = []
for knob in knob_config.keys():
    if knob not in temp_response:
        missing_in_response.append(knob)

# Find knobs in response but not in config
extra_in_response = []
for knob in temp_response.keys():
    if knob not in knob_config:
        extra_in_response.append(knob)

print(f"Total knobs in config: {len(knob_config)}")
print(f"Total knobs in response: {len(temp_response)}")
print()

if missing_in_response:
    print(f"Knobs in config but MISSING from response ({len(missing_in_response)}):")
    for knob in missing_in_response:
        print(f"  - {knob}")
else:
    print("✅ All config knobs are present in response")

print()

if extra_in_response:
    print(f"Knobs in response but NOT in config ({len(extra_in_response)}):")
    for knob in extra_in_response:
        print(f"  - {knob}")
else:
    print("✅ No extra knobs in response")

print()
print(f"Coverage: {len(temp_response) - len(extra_in_response)}/{len(knob_config)} ({(len(temp_response) - len(extra_in_response))/len(knob_config)*100:.1f}%)")