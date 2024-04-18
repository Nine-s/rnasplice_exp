import os
import datetime
import time
import subprocess
from kubernetes import client, config, stream
from kubernetes.stream import stream

# K8S config
path_to_work_folder = "/data/ninon/rnasplice_experiments_traces/"
path_to_trace_files = "/data/ninon/"
path_to_trace_folders = ""
path_to_nextflow = "nextflow"
name_of_volume = "nextflow-ninon"  
namespace = "default"  
helper_pod = "ubuntu-pod"
helper_container = "ubuntu-pod"

# Load the Kubernetes configuration
config.load_kube_config('/home/ninon/.kube/config')

# Create an API client
api = client.CoreV1Api()

def check_pod_status(pod_name):
    pod = api.read_namespaced_pod_status(pod_name, namespace)
    return pod.status.phase


def execute_command_in_container(input_command):
    try:
        response = stream(api.connect_get_namespaced_pod_exec, helper_pod, namespace, command=['/bin/bash', '-c', input_command], container=helper_container, stderr=True, stdout=True)
        if response:
            print(f"Response: {response}")
        else:
            print("Empty response received. This does not indicate an error.")
    except Exception as e:
        print(f"An error occurred while executing the command: {e}")


def run_tc_config(bandwidth, list_of_nodes): #TODO ninon: add list of nodes
    if (bandwidth is not None):
        my_command = "start_tc_config_command" + str(bandwidth) + "end_tc_config_command"
        runCommand(my_command) #TODO : vasilis: take care of the command
        check_bandwidth(bandwidth) #???

def run_one_experiment(command):
    current_datetime = datetime.datetime.now()
    start_time = current_datetime.strftime("%d-%m-%y %H:%M")
    command_to_run = path_to_nextflow + " kuberun " + command + " -v " + name_of_volume
    result = subprocess.run(command_to_run, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True) 
    output_lines = result.stdout.splitlines()
    print('Searching for pod name...')
    for line in output_lines:
        if "Pod started:" in line:
            # Extract the pod name
            pod_name = line.split("Pod started: ")[-1]
            break

    try:
        print(f"Pod name: {pod_name}")
    except:
        print("Pod name not found. Exiting...")
        exit(1)

    while True:
        status = check_pod_status(pod_name)
        if status == "Succeeded":
            print(f"Pod {pod_name} has succeeded.")
            break
        elif status == "Failed":
            print(f"Pod {pod_name} has failed.")
            break
        else:
            print(f"Pod {pod_name} is still running. Current status: {status}")
            time.sleep(120)  # Sleep for 2 minute (120 seconds)

    current_datetime = datetime.datetime.now()
    end_time = current_datetime.strftime("%d-%m-%y %H:%M")
    return start_time, end_time

def create_log_file():
    base_name, extension = os.path.splitext(logname)
    counter = 1
    new_filename = logname
    while os.path.exists(new_filename):
        new_filename = f"{base_name}_{counter}{extension}"
        counter += 1
    open(new_filename, "a").close()
    print(f"File '{new_filename}' created.")

def add_data_to_log(start_time, end_time, bandwidth, node, exp, replicate):
    with open(logname, "a") as log:
        log.write(start_time + "\t" + end_time + "\t" + bandwidth + "\t" + node + "\t" + exp + "\t" + replicate + "\n")
    return

def check_if_daw_is_done():
    return True

def move_trace_files(bandwidth, nodes, daw_type, replicate):
    path_to_right_trace_folder = path_to_trace_folders + "/" + bandwidth  + "/" + nodes  + "/" + daw_type  + "/" + replicate  + "/" 
    subprocess.run("mv " + path_to_trace_files + "/_* " + path_to_right_trace_folder) 

def remove_work_folder(): 
    subprocess.run("rm -r " + path_to_work_folder + "work")



### START

# NODES
exp_4_nodes = ["worker-c23","worker-c24","worker-c25","worker-c26"]
exp_8_nodes = ["worker-c23","worker-c24","worker-c25","worker-c26","worker-c27","worker-c28","worker-c29","worker-c30"]
exp_16_nodes = ["worker-c23","worker-c24","worker-c25","worker-c26","worker-c27","worker-c28","worker-c29","worker-c30","worker-c34","worker-c35","worker-c36","worker-c37","worker-c38","worker-c39","worker-c40","worker-c41"]

# PATHS
logname = "rnasplice_execution.log"
path_to_config_files = "/data/ninon/rnasplice_experiments_configs/" 

# EXP PARAMETERS
bandwidths = [None, 1, 2, 10] #in Mb # TODO
nodes = [4, 8, 16]

command_4_nodes = "nextflow kuberun Nine-s/rnasplice_generated_modified_reduced_/ -r 4_nodes -c " + path_to_config_files + "exp_4_nodes.config"
command_8_nodes = "nextflow kuberun Nine-s/rnasplice_generated_modified_reduced_/ -r 8_nodes -c " + path_to_config_files + "exp_8_nodes.config"
command_16_nodes = "nextflow kuberun Nine-s/rnasplice_generated_modified_reduced_/ -r 16_nodes -c " + path_to_config_files + "exp_16_nodes.config"
daws_rewritten_commandline = [command_4_nodes, command_8_nodes, command_16_nodes]

command_baseline_4_nodes = "nextflow kuberun Nine-s/rnasplice_TODO -r master -c " + path_to_config_files + "baseline_4_nodes.config"
command_baseline_8_nodes = "nextflow kuberun Nine-s/rnasplice_TODO -r master -c " + path_to_config_files + "baseline_8_nodes.config"
command_baseline_16_nodes = "nextflow kuberun Nine-s/rnasplice_TODO -r master -c " + path_to_config_files + "baseline_16_nodes.config"
daws_baseline_commandline = [command_baseline_4_nodes, command_baseline_8_nodes, command_baseline_16_nodes]

command_8_nodes_split_2 = "nextflow kuberun Nine-s/rnasplice_generated_modified_reduced_/ -r 8_nodes -c " + path_to_config_files + "exp_8_nodes_split_2.config"
command_16_nodes_split_2 = "nextflow kuberun Nine-s/rnasplice_generated_modified_reduced_/ -r 16_nodes -c " + path_to_config_files + "exp_16_nodes_split_2.config"

### RUN THE EXPERIMENTS

create_log_file()

for i in range(len(bandwidths)):
    run_tc_config(bandwidths[i])
    for j in range(len(nodes)):
        # run rewriten daw
        for replicate in range(2):
            start_time, end_time = run_one_experiment(daws_rewritten_commandline[j])
            move_trace_files(bandwidths[i], nodes[j], "rewritten", str(replicate+1))
            add_data_to_log(start_time, end_time, str(bandwidths[i]), nodes[j], "rewritten", str(replicate+1))
            remove_work_folder()

        # run baseline daw
        for replicate in range(2):
            start_time, end_time = run_one_experiment(daws_baseline_commandline[j])
            move_trace_files(bandwidths[i], nodes[j], "baseline", replicate+1)
            add_data_to_log(start_time, end_time, str(bandwidths[i]), nodes[j], "baseline", str(replicate+1))
            remove_work_folder()

        # run split 2 for 8 nodes
        if(j == 1):
            for replicate in range(2):
                start_time, end_time = run_one_experiment(command_8_nodes_split_2)

                move_trace_files(bandwidths[i], nodes[j], "rewritten", str(replicate+1))
                add_data_to_log(start_time, end_time, str(bandwidths[i]), nodes[j], "rewritten", str(replicate+1))
                remove_work_folder()

        # run split 2 for 16 nodes
        if(j == 2):
            for replicate in range(2):
                start_time, end_time = run_one_experiment(command_16_nodes_split_2)

                move_trace_files(bandwidths[i], nodes[j], "rewritten", str(replicate+1))
                add_data_to_log(start_time, end_time, str(bandwidths[i]), nodes[j], "rewritten", str(replicate+1))
                remove_work_folder()
