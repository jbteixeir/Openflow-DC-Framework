from __future__ import division
from socket import socket, AF_INET, SOCK_STREAM
import cPickle as pickle
import random
import sys
import time
import threading
import math
import random


#Get Ip and Port addresses
IP = sys.argv[1]
PORT = int(sys.argv[2])
ADS = (IP, PORT)

#request_rate - interval between requests
request_rate = float(1/int(sys.argv[3]))

#average vm timeout
avg_timeout = int(sys.argv[4])

#Number of user types
num_usr_types = sys.argv[5]

#user type request percentage
usr_type_percentage = {}
previous_type = 0
for type in range(int(num_usr_types)):
    if previous_type == 0:
        usr_type_percentage[type] = (0, float(sys.argv[5+type]))
    # elif (type+1 == int(num_usr_types)):
    #     usr_type_percentage[type] = (previous_type, 1)
    else:
        usr_type_percentage[type] = (previous_type, previous_type+float(sys.argv[5+type]))

    previous_type = previous_type + float( sys.argv[6+type])
    
if usr_type_percentage[len(usr_type_percentage)-1][1] > 1:
    print "*** Sum of percentage of each user type request cannot be larger than 1."
    exit(0)

#print usr_type_percentage
tcpsoc = socket(AF_INET, SOCK_STREAM)

def nextTime(rateParameter):
    return -math.log(1.0 - random.random()) / rateParameter

def receiveVMAllocated(tcpsoc):
    while 1 :
        try :
            data = tcpsoc.recv(4096)
            print data
        except Exception, e:
            pass

def startVMRequester ():
    connected = 0
    while(1):
        print "Waiting for VM Request Receiver to connect... "
        while not connected:
            try:
                tcpsoc.connect(ADS)
                connected = 1
                print "Connection established"
            except Exception, e:
                #print "Connection not established"
                time.sleep(10)
                connected = 0
        
        timer = time.time()
        
        while 1:
            #send the requests based on statistics
            #sleep time = if the random function is perfect, 
            #time since last request == sleep_time
            timer = time.time()
            time_to_sleep = nextTime(request_rate)
            time.sleep(time_to_sleep)
            
            cpu = 1
            #cpu = random.randrange(1, 10)
            #ram = random.randrange(1, 32)
            #disk = random.randrange(5, 1000)
            ram = 0
            disk = 0
            #network = nextTime(1/(5))
            #network = (random.randrange(10, 100)/100)
            network = 1

            #type of request it is going to do
            request_type = random.randint(0,100)/100
            final_request_type = None

            #calculate a vm timeout
            tmp_avg_timeout = int(nextTime(1/avg_timeout))
            
            for usr_type in usr_type_percentage:
                if (request_type >= usr_type_percentage[usr_type][0] and request_type <= usr_type_percentage[usr_type][1]):
                    final_request_type = usr_type + 1

            #tcpsoc.sendall(pickle.dumps([cpu, ram, disk, network, final_request_type, tmp_avg_timeout]))
            tcpsoc.sendall(str(1)+"/"+str(cpu)+"/"+str(ram)+"/"+str(disk)+"/"+str(network)+"/"+str(final_request_type)+"/"+str(tmp_avg_timeout))
            print "Request Sent - CPU = ", cpu, ", RAM = ", ram, ", DISK = ", disk, ", Network = ", network, ", Request Type = ", final_request_type, "Timeout = ", tmp_avg_timeout

            print "Time since last request - ", int((time.time() - timer)), " sec\n"

        tcpsoc.close()

#start the thread to receive the confirmation of vm allocation
t2 = threading.Thread(target=receiveVMAllocated, args=(tcpsoc,))
t2.daemon = True
t2.start()

startVMRequester()
