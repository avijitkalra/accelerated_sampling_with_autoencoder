"""
This program takes a "terminal command" (should be within quotation mark) as an argument, 
generate corresponding sge file, and qsub it.
"""


import argparse, subprocess, os

parser = argparse.ArgumentParser()
parser.add_argument("command", type=str, help="command to run")
parser.add_argument("--submit", help="submit the job", action="store_true")
parser.add_argument('--gpu', help="whether to run on GPU", action="store_true")
parser.add_argument("--node", type=int, default=2)
args = parser.parse_args()

whether_to_qsub = args.submit
command_in_sge_file = args.command.strip()
if args.gpu:
    gpu_option_string = '#$ -l gpu=1'
else:
    gpu_option_string = ''

if command_in_sge_file[-1] == '&':    # need to remove & otherwise it will not work in the cluster
    command_in_sge_file = command_in_sge_file[:-1]

content_for_sge_file = '''#!/bin/bash

#$ -S /bin/bash           # use bash shell
#$ -V                     # inherit the submission environment 
#$ -cwd                   # start job in submission directory

#$ -m ae                 # email on abort, begin, and end
#$ -M wei.herbert.chen@gmail.com         # email address

#$ -q all.q               # queue name
#$ -l h_rt=240:00:00       # run time (hh:mm:ss)

%s

#$ -l hostname=compute-0-%d

%s

echo "This job is DONE!"

exit 0
''' % (gpu_option_string, args.node, command_in_sge_file)

folder_to_store_sge_files = '../sge_files/'

if not os.path.exists(folder_to_store_sge_files):
    subprocess.check_output(['mkdir', folder_to_store_sge_files])

assert (os.path.exists(folder_to_store_sge_files))

sge_filename = folder_to_store_sge_files + command_in_sge_file.replace(' ', '_').replace('..', '_').replace('/','_').replace('&', '') + '.sge'

with open(sge_filename, 'w') as sge_file:
    sge_file.write(content_for_sge_file)

if whether_to_qsub:
    subprocess.check_output(['qsub', sge_filename])
