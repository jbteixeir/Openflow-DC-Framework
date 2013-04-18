from pox.lib.revent.revent import EventMixin, Event
from pox.core import core
from ext.ERCSTopology import ercs_topology
from socket import *
import cPickle as pickle
import threading
import thread
import time
import os

from time import sleep
log = core.getLogger()

class VMRequest (Event) :
    '''
    TODO: maybe in the future include IO
    '''
    def __init__ (self, time, cpu, ram, disk, network, request_type) :
        Event.__init__(self)
        self.time = time
        self.cpu = cpu
        self.ram = ram
        self.disk = disk
        self.network = network
        self.request_type = request_type


class VMReceiver (EventMixin, threading.Thread):
    '''
    Raises an event every time a new request arrives
    '''
    _eventMixin_events = set([
                          VMRequest,
                          ])
    
    def __init__(self, inithandler=None):
        threading.Thread.__init__(self)
        self.request_history = {}
        self.ip = ""
        self.port = ""
        self.socket_tp = None
        
        if inithandler == None :
            self.askForArgs()
        else :
            self.getArgsFromIni(inithandler)

        #Start thread that Connect to the topology generator
        log.info("Connecting to topology generator...")
        thread.start_new_thread(self.connectToTopologyGenerator, ())
        log.info("Connecting to topology generator... DONE")
    
    def askForArgs(self):
        #ask for ip and port to bind to
        addr = raw_input("VM RECEIVER: Insert ip address:port for listening to VM requests (ex:127.0.0.1:6633): ")
        
        #check if they were well introduced
        if len(addr.split(":",1)) == 2:
            self.ip = addr.split(":",1)[0] 
            self.port = int(addr.split(":",1)[1])
        while not isIPandPort(self.ip, self.port):
            addr = raw_input("VM RECEIVER: Please insert Ip Address and port in the correct format (ex:127.0.0.1:6633): ")
            if len(addr.split(":",1)) == 2:
                self.ip = addr.split(":",1)[0] 
                self.port = int(addr.split(":",1)[1])
    
    def getArgsFromIni(self, inithandler):
        try :
            section = "vmreceiver"
            key = "ip"
            self.ip = inithandler.read_ini_value(section, key)
            key = "port"
            self.port = int(inithandler.read_ini_value(section, key))
            
            log.debug("Successfully got vmreceiver values")
        except Exception, e :
            log.error("INI File doesn't contain expected values")
            print e
            os._exit(0)
            
    def run(self):

        #Start thread that accepts connections and handles the VM Requests
        thread.start_new_thread(self.connectToRequester, ())
        
        #Start the thread that notifies the VM Requester when the VM was allocated 
        
    def notifyVMAllocation(self, new_vm_caract, holding_time = None, new_vm_ip = None, core_candidate = None, 
            agg_candidate = None, edge_candidate = None, ouside_host_ip = None):

        log.debug("Notifying VM Requester of new VM Allocation...")
        if new_vm_ip == None or core_candidate == None or agg_candidate == None or edge_candidate == None:
            data = "VM Allocation FAIL - Request Type = %s, CPU = %s, RAM = %s, DISK = %s \n" %  (new_vm_caract[len(new_vm_caract)-1], 
                    new_vm_caract[0], new_vm_caract[1], new_vm_caract[2])
        else:
            data = "VM Allocation SUCESS - Request Type = %s, CPU = %s, RAM = %s, DISK = %s \n CoreS = %s, AggS = %s, EdgeS = %s, HostIP = %s\n" % (new_vm_caract[4], new_vm_caract[0], new_vm_caract[1], 
                new_vm_caract[2], core_candidate, agg_candidate, edge_candidate, new_vm_ip)
            try:
                #NOtify host to start sending traffic to this new ip
                log.debug("Notifying Outside host to start sending traffic for new VM...")    
                #s.sendall(str(new_vm_ip)+"/"+str(new_vm_caract[3])+"/"+str(holding_time)+"/"+str(core_candidate))
                #adata = str(new_vm_ip)+"/"+str(new_vm_caract[3])+"/"+str(holding_time)
                #s.sendall(adata)
                self.socket_tp.sendall(pickle.dumps([str(new_vm_ip),new_vm_caract[3],holding_time, 
                    str(ouside_host_ip)]))
                log.debug("Notifying Outside host to start sending traffic for new VM... DONE")
            except Exception, e:
                log.debug("Notifying Outside host to start sending traffic for new VM... FAIL")
                #TODO: Later put this in a stack and as soon as connected, ask to send traffic
                self.connectToTopologyGenerator()
        try :
            self.clientsocket.send(data)
            log.debug("Notifying VM Requester of new VM Allocation... DONE")
        except Exception, e:
            log.debug("Notifying VM Requester of new VM Allocation... FAIL")
            log.error("Trying to notify VM Requester of new VM allocation, but it's disconnected...")
        
    
    def connectToTopologyGenerator(self):
        try:
            self.socket_tp = socket(AF_UNIX, SOCK_STREAM)
            self.socket_tp.connect("/home/mininet/socket.tmp")
        except Exception, e:
            sleep(1)
            self.connectToTopologyGenerator()

    
    def connectToRequester(self):
        addr = (self.ip, self.port)
        serversocket = socket(AF_INET, SOCK_STREAM)
        serversocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        serversocket.bind(addr)
        serversocket.listen(1)
        
        while 1:
            log.info("Waiting for VM Requester connections...")
            self.clientsocket, self.clientaddr = serversocket.accept()
            self.listenToRequest(self.clientaddr, self.clientsocket)
        serversocket.close()    
    
    def listenToRequest(self, clientaddr, clientsocket):
            log.info("IP = %s, Port = %s - New VM Requester Connected ", clientaddr[0] ,clientaddr[1])
            
            while 1:
                try :
                    data = clientsocket.recv(2048)
                except Exception, e:
                    log.info("VM Requester Disconnected")
                    break
                try :
                    (cpu, ram, disk, network, request_type) = pickle.loads(data)
                    log.debug("CPU = %s, RAM = %s, Disk = %s, Network = %s, Request Type = %s - New VM Request received", cpu, ram, disk, network, request_type)
                except Exception, e:
                    log.warning("Corrupted Request Received")
                    print e
                    break
                try :
                    self.raiseEvent(VMRequest, time.time(), cpu, ram, disk, network, request_type)
                except Exception, e:
                    print e
                '''
                try :
                    #TODO: For now just so we know how to send back things               
                    msg = "You sent me: %s" % data
                    clientsocket.send(msg)
                except Exception, e:
                    pass
                '''
        
            clientsocket.close()

'''
Auxiliar Function
'''
def isIPandPort(ipaddress, port):
    '''
    Check if Ip address and port are in the correct form
    IPv4 Only (for now)
    '''
    if (not ercs_topology.is_number(port)) :
        log.debug("Bad Port Number")
        return False
    elif not ((int(port) > 1024) and (int(port) < 65536)):
        log.debug("Bad Port Number")
        return False
    else :
        for no in ipaddress.split(".",3) :
            if (not ercs_topology.is_number(no)) :
                log.debug("Bad IP Address")
                return False
            elif not ((int(no) >= 0) and (int(no) <= 255)):
                log.debug("Bad IP Address")
                return False
    return True   
    
def launch():
    VMReceiver()
    
