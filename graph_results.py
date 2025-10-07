import matplotlib.pyplot as plt

# Read the data
with open('model_output_tpch2.txt', 'r') as f:
    lines = f.readlines()

default_qps = float(lines[0].split(':')[1].strip())
response_qps = [float(line.split(':')[1].strip()) for line in lines[1:]]

# Convert to positive values (remove negative sign)
default_qps = abs(default_qps)
response_qps = [abs(qps) for qps in response_qps]

# Combine responses only (R1, R2, etc.)
all_qps = response_qps
all_names = [f"R{i+1}" for i in range(len(response_qps))]

# Create line plot
plt.figure(figsize=(10, 6))
plt.plot(all_names, all_qps, 'bo-', linewidth=2, markersize=8)

# Add default as horizontal line
plt.axhline(y=default_qps, color='red', linestyle='--', linewidth=2, 
            label=f'Default (R0): {default_qps:.3f}')

plt.xlabel('Configuration')
plt.ylabel('QPS (Queries Per Second)')
plt.title('PostgreSQL Configuration Performance (Higher is Better)')
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()

plt.savefig('qps_results.png', dpi=300)
plt.show()

print(f"Default QPS: {default_qps:.3f}")
print(f"Best: R{response_qps.index(max(response_qps))+1} with {max(response_qps):.3f} QPS")