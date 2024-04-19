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
        if "prometheus-prometheus-kube-prometheus-prometheus-0" in pod_name:
            return pod_name

    raise Exception("No Prometheus pod found with 'prometheus-kube' in its name.")

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
        # Show query in case of error
        print(f"Query: {query}")
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

def plot_data(timestamps, values, title='', xlabel='', ylabel=''):
    plt.figure(figsize=(10, 6))
    plt.plot(timestamps, values, marker='o')
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Save the plot
    plt.savefig(f"{title.replace(' ', '_')}.png")


VECTOR_QUERIES = {
    'non_idle_cpu_time': '100 - avg(rate(node_cpu_seconds_total{instance={{node}}, mode="idle"}[{{max_time}}m]) * 100)',
    'used_ram': '(node_memory_MemTotal_bytes{instance={{node}}} - node_memory_MemAvailable_bytes{instance={{node}}})',
    'used_disk_space': '(node_filesystem_size_bytes{instance={{node}}, mountpoint="/var"} - node_filesystem_free_bytes{instance={{node}}, mountpoint="/var"})', #TODO check if it works when the query range is given externally
    'used_pvc_space': 'kubelet_volume_stats_used_bytes{persistentvolumeclaim="ninon-nextflow"}', # This fetches multiple graphs, need to get only one
    'total_bytes_transmitted_regular_network': 'rate(node_network_transmit_bytes_total{instance={{node}}, device="eno1np0"}[{{max_time}}h])',
    'total_bytes_received_regular_network': 'rate(node_network_receive_bytes_total{instance={{node}}, device="eno1np0"}[{{max_time}}h])',
    'total_bytes_transmitted_ceph_network': 'rate(node_network_transmit_bytes_total{instance={{node}}, device="eno2np1"}[{{max_time}}h])',
    'total_bytes_received_ceph_network': 'rate(node_network_receive_bytes_total{instance={{node}}, device="eno2np1"}[{{max_time}}h])',
}

GAUGE_QUERIES = {"cluster_total_bytes_written": "sum(irate(ceph_osd_op_w_in_bytes[1m]))",
                "cluster_total_bytes_read": 'sum(irate(ceph_osd_op_r_in_bytes[1m]))',
                "cluster_total_ops_written": "sum(irate(ceph_osd_op_w[1m]))",
                "cluster_total_ops_read": "sum(irate(ceph_osd_op_r[1m]))",
                }


LIST_OF_NODES = ["10.0.0.24:9100", "10.0.0.38:9100"]

def generate_vector_queries(max_time_to_query):
    list_of_queries = []
    for query_name, query_template in VECTOR_QUERIES.items():
        for node in LIST_OF_NODES:
            query = query_template.replace('{{node}}', f'"{node}"').replace('{{max_time}}', str(max_time_to_query))
            list_of_queries.append(query)

    return list_of_queries

def generate_vector_queries(max_time_to_query):
    list_of_queries = []
    for query_name, query_template in GAUGE_QUERIES.items():
        query = query_template.replace('{{max_time}}', str(max_time_to_query))
        list_of_queries.append(query)

    return list_of_queries

if __name__ == "__main__":
    vector_queries_list = generate_vector_queries(1)
    for query in vector_queries_list:
        print(query)

    for query in generate_vector_queries(1):
        print(query)

    namespace = "monitoring"
    prometheus_pod = find_prometheus_pod(namespace)
    port_forwarding_process = start_port_forwarding(namespace, prometheus_pod, 9090, 9090)
    prometheus_url = "http://localhost:9090"

    example_query = vector_queries_list[0]

    # Query Prometheus
    start = datetime.datetime.now() - datetime.timedelta(hours=1)
    end = datetime.datetime.now()
    step = 30
    data = query_prometheus(prometheus_url, query, start, end, step)

    for title, query in VECTOR_QUERIES.items():
        for node in LIST_OF_NODES:
            filled_query = query.replace('{{node}}', f'"{node}"').replace('{{max_time}}', '1')
            print(f"Querying {title} for node {node}. The query is: {filled_query}")
            try:
                data = query_prometheus(prometheus_url, filled_query, start, end, step)
                timestamps, values = parse_timeseries(data)
            except:
                print(f"Failed to query {title} for node {node}.")
                # Stop the port forwarding and exit
                port_forwarding_process.terminate()
                port_forwarding_process.wait()
                exit(1)

            plot_data(timestamps, values, title=f"{title} for node {node}", xlabel="Time", ylabel=title)
    
    for title, query in GAUGE_QUERIES.items():
        print(f"Querying {title}. The query is: {query}")
        try:
            data = query_prometheus(prometheus_url, query, start, end, step)
            timestamps, values = parse_timeseries(data)
        except:
            print(f"Failed to query {title}.")
            # Stop the port forwarding and exit
            port_forwarding_process.terminate()
            port_forwarding_process.wait()
            exit(1)

        plot_data(timestamps, values, title=title, xlabel="Time", ylabel=title)
    
    # Stop port forwarding
    port_forwarding_process.terminate()
    port_forwarding_process.wait()
    print("Port forwarding stopped.")
    
    exit(0)
