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
    'non_idle_cpu_time_percentage': '100 - avg(rate(node_cpu_seconds_total{instance={{node}}, mode="idle"}[{{step}}]) * 100)', # DONE
    'used_ram_gigabytes': '(node_memory_MemTotal_bytes{instance={{node}}} - node_memory_MemAvailable_bytes{instance={{node}}}) / 1024^3', # DONE
    'used_disk_space': 'sum((node_filesystem_size_bytes{instance={{node}}} - node_filesystem_free_bytes{instance={{node}}}) / 1024^3)', # DONE
    'used_pvc_space': 'kubelet_volume_stats_used_bytes{persistentvolumeclaim="ninon-nextflow"}', # This fetches multiple graphs, need to get only one
    'total_bytes_transmitted_regular_network': 'increase(node_network_transmit_bytes_total{instance={{node}}, device="eno1np0"}[{{step}}]) / 1024^3',
    'total_bytes_received_regular_network': 'increase(node_network_receive_bytes_total{instance={{node}}, device="eno1np0"}[{{step}}]) / 1024^3',
    'total_bytes_transmitted_ceph_network': 'increase(node_network_transmit_bytes_total{instance={{node}}, device="eno2np1"}[{{step}}]) / 1024^3',
    'total_bytes_received_ceph_network': 'increase(node_network_receive_bytes_total{instance={{node}}, device="eno2np1"}[{{step}}]) / 1024^3',

}

GAUGE_QUERIES = {
    "total_write_operations": "sum(irate(ceph_osd_op_w[1m])) / 1024^3",
    "total_read_operations": "sum(irate(ceph_osd_op_r[1m])) / 1024^3",
    "total_written_bytes": "sum(irate(ceph_osd_op_w_in_bytes[1m]))/ 1024^3",
    "total_read_bytes": "sum(irate(ceph_osd_op_r_out_bytes[1m])) / 1024^3",
}

LIST_OF_NODES = ["10.0.0.24:9100", "10.0.0.38:9100"]

def generate_vector_queries(step):
    list_of_queries = []
    for query_name, query_template in VECTOR_QUERIES.items():
        for node in LIST_OF_NODES:
            query = query_template.replace('{{node}}', f'"{node}"').replace('{{step}}', step)
            list_of_queries.append(query)

    return list_of_queries

def generate_gauge_queries(step):
    list_of_queries = []
    for query_name, query_template in GAUGE_QUERIES.items():
        query = query_template.replace('{{step}}', step)
        list_of_queries.append(query)

    return list_of_queries

if __name__ == "__main__":
    namespace = "monitoring"
    prometheus_pod = find_prometheus_pod(namespace)
    port_forwarding_process = start_port_forwarding(namespace, prometheus_pod, 9090, 9090)
    prometheus_url = "http://localhost:9090"

    # Generate example datetimes to query (2 hours duration yesterday)
    # starts yesterday
    start = datetime.datetime.now() - datetime.timedelta(days=1)
    # lasts 2 hours
    end = start + datetime.timedelta(hours=2)
    step = '1m'

    # # Query Prometheus right now
    # start = datetime.datetime.now() - datetime.timedelta(hours=1)
    # end = datetime.datetime.now()
    # step = 30
    # data = query_prometheus(prometheus_url, query, start, end, step)

    for title, query in VECTOR_QUERIES.items():
        for node in LIST_OF_NODES:
            filled_query = query.replace('{{node}}', f'"{node}"').replace('{{step}}', step)
            print(f"Querying {title} for node {node}. The query is: {filled_query}")
            try:
                data = query_prometheus(prometheus_url, filled_query, start, end, step)
                # Save the plain json data to a file
                with open(f"{title.replace(' ', '_')}.json", "w") as f:
                    f.write(str(data))
                    timestamps, values = parse_timeseries(data)
            except:
                print(f"Failed to query {title} for node {node}.")
                # Stop the port forwarding and exit
                port_forwarding_process.terminate()
                port_forwarding_process.wait()
                exit(1)

            plot_data(timestamps, values, title=f"{title} for node {node}", xlabel="Time", ylabel=title)
    
    # Does CEPH require different numbers?
    # starts yesterday
    start = datetime.datetime.now() - datetime.timedelta(days=1)
    # lasts 2 hours
    end = start + datetime.timedelta(hours=2)
    step = '500s' # Try a few steps here to check the difference
    
    for title, query in GAUGE_QUERIES.items():
        print(f"Querying {title}. The query is: {query}")
        try:
            data = query_prometheus(prometheus_url, query, start, end, step)
            # Save the plain json data to a file
            with open(f"{title.replace(' ', '_')}.json", "w") as f:
                f.write(str(data))
            
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
