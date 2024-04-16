import os
import datetime

logname = "rnasplice_execution.log"

def run_tc_config(bandwidth):
    if (bandwidth is not None):
        my_command = "start_tc_config_command" + str(bandwidth) + "end_tc_config_command"
        runCommand(my_command) #TODO
        check_bandwidth(bandwidth) #???

def run_one_experiment(command):
    current_datetime = datetime.datetime.now()
    start_time = current_datetime.strftime("%d-%m-%y %H:%M")
    # TODO check what's best for prometheus
    runCommand(command) #TODO
    return start_time

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
    path_to_trace = ""
    path_to_trace_folders = ""
    #TODO

def remove_work_folder():
    path_to_work_folder = "" # TODO
    runCommand("rm -r " + path_to_work_folder)

bandwidths = [None, 1, 2, 10] #in Mb # TODO

nodes = [4, 8, 16]

path_to_config_files = "./TODO"

command_4_nodes = "nextflow kuberun Nine-s/rnasplice_generated_modified_reduced_/ -r 4_nodes -c " + path_to_config_files + " rnasplice_4_nodes.config"
command_8_nodes = "nextflow kuberun Nine-s/rnasplice_generated_modified_reduced_/ -r master -c " + path_to_config_files + " rnasplice_8_nodes.config"
command_16_nodes = "nextflow kuberun Nine-s/rnasplice_generated_modified_reduced_/ -r master -c " + path_to_config_files + " rnasplice_16_nodes.config"
daws_rewritten_commandline = [command_4_nodes, command_8_nodes, command_16_nodes]

command_baseline_4_nodes = "nextflow kuberun Nine-s/rnasplice_TODO -r master -c " + path_to_config_files + " rnasplice_basedaw.config"
command_baseline_8_nodes = "nextflow kuberun Nine-s/rnasplice_TODO -r master -c " + path_to_config_files + " rnasplice_basedaw.config"
command_baseline_16_nodes = "nextflow kuberun Nine-s/rnasplice_TODO -r master -c " + path_to_config_files + " rnasplice_basedaw.config"
daws_baseline_commandline = [command_baseline_4_nodes, command_baseline_8_nodes, command_baseline_16_nodes]

command_8_nodes_split_2 = "nextflow kuberun Nine-s/rnasplice_generated_modified_reduced_/ -r master -c " + path_to_config_files + " rnasplice_8_nodes_split_2.config"
command_16_nodes_split_2 = "nextflow kuberun Nine-s/rnasplice_generated_modified_reduced_/ -r master -c " + path_to_config_files + " rnasplice_16_nodes_split_2.config"
create_log_file()

for i in range(len(bandwidths)):
    run_tc_config(bandwidths[i])
    for j in range(len(nodes)):

        # run rewriten daw
        for replicate in range(2):
            start_time = run_one_experiment(daws_rewritten_commandline[j])
            end_time = check_if_daw_is_done()
            move_trace_files(bandwidths[i], nodes[j], "rewritten", str(replicate+1))
            add_data_to_log(start_time, end_time, str(bandwidths[i]), nodes[j], "rewritten", str(replicate+1))
            remove_work_folder()

        # run baseline daw
        for replicate in range(2):
            start_time = run_one_experiment(daws_baseline_commandline[j])
            end_time = check_if_daw_is_done()
            move_trace_files(bandwidths[i], nodes[j], "baseline", replicate+1)
            add_data_to_log(start_time, end_time, str(bandwidths[i]), nodes[j], "baseline", str(replicate+1))
            remove_work_folder()

        # run split 2 for 8 nodes
        if(j == 1):
            for replicate in range(2):
                start_time = run_one_experiment(command_8_nodes_split_2)
                end_time = check_if_daw_is_done()
                move_trace_files(bandwidths[i], nodes[j], "rewritten", str(replicate+1))
                add_data_to_log(start_time, end_time, str(bandwidths[i]), nodes[j], "rewritten", str(replicate+1))
                remove_work_folder()

        # run split 2 for 16 nodes
        if(j == 2):
            for replicate in range(2):
                start_time = run_one_experiment(command_16_nodes_split_2)
                end_time = check_if_daw_is_done()
                move_trace_files(bandwidths[i], nodes[j], "rewritten", str(replicate+1))
                add_data_to_log(start_time, end_time, str(bandwidths[i]), nodes[j], "rewritten", str(replicate+1))
                remove_work_folder()
        # clean pods?
        # check threads for baseline