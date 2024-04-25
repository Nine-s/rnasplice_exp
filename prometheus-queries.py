import subprocess
import requests
import time
import datetime
import pandas as pd
import matplotlib.pyplot as plt
import json

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

def query_prometheus_and_save_results(start, end, list_of_nodes, experiment_name):
    namespace = "monitoring"
    prometheus_pod = find_prometheus_pod(namespace)
    port_forwarding_process = start_port_forwarding(namespace, prometheus_pod, 9090, 9090)
    prometheus_url = "http://localhost:9090"

    step = '1m'
    for title, query in KUBERNETES_QUERIES.items():
        for node in list_of_nodes:
            filled_query = query.replace('{{node}}', f'"{node}"').replace('{{step}}', step)
            print(f"Querying {title} for node {node}. The query is: {filled_query}")
            try:
                data = query_prometheus(prometheus_url, filled_query, start, end, step)
                # Save the plain json data to a file
                specific_title = f"{experiment_name + '_' + title.replace(' ', '_') + '_' + node}" 
                with open(specific_title + ".json", "w") as f:
                    json.dump(data, f)
                    timestamps, values = parse_timeseries(data)
            except:
                print(f"Failed to query {title} for node {node}.")
                # Stop the port forwarding and exit
                port_forwarding_process.terminate()
                port_forwarding_process.wait()
                exit(1)

            plot_data(timestamps, values, title=specific_title, xlabel="Time", ylabel=title)
    
    for title, query in CEPH_QUERIES.items():
        print(f"Querying {title}. The query is: {query}")
        try:
            data = query_prometheus(prometheus_url, query, start, end, step)
            # Save the plain json data to a file
            specific_title = f"{experiment_name + '_' + title.replace(' ', '_') + '_' + node}" 
            with open(specific_title + ".json", "w") as f:
                json.dump(data, f)
            
            timestamps, values = parse_timeseries(data)
        except:
            print(f"Failed to query {title}.")
            # Stop the port forwarding and exit
            port_forwarding_process.terminate()
            port_forwarding_process.wait()
            exit(1)

        plot_data(timestamps, values, title=specific_title, xlabel="Time", ylabel=title)
    
    # Stop port forwarding
    port_forwarding_process.terminate()
    port_forwarding_process.wait()
    print("Port forwarding stopped.")

    return


def parse_experiments(filename):
    experiments = []
    with open(filename, 'r') as file:
        for line in file:
            fields = line.strip().split('\t')
            if len(fields) >= 6:
                # Handle datetime parsing
                start_datetime = datetime.datetime.strptime(fields[0], "%d-%m-%y_%H-%M")
                end_datetime = datetime.datetime.strptime(fields[1], "%d-%m-%y %H:%M")
                
                experiment = {
                    'start': start_datetime,
                    'end': end_datetime,
                    'bandwidth': fields[2] if fields[2] != '' else None,
                    'number_of_nodes': int(fields[3]),
                    'type': fields[4],
                    'number_of_replicas': int(fields[5]),
                    'title': f"{fields[3]}_nodes_{fields[4]}_{fields[5]}_replicas_{fields[2]}_bandwidth"
                }
                experiments.append(experiment)
    return experiments



KUBERNETES_QUERIES = {
    'non_idle_cpu_time_percentage': '100 - avg(rate(node_cpu_seconds_total{instance={{node}}, mode="idle"}[{{step}}]) * 100)', # DONE
    'used_ram_gigabytes': '(node_memory_MemTotal_bytes{instance={{node}}} - node_memory_MemAvailable_bytes{instance={{node}}}) / 1024^3', # DONE
    'used_disk_space_gigabytes': 'sum((node_filesystem_size_bytes{instance={{node}}} - node_filesystem_free_bytes{instance={{node}}}) / 1024^3)', # DONE
    'used_pvc_space_gigabytes': 'kubelet_volume_stats_used_bytes{persistentvolumeclaim="nextflow-ninon"}', 
    'total_bytes_transmitted_regular_network_megabytes': 'increase(node_network_transmit_bytes_total{instance={{node}}, device="eno1np0"}[{{step}}]) / 1024^2',
    'total_bytes_received_regular_network_megabytes': 'increase(node_network_receive_bytes_total{instance={{node}}, device="eno1np0"}[{{step}}]) / 1024^2',
    'total_bytes_transmitted_ceph_network_megabytes': 'increase(node_network_transmit_bytes_total{instance={{node}}, device="eno2np1"}[{{step}}]) / 1024^2',
    'total_bytes_received_ceph_network_megabytes': 'increase(node_network_receive_bytes_total{instance={{node}}, device="eno2np1"}[{{step}}]) / 1024^2',

}

CEPH_QUERIES = {

    "total_write_operations_throughput": "sum(irate(ceph_osd_op_w[5m]))",
    "total_read_operations_throughput": "sum(irate(ceph_osd_op_r[5m]))",
    "total_written_bytes_throughput": "sum(irate(ceph_osd_op_w_in_bytes[5m]))",
    "total_read_bytes_throughput": "sum(irate(ceph_osd_op_r_out_bytes[5m]))",

    "total_write_operations_last_hour": "sum(increase(ceph_osd_op_w[1h]))",
    "total_read_operations_last_hour": "sum(increase(ceph_osd_op_r[1h]))",
    "total_written_bytes_last_hour": "sum(increase(ceph_osd_op_w_in_bytes[1h]))",
    "total_read_bytes_last_hour": "sum(increase(ceph_osd_op_r_out_bytes[1h]))",

}


exp_4_nodes_addresses = ["10.0.0.24:9100","10.0.0.25:9100","10.0.0.26:9100","10.0.0.27:9100"]
exp_8_nodes_addresses = ["10.0.0.24:9100","10.0.0.25:9100","10.0.0.26:9100","10.0.0.27:9100","10.0.0.28:9100","10.0.0.23:9100","10.0.0.43:9100","10.0.0.40:9100"]
exp_16_nodes_addresses = ["10.0.0.23:9100","10.0.0.24:9100","10.0.0.25:9100","10.0.0.26:9100","10.0.0.27:9100","10.0.0.28:9100","10.0.0.29:9100","10.0.0.30:9100","10.0.0.34:9100","10.0.0.35:9100","10.0.0.36:9100","10.0.0.37:9100","10.0.0.38:9100","10.0.0.39:9100","10.0.0.40:9100","10.0.0.41:9100"]
ceph_node_addresses = ["10.0.0.23:9100","10.0.0.24:9100","10.0.0.25:9100","10.0.0.26:9100","10.0.0.27:9100","10.0.0.28:9100","10.0.0.29:9100","10.0.0.40:9100",]

if __name__ == "__main__":
    experiments = parse_experiments("script_logs.tsv")

    # For the first 2 experiments, query Prometheus and save the results
    for experiment in experiments[1:3]:
        case = experiment['number_of_nodes']
        if case == 4:
            experiment['nodes'] = exp_4_nodes_addresses
        elif case == 8:
            experiment['nodes'] = exp_8_nodes_addresses
        elif case == 16:
            experiment['nodes'] = exp_16_nodes_addresses
        else:
            print("Invalid number of nodes.")
            exit(1)
        query_prometheus_and_save_results(experiment['start'], experiment['end'], experiment['nodes'], experiment['title'])