#!/bin/python3
filename='edge-acls.txt'

#with open(filename, "r") as file_handle:
#    file_contents = file_handle.read()

import pyping
def ping(host):
    r = pyping.ping(host)
    if r.ret_code == 0:
        print("Success")
    else:
        print("Failed with {}".format(r.ret_code))

with open(filename) as topo_file:
    for line in topo_file:
        line=line.strip()
#        print(line)
        words=line.split(' ')
        ip=words[5]
        print(str(len(words))+": "+ip)
        ping(ip)
