from socket import socket, AF_INET, SOCK_STREAM
import cPickle as pickle
import random
import sys
import time
import threading

#Get Ip and Port addresses
IP = sys.argv[1]
PORT = int(sys.argv[2])
ADS = (IP, PORT)

#request_rate - requestes per hour
request_rate = int(sys.argv[3])
#sleep_time - time interval between requests
sleep_time = 3600 / request_rate

tcpsoc = socket(AF_INET, SOCK_STREAM)

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
			request = random.randrange(1, sleep_time)
			if request == 1:
		
				cpu = random.randrange(1, 100)
				#ram = random.randrange(1, 32)
				#disk = random.randrange(5, 1000)
				ram = 0
				disk = 0
				network = random.randrange(0, 2)
		
				tcpsoc.sendall(pickle.dumps([cpu, ram, disk, network]))
				print "Request Sent - CPU = ", cpu, ", RAM = ", ram, ", DISK = ", disk, ", Network = ", network
				print "Time since last request - ", int((time.time() - timer)), " sec\n"
				timer = time.time()
			else:
				time.sleep(1)
		tcpsoc.close()

#start the thread to receive the confirmation of vm allocation
t2 = threading.Thread(target=receiveVMAllocated, args=(tcpsoc,))
t2.daemon = True
t2.start()

startVMRequester()
	
		