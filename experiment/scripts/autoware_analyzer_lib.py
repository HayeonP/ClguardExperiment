import csv
import yaml
import rosbag
import math
import os
import signal
import subprocess
import matplotlib.pyplot as plt

def save_dict(data, path):
    with open(path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False)
    return

def subsctract_dicts(data1, data2):
    output = {}
    keys = data1.keys()
    for k in keys:
        if k not in data2: continue
        output[k] = data1[k] - data2[k]
    return output

def get_dict_avg(data):
    sum = 0.0
    for key in data:
        sum = sum + float(data[key])
    return sum / float(len(data))

def get_dict_max(data):
    max = 0.0
    for key in data:
        v = float(data[key])
        if v > max: max = v
    return max

def read_topics_from_bag(rosbag_path, topic_name):
    print(rosbag_path)
    bag = rosbag.Bag(rosbag_path)
    output = []
    for _, msg, _ in bag.read_messages():        
        output.append(msg)
    return output

def get_instance_pair_by_x(center_offset_path, start_x, end_x):
    output_start_instance = -1.0
    output_end_instance = -1.0
    with open(center_offset_path) as f:
        reader = csv.reader(f)

        for i, line in enumerate(reader):
            if i == 0: continue
            instance = float(line[4])
            x = float(line[5])
            if start_x > end_x:
                if x < start_x and output_start_instance < 0: output_start_instance = instance
                if x < end_x and output_end_instance < 0: output_end_instance = instance
            else:
                if x > start_x and output_start_instance < 0: output_start_instance = instance
                if x > end_x and output_end_instance < 0: output_end_instance = instance
    # print(output_start_instance, output_end_instance)
    return output_start_instance, output_end_instance    

def get_E2E_response_time(first_node_path, last_node_path, E2E_start_instance, E2E_end_instance, type):
    if type != 'shortest' and type != 'longest':
        print('[ERROR] Invalidate type:', type)
        exit()

    instance_info = {}
    start_instance = -1
    E2E_response_time = {}

    # E2E Response Time
    with open(last_node_path) as f_last:
        reader = csv.reader(f_last)        
        for i, row in enumerate(reader):            
            if i == 0: continue # Skip first row

            end_time = float(row[3])
            instance_id = int(row[4])
            if type == 'shortest':
                if instance_id in instance_info: continue
            if i == 1: start_instance = instance_id         
            instance_info[instance_id] = {'start_time': -1.0, 'end_time': end_time}

    with open (first_node_path) as f_start:        
        reader = csv.reader(f_start)
        for i, row in enumerate(reader):
            
            if i == 0: continue # Skip first row            
            
            start_time = float(row[2])
            instance_id = int(row[4])
            if instance_id < start_instance: continue
            if instance_id not in instance_info: continue
            if type == 'shortest':
                if instance_info[instance_id]['start_time'] > 0: continue
            instance_info[instance_id]['start_time'] = start_time
    for instance_id in instance_info:
        response_time = instance_info[instance_id]['end_time'] - instance_info[instance_id]['start_time']        
        E2E_response_time[instance_id] = float(response_time * 1000) # unit: ms

    keys = list(E2E_response_time.keys())

    does_start_instance_found = False    
    for key in keys:
        if key > E2E_start_instance and not does_start_instance_found:
            E2E_start_instance = key
            does_start_instance_found = True
            continue             
        E2E_end_instance = key               
        if key > E2E_end_instance and E2E_end_instance > 0.0: break        
    remove_target = []
    for k in E2E_response_time:
        if k < E2E_start_instance or k > E2E_end_instance or k not in keys: remove_target.append(k)        
    
    for k in remove_target: E2E_response_time.pop(k, None)

    avg_E2E_response_time = get_dict_avg(E2E_response_time)
    max_E2E_response_time = get_dict_max(E2E_response_time)

    return E2E_response_time, max_E2E_response_time, avg_E2E_response_time

def start_rosbag_record(topic_names):   
    topic_str = '' 
    for topic in topic_names:
        topic_str = topic_str + ' ' + topic

    subprocess.Popen('source /opt/ros/melodic/setup.bash && rosbag record -O output' + topic_str, shell=True, executable='/bin/bash')
    return

def get_center_offset(center_offset_path):
    center_offset = {}
    with open(center_offset_path) as f:
        reader = csv.reader(f)
        for i, line in enumerate(reader):
            if i == 0: continue
            instance = float(line[4])
            center_offset[instance] = abs(float(line[2]))

    max_center_offset = get_dict_max(center_offset)
    avg_center_offset = get_dict_avg(center_offset)

    return center_offset, max_center_offset, avg_center_offset

def get_waypoints(center_offset_path):
    waypoints = []
    with open(center_offset_path) as f:
        reader = csv.reader(f)
        for i, line in enumerate(reader):
            if i == 0: continue
            pose_x = float(line[5])
            pose_y = float(line[6])
            waypoints.append([pose_x,pose_y])
    
    return waypoints

def get_center_line(center_line_path):
    center_line = []
    with open(center_line_path) as f:
        reader = csv.reader(f)
        for i, line in enumerate(reader):
            if i == 0: continue
            pose_x = float(line[0])
            pose_y = float(line[1])
            center_line.append([pose_x,pose_y])
    
    return center_line

def get_experiment_info(experiment_info_path):
    experiment_info = {}
    with open(experiment_info_path, 'r') as f:
        experiment_info = yaml.safe_load(f)
    return experiment_info

def stop_rosbag_record():
    _output = str(os.popen('ps au | grep rosbag').read())
    _output = _output.split('\n')
    for line in _output:    
        if not '/opt/ros/melodic/bin/rosbag' in line: continue
        pid = -1
        for v in line.split(' '):
            try: pid = int(v)
            except: continue        
            break

        if pid != -1: os.kill(pid, signal.SIGINT)

def get_number_of_files(path):
    output = str(os.popen('ls ' + path).read())
    output = output.split('\n')
    return len(output) - 1

def check_matching_is_failed(center_offset_path, start_instance, end_instance):    
    with open(center_offset_path) as f:
        reader = csv.reader(f)
        for i, line in enumerate(reader):
            if i == 0: continue
            instance = int(line[4])
            ndt_score = float(line[7])
            if instance < start_instance: continue
            if ndt_score > 2.0: return True
            if instance > end_instance: break
            
    return False

def mouse_event(event):
    print('x: {} and y: {}'.format(event.xdata, event.ydata))
    return

def convert_boolean_list_to_int_list(list_of_booleans):    
    return [int(item) for item in list_of_booleans]

def get_idices_of_one_from_list(input, reverse=False):
    output = []
    for i, v in enumerate(input):
        if reverse: v = 2**v%2
        if v: output.append(i)
    return output

def merge_binary_list_to_idx_list(a, b):
    output = []
    for i,_ in enumerate(a):
        if a[i] == 1 or b[i] == 1: output.append(i)
    return output
    

