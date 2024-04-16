import subprocess
import requests
import time
import datetime
import pandas as pd
import matplotlib.pyplot as plt

def find_prometheus_pod(namespace):
    cmd = f"kubectl get pods -n {namespace} --no-headers -o custom-columns=:metadata.name"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception("kubectl command failed. Error: " + result.stderr.strip())

    pod_names = result.stdout.split()
    for pod_name in pod_names:
        if "prometheus-server" in pod_name:
            return pod_name

    raise Exception("No Prometheus pod found with 'prometheus-server' in its name.")

def start_port_forwarding(namespace, pod_name, local_port, remote_port):
    command = [
        "kubectl", "port-forward",
        f"pod/{pod_name}",
        f"{local_port}:{remote_port}",
        "-n", namespace
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(2)  # Give kubectl a moment to establish the connection
    if process.poll() is not None:
        raise Exception(f"Failed to start port forwarding, error: {process.stderr.read().decode()}")
    print(f"Port forwarding established on localhost:{local_port} -> {pod_name}:{remote_port}")
    return process

def query_prometheus(prometheus_url, query, start, end, step):
    params = {
        'query': query,
        'start': start.timestamp(),
        'end': end.timestamp(),
        'step': step
    }
    response = requests.get(f"{prometheus_url}/api/v1/query_range", params=params)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to query Prometheus: {response.status_code} - {response.text}")

def parse_timeseries(data):
    results = data['data']['result']
    timestamps = []
    values = []
    for result in results:
        for value in result['values']:
            timestamps.append(pd.to_datetime(value[0], unit='s'))
            values.append(float(value[1]))
    return timestamps, values

def plot_data(timestamps, values):
    plt.figure(figsize=(10, 6))
    plt.plot(timestamps, values, marker='o')
    plt.title('CPU Usage Over Time')
    plt.xlabel('Time')
    plt.ylabel('CPU Usage')
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

def main():
    namespace = "monitoring"
    prometheus_pod = find_prometheus_pod(namespace)
    local_port = 9090
    remote_port = 9090
    query = '1 - avg(rate(node_cpu_seconds_total{instance="10.0.0.29:9100", mode="idle"}[1h]))'
    now = datetime.datetime.now()
    start_time = now - datetime.timedelta(hours=1)
    end_time = now
    step = '60'  # step size in seconds

    process = start_port_forwarding(namespace, prometheus_pod, local_port, remote_port)
    try:
        data = query_prometheus(f"http://localhost:{local_port}", query, start_time, end_time, step)
        timestamps, values = parse_timeseries(data)
        plot_data(timestamps, values)
    finally:
        process.terminate()
        process.wait()
        print("Port forwarding stopped.")

if __name__ == "__main__":
    main()


