import os
import datetime
import time
import subprocess
from kubernetes import client, config, stream
from kubernetes.stream import stream

# PVC paths
my_pvc_path = "/data/rnaseq/"
path_to_work_folder = "/data/rnaseq/" 
path_to_trace_files = "/data/rnaseq/" 
path_to_trace_folders = "/data/rnaseq/rnasplice_experiments_traces/"

# K8S config
path_to_nextflow = "/home/rnaseq/nextflow"
name_of_volume = "nextflow-ninon"  
namespace = "default"
helper_pod = "ubuntu-pod"
helper_container = "ubuntu-pod"

# Load the Kubernetes configuration
config.load_kube_config('/home/rnaseq/kubeconfig')

# Create an API client
api = client.CoreV1Api()

def check_pod_status(pod_name):
    pod = api.read_namespaced_pod_status(pod_name, namespace)
    return pod.status.phase

def move_files_in_pod(namespace, pod_name, src, dest):

    # Command to be executed in the pod
    cmd = ['sh', '-c', f'mv {src} {dest}']

    try:
        # Connecting to the pod and executing the command
        resp = stream(api.connect_get_namespaced_pod_exec, pod_name, namespace,
                      command=cmd, stderr=True, stdin=False,
                      stdout=True, tty=False)
        print("Files moved successfully:")
        print(resp)
    except Exception as e:
        print("Failed to move files:")
        print(str(e))

def delete_work_folder_in_pod(namespace, pod_name, path_to_work_folder):

    # Command to be executed in the pod
    cmd = ['sh', '-c', f'rm -r {path_to_work_folder}work']

    try:
        # Connecting to the pod and executing the command
        resp = stream(api.connect_get_namespaced_pod_exec, pod_name, namespace,
                      command=cmd, stderr=True, stdin=False,
                      stdout=True, tty=False)
        print("Files moved successfully:")
        print(resp)
    except Exception as e:
        print("Failed to move files:")
        print(str(e))

def create_folder_in_pod(namespace, pod_name, path, dirname):

    # Command to be executed in the pod
    cmd = ['sh', '-c', f'mkdir -p {path}{dirname}']

    try:
        # Connecting to the pod and executing the command
        resp = stream(api.connect_get_namespaced_pod_exec, pod_name, namespace,
                      command=cmd, stderr=True, stdin=False,
                      stdout=True, tty=False)
        print("Files moved successfully:")
        print(resp)
    except Exception as e:
        print("Failed to move files:")
        print(str(e))

def execute_command_in_container(input_command):
    try:
        response = stream(api.connect_get_namespaced_pod_exec, helper_pod, namespace, command=['/bin/bash', '-c', input_command], container=helper_container, stderr=True, stdout=True)
        if response:
            print(f"Response: {response}")
        else:
            print("Empty response received. This does not indicate an error.")
    except Exception as e:
        print(f"An error occurred while executing the command: {e}")



def run_tc_config(bandwidth):
    # Setting the bandwidth for all nodes except the metadata servers
    list_of_nodes = ['hu-worker-c24', 'hu-worker-c25', 'hu-worker-c26', 'hu-worker-c27', 'hu-worker-c28',
     'hu-worker-c29', 'hu-worker-c30', 'hu-worker-c31', 'hu-worker-c32', 'hu-worker-c33',
     'hu-worker-c34', 'hu-worker-c35', 'hu-worker-c36', 'hu-worker-c37', 'hu-worker-c38',
     'hu-worker-c39', 'hu-worker-c40', 'hu-worker-c41', 'hu-worker-c42', 'hu-worker-c43']
    inventory_path = '/home/rnaseq/rnasplice_exp/hosts'
    module = 'command'

    # Create an inventory file
    with open(inventory_path, 'w') as file:
        file.write('[all_nodes]\n')
        for node in list_of_nodes:
            file.write(f"{node}\n")


    if not bandwidth:    
        args = 'tcdel eno2np1 --all'
        print(args)
        try:
            # Delete any existing configuration
            result = subprocess.run(
                ['ansible', 'all_nodes', '-i', inventory_path, '-m', module, '-a', args, '--become', '-u', 'root'],
                check=True,  # Check for errors
                text=True,  # Get output as text
                capture_output=True  # Capture output
            )
            print(result)
        except subprocess.CalledProcessError as e:
            return e.stderr
        return

    if (bandwidth is not None):
        args = 'tcdel eno2np1 --all'
        print(args)
        try:
            # Delete any existing configuration
            result = subprocess.run(
                ['ansible', 'all_nodes', '-i', inventory_path, '-m', module, '-a', args, '--become', '-u', 'root'],
                check=True,  # Check for errors
                text=True,  # Get output as text
                capture_output=True  # Capture output
            )
            print(result)
        except subprocess.CalledProcessError as e:
            return e.stderr

        # Set limit on outgoing
        args = 'tcset eno2np1 --direction outgoing --rate ' + bandwidth
        print(args)
        try:
            # Delete any existing configuration
            result = subprocess.run(
                ['ansible', 'all_nodes', '-i', inventory_path, '-m', module, '-a', args, '--become', '-u', 'root'],
                check=True,  # Check for errors
                text=True,  # Get output as text
                capture_output=True  # Capture output
            )
            print(result)
        except subprocess.CalledProcessError as e:
            return e.stderr

        # Set limit on outgoing
        args = 'tcset eno2np1 --direction incoming --rate ' + bandwidth
        print(args)
        try:
            # Delete any existing configuration
            result = subprocess.run(
                ['ansible', 'all_nodes', '-i', inventory_path, '-m', module, '-a', args, '--become', '-u', 'root'],
                check=True,  # Check for errors
                text=True,  # Get output as text
                capture_output=True  # Capture output
            )
            print(result)
        except subprocess.CalledProcessError as e:
            return e.stderr

def run_one_experiment(command):
    current_datetime = datetime.datetime.now()
    start_time = current_datetime.strftime("%d-%m-%y_%H-%M")
    print(command)
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True) 
    output_lines = result.stdout.splitlines()
    print(output_lines)
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
        log.write(str(start_time) + "\t" + str(end_time) + "\t" + str(bandwidth) + "\t" + str(node) + "\t" + str(exp) + "\t" + str(replicate) + "\n")
    return

def check_if_daw_is_done():
    return True

def move_trace_files(bandwidth, nodes, daw_type, replicate):
    path_to_right_trace_folder = path_to_trace_folders + "rnasplice_exp_traces" + "/" + str(bandwidth)  + "/" + str(nodes)  + "/" + str(daw_type)  + "/" + str(replicate)  + "/" 
    create_folder_in_pod(namespace, helper_pod, "" , path_to_right_trace_folder)
    move_files_in_pod(namespace, helper_pod, path_to_trace_files + "_*", path_to_right_trace_folder)

def remove_work_folder(): 
    delete_work_folder_in_pod(namespace, helper_pod, path_to_work_folder)

### START

# NODES
exp_4_nodes = ["hu-worker-c24","hu-worker-c25","hu-worker-c26","hu-worker-c27"]
exp_8_nodes_TODO = ["hu-worker-c24","hu-worker-c25","hu-worker-c26","hu-worker-c27","hu-worker-c28","hu-worker-c23","hu-worker-c43","hu-worker-c40"]
exp_16_nodes = ["hu-worker-c23","hu-worker-c24","hu-worker-c25","hu-worker-c26","hu-worker-c27","hu-worker-c28","hu-worker-c29","hu-worker-c30","hu-worker-c34","hu-worker-c35","hu-worker-c36","hu-worker-c37","hu-worker-c38","hu-worker-c39","hu-worker-c40","hu-worker-c41"]

exp_4_nodes_addresses = ["10.0.0.24:9100","10.0.0.25:9100","10.0.0.26:9100","10.0.0.27:9100"]
exp_8_nodes_addresses = ["10.0.0.24:9100","10.0.0.25:9100","10.0.0.26:9100","10.0.0.27:9100","10.0.0.28:9100","10.0.0.34:9100","10.0.0.35:9100","10.0.0.36:9100"]
exp_16_nodes_addresses = ["10.0.0.23:9100","10.0.0.24:9100","10.0.0.25:9100","10.0.0.26:9100","10.0.0.27:9100","10.0.0.28:9100","10.0.0.29:9100","10.0.0.30:9100","10.0.0.34:9100","10.0.0.35:9100","10.0.0.36:9100","10.0.0.37:9100","10.0.0.38:9100","10.0.0.39:9100","10.0.0.40:9100","10.0.0.41:9100"]

# PATHS
logname = "rnasplice_execution.log"
path_to_config_files = "/home/rnaseq/rnasplice_exp/" 

# EXP PARAMETERS
#bandwidths = [None, 1, 2, 10] #in Mb # TODO
#nodes = [4, 8, 16] # TODO
#replicates_number = 2 # TODO

bandwidths = ['', '1Gbs'] # temporary for testing
nodes = [4, 8, 16] # temporary for testing
replicates_number = 1

command_4_nodes = "/home/rnaseq/nextflow kuberun Nine-s/rnasplice_generated_modified_reduced_/ -r 4_nodes -c " + path_to_config_files + "exp_4_nodes.config"
command_8_nodes = "/home/rnaseq/nextflow kuberun Nine-s/rnasplice_generated_modified_reduced_/ -r 8_nodes -c " + path_to_config_files + "exp_8_nodes.config"
command_16_nodes = "/home/rnaseq/nextflow kuberun Nine-s/rnasplice_generated_modified_reduced_/ -r 16_nodes -c " + path_to_config_files + "exp_16_nodes.config"
daws_rewritten_commandline = [command_4_nodes, command_8_nodes, command_16_nodes]

command_baseline_4_nodes = "/home/rnaseq/nextflow kuberun Nine-s/generated_workflow_reduced -r master -c " + path_to_config_files + "baseline_4_nodes.config"
command_baseline_8_nodes = "/home/rnaseq/nextflow kuberun Nine-s/generated_workflow_reduced -r master -c " + path_to_config_files + "baseline_8_nodes.config"
command_baseline_16_nodes = "/home/rnaseq/nextflow kuberun Nine-s/generated_workflow_reduced -r master -c " + path_to_config_files + "baseline_16_nodes.config"
daws_baseline_commandline = [command_baseline_4_nodes, command_baseline_8_nodes, command_baseline_16_nodes]

#TOFIX
#command_8_nodes_split_2 = "/home/rnaseq/nextflow kuberun Nine-s/rnasplice_generated_modified_reduced_/ -r 8_nodes -c " + path_to_config_files + "exp_8_nodes_split_2.config"
command_16_nodes_split_2 = "/home/rnaseq/nextflow kuberun Nine-s/rnasplice_generated_modified_reduced_/ -r 16_nodes -c " + path_to_config_files + "exp_16_nodes_split_2.config"
command_16_nodes_split_4 = "/home/rnaseq/nextflow kuberun Nine-s/rnasplice_generated_modified_reduced_/ -r 16_nodes -c " + path_to_config_files + "exp_16_nodes_split_4.config"
command_16_nodes_split_8 = "/home/rnaseq/nextflow kuberun Nine-s/rnasplice_generated_modified_reduced_/ -r 16_nodes -c " + path_to_config_files + "exp_16_nodes_split_8.config"




### RUN THE EXPERIMENTS

create_log_file()

for i in range(len(bandwidths)):
    run_tc_config(bandwidths[i])
    for j in range(len(nodes)):
        #run rewriten daw
        # for replicate in range(replicates_number):
        #     start_time, end_time = run_one_experiment(daws_rewritten_commandline[j])
        #     move_trace_files(bandwidths[i], nodes[j], "rewritten", str(replicate))
        #     add_data_to_log(start_time, end_time, str(bandwidths[i]), nodes[j], "rewritten", str(replicate))
        #     remove_work_folder()

        # run baseline daw
        for replicate in range(replicates_number):
            start_time, end_time = run_one_experiment(daws_baseline_commandline[j])
            move_trace_files(bandwidths[i], nodes[j], "baseline", replicate)
            add_data_to_log(start_time, end_time, str(bandwidths[i]), nodes[j], "baseline", str(replicate))
            remove_work_folder()

        # run different splits for 16 nodes
        # if(j == 2):
        #     for replicate in range(replicates_number):
        #         start_time, end_time = run_one_experiment(command_16_nodes_split_8)

        #         move_trace_files(bandwidths[i], nodes[j], "rewritten", str(replicate))
        #         add_data_to_log(start_time, end_time, str(bandwidths[i]), nodes[j], "rewritten", str(replicate))
        #         remove_work_folder()
            
        #     for replicate in range(replicates_number):
        #         start_time, end_time = run_one_experiment(command_16_nodes_split_4)

        #         move_trace_files(bandwidths[i], nodes[j], "rewritten", str(replicate))
        #         add_data_to_log(start_time, end_time, str(bandwidths[i]), nodes[j], "rewritten", str(replicate))
        #         remove_work_folder()

        #     for replicate in range(replicates_number):
        #         start_time, end_time = run_one_experiment(command_16_nodes_split_2)

        #         move_trace_files(bandwidths[i], nodes[j], "rewritten", str(replicate))
        #         add_data_to_log(start_time, end_time, str(bandwidths[i]), nodes[j], "rewritten", str(replicate))
        #         remove_work_folder()
