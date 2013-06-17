#!/usr/bin/env python
'''log_analyzer.py parses event log generated by AWE and generates performance
results (in tables or figures)
This script is a rather dynamic. And some of the existing functions may be 
used for some specific analysis only. Users may use this as a template to write
new analysis functions for their own needs.'''

import datetime
import json
import matplotlib.pyplot as plt
import numpy as np
import sys
import time
from optparse import OptionParser

color_list = ['b', 'r', 'k', 'g', 'm', 'y']
stage_list = ["prep", "derep", "screen", "fgs", "uclust", "blat"]

DEFAULT_TOTALWORK = 1
CLIENT_QUOTA = 80

def parsePerfLog(filename):
    '''parse perf log'''
    raw_job_dict = {}
    wlf = open(filename, "r")
    
    job_dict = {}
    
    for line in wlf:
        total_data_move = 0
        total_compute = 0
        line = line.strip('\n')
        line = line.strip('\r')
        if len(line)==0:
            continue
        jsonstream = line[26:]
        data =  json.loads(jsonstream)
        #pprint(data)
        print "======="
        for key, val in data.iteritems():
            if key == 'Ptasks':
                for k in sorted(val.keys()):
                    print k, val[k]
            elif key == 'Pworks':
                for k in sorted(val.keys()):
                    print k, val[k]
                    total_data_move += val[k]['DataIn'] + val[k]['DataOut']
                    total_compute += val[k]['Runtime']
            else:
                print key, val
        job_dict[data['Id']] = data
        print "data movement overhead of job %s: %f" % (data['Id'], float(total_data_move) / (total_data_move + total_compute))
    print "%d completed jobs have been parsed from the perf log" % len(job_dict.keys())    
    return job_dict                       

def parseEventLog(filename):
    '''parse event log'''
    raw_job_dict = {}
    wlf = open(filename, "r")
    
    job_dict = {}
    
    for line in wlf:
        line = line.strip('\n')
        line = line.strip('\r')
        if len(line) == 0:
            continue
        if line[0] != "[":
            continue 
        
        timestr = line[1:20]
        
        timeobj = datetime.datetime.strptime(timestr, "%Y/%m/%d %H:%M:%S")
        timestamp = time.mktime(timeobj.timetuple())
        
        infostr = line.split()[4]
        parts = infostr.split(';')
        
        event = parts[0]
        
        attr = {}
        for item in parts[1:]:
            segs = item.split('=')
            key = segs[0]
            val = segs[1]
            attr[key] = val
       
        if event == "JQ":  #job submitted
            job = {}
            id =  attr['jobid']
            job['id'] = id
            job['jid'] = attr['jid']
            job['submit'] = timestamp
            job['total_task'] = 0
            job['task_list'] = []
            job_dict[id] = job
            
        if event == "TQ" or event == "TD":  # task enqueue
            taskid = attr['taskid']
            segs = taskid.split('_')
            jobid = segs[0]
            stage = int(segs[1])
            if not job_dict.has_key(jobid):
                continue
            
            job = job_dict[jobid]
            anchor = job['submit']
            
            if event == "TQ":
                task_interval = [timestamp-anchor, 0]
                if stage == job['total_task']: #record the first TQ
                    job['task_list'].append(task_interval) 
                    job['total_task'] += 1
                else:
                    del job_dict[jobid]
                    continue   # ignore jobs that have task re-queued for now
            else:
                job['task_list'][-1][1] = timestamp-anchor
                
                
        if event == "JD":
            id =  attr['jobid']
            if not job_dict.has_key(jobid):
                continue
            job_dict[id]['end'] = timestamp
            
        
    for key, value in job_dict.items():
        if not value.has_key('end'):
            del job_dict[key]
        else:
            value['time_points'] = [0]
            anchor = job['submit']
            for item in job['task_list']:
                timepoint = item[0] - anchor              
     
    print "%d completed jobs have been parsed from the event log" % len(job_dict.keys())    
         
    return job_dict                       


def draw_task_runtime_bar_charts(job_dict):
    '''input job_dict, depict task runtime bar chart for each job'''
    stage_list = ["prep", "derep", "screen", "fgs", "uclust", "blat"]
    for id, job in job_dict.items():
        runtime_list = []
        for item in job['task_list']:
            runtime_list.append(item[1]-item[0])
        draw_taskrun_bar_chart_single(job['jid'], runtime_list, stage_list)
    
def draw_taskrun_bar_chart_single(name, runtime_list, stage_list):
    '''draw task running time bar chart for a single job'''
    N = len(runtime_list)
    ind = np.arange(N)
    
    fig = plt.figure()
    ax = fig.add_subplot(111)
    rects = ax.bar(ind, runtime_list)
    width = 0.35       # the width of the bars

    
    ax.set_ylabel('running time (sec)')
    ax.set_title('running time by each stages')
    ax.set_xticks(ind + width)
    ax.set_xticklabels( stage_list )
    
    def autolabel(rects):
        # attach some text labels
        for rect in rects:
            height = rect.get_height()
            ax.text(rect.get_x()+rect.get_width()/2., 1.0*height, '%d'%int(height),
                    ha='center', va='bottom')
    
    autolabel(rects)
    fig.savefig("%s.png" % name)
    
def draw_task_bars(bins, stage_list, name):

    N = len(stage_list)
    
    ind = np.arange(N)  # the x locations for the groups
    width = 0.15       # the width of the bars
    pad = 0.15

    fig = plt.figure()
    ax = fig.add_subplot(111)
    rects = []
    i = 0
    num_colors = len(color_list)
    for key in bins.keys():
        bin = bins[key]
        rects.append(ax.bar(pad + ind+width*i, bin, width, color=color_list[i % num_colors]))
        i += 1
    
    # add some
    ax.set_ylabel('running time (sec)')
    ax.set_title('running time by each stages')
    ax.set_xticks(pad + ind + width)
    ax.set_xticklabels(stage_list)
    #ax.set_yscale('log')

    #ax.legend( (rects[0][0], rects[1][0]), ('Men', 'Women') )

    fig.savefig("%s.png" % name)
    
def print_task_runtime_table(job_dict):
    for id, job in job_dict.items():
        line = ""
        line += job['jid'] + ","
        for item in job['task_list']:
            runtime = item[1] - item[0]
            line += "%d," % runtime
        line = line[:-1]
        print line
        
def parse_workload(filename):
    raw_job_dict = {}
    wlf = open(filename, "r")
    
    job_dict = {}
    
    i = 1
    starttime = 0
    
    jobload = []
    taskload = []
    workload = []
    
    jobct = 0
    taskct = 0
    workct = 0    
    
    for line in wlf:
        line = line.strip('\n')
        line = line.strip('\r')
        if len(line) == 0:
            continue
        if line[0] != "[":
            continue 
        
        timestr = line[1:20]
        
        timeobj = datetime.datetime.strptime(timestr, "%Y/%m/%d %H:%M:%S")
        unixtime = int(time.mktime(timeobj.timetuple()))
        
        if i==1:
            starttime = unixtime
        
        timestamp = unixtime - starttime
        
        infostr = line.split()[4]
        parts = infostr.split(';')
        
        event = parts[0]
                        
        attr = {}
        for item in parts[1:]:
            segs = item.split('=')
            key = segs[0]
            val = segs[1]
            attr[key] = val
            
        if event == "JQ":  #job submitted
            jobct += 1
            taskct += 6
        elif event == "JD":
            jobct -= 1
        elif event == "TQ":
            workct += int(attr.get("totalwork", DEFAULT_TOTALWORK))
        elif event == "TD":
            taskct -= 1
        elif event == "WD":
            workct -= 1
            
        if event in ["JQ", "JD"]:
            jobload.append((timestamp, jobct))
        if event in ["JQ", "TD"]:
            taskload.append((timestamp, taskct))
        if event in ["TQ", "WD"]:
            workload.append((timestamp, workct))
            
        i += 1
        
    return jobload, taskload, workload

def plot_workload(workload, name):
    print "plotting: workload"
    print len(workload), workload[-1]
    fig = plt.figure()
    ax = fig.add_subplot(111)
    plt.title("number of active workunits (queuing + running)")
    interval = 5
    max_point = workload[-1][0] / interval
    timepoint = 0
    timepoints = []
    workct = []
    maxjob = 0
    lastpoint = 0
    for i in range(0, max_point+1):
        timepoint = i * interval
        j = lastpoint
        
        while timepoint >= workload[j][0]:
            j += 1
            if j == len(workload):
                break
        lastpoint = j - 1
        if lastpoint < 0:
            lastpoint = 0
        print timepoint, workload[lastpoint][1], workload[lastpoint]
        workct.append(workload[lastpoint][1])
        timepoints.append(i * interval)
        #print timepoint, workct[i]

    busyclient = []
    for ct in workct:
        if ct >= CLIENT_QUOTA:
            busyclient.append(CLIENT_QUOTA)
        else:
            busyclient.append(ct)
    
    timepoints.append(timepoints[-1] + interval)
    busyclient.append(0)
    workct.append(0)
    
    ax.plot(timepoints, workct, color = "b", lw=1.5)
    ax.plot(timepoints, [CLIENT_QUOTA for i in range(0, len(timepoints))], color = "r")
    ax.fill_between(timepoints, 0, busyclient)
    #ax.set_ylim(0, 160)
    #ax.set_xlim(0, 30000)
    ax.set_xlabel('time elapsed (sec)')
    ax.grid(True)
    print "max_timepoint=", timepoints[-1]
    plt.savefig(name+".eps")

if __name__ == "__main__":
    p = OptionParser()
    p.add_option("-e", dest = "eventlog", type = "string", 
                    help = "path of event log file")
    
    p.add_option("-p", dest = "perflog", type = "string", 
                    help = "path of perf log file")
    
    p.add_option("-w", dest = "workload", action = "store_true", default = False,
                    help = "draw workload running graph, used with -e")
    
    p.add_option("-r", "--rawjobs", dest = "rawjobs", \
            action = "store_true", \
            default = False, \
            help = "show raw job dict parsed from the event log")
        
    p.add_option("-b", "--bars", dest = "taskbars", \
            action = "store_true", \
            default = False, \
            help = "draw bar chart of task runtime for a list of jobs")
    
    p.add_option("--each", dest = "each", \
            action = "store_true", \
            default = False, \
            help = "draw bar charts of task runtimes for each job")
    
    p.add_option("-t", "--taskcsv", dest = "taskcsv", \
            action = "store_true", \
            default = False, \
            help = "print task runtime .csv, (jobid, task_1_runtime, task_2_runtime, ...)")
    
    (opts, args) = p.parse_args()
    
    if not opts.eventlog and not opts.perflog:
        print "please specify path of either event log file (-e) or perf log file (-p)"
        p.print_help()
        exit()

    
    job_dict = {}
    
    if opts.eventlog:
        job_dict = parseEventLog(opts.eventlog)
    elif opts.perflog:
        job_dict = parsePerfLog(opts.perflog)
        
    if opts.taskbars:
        bins = {}
        for id, job in job_dict.items():
            jid = job['jid']
            bin = []
            for item in job['task_list']:
                runtime = item[1] - item[0]
                bin.append(runtime)
            bins[jid] = bin
        draw_task_bars(bins, stage_list, 'task_runtime')
        
    if opts.each:
        draw_task_runtime_bar_charts(job_dict)
    
    if opts.rawjobs:
        for key, value in job_dict.items():
            print key, value
    
    if opts.taskcsv:
        print_task_runtime_table(job_dict)
        
    if opts.workload:
        if not opts.eventlog:
            print "workload parsing (-w) needs to specify event log (-e)"
            exit()
        jobload, taskload, workload = parse_workload(opts.eventlog)
        
        #for load in workload:
        #    print load[0], load[1]
        #print "========="        
        #for load in taskload:
        #    print load[0], load[1]
        #print "========="
        #for load in jobload:
        #    print load[0], load[1]
            
        plot_workload(workload, opts.eventlog.split(".")[0])
        
        
        
        
        
    
    