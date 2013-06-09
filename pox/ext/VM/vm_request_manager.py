from pox.lib.revent.revent import EventMixin, Event
from pox.core import core
from ext.Topology import ercs_topology
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
    Event with new virtual machine allocation request
    '''
    def __init__ (self, vm_id, time, cpu, ram, disk, network, request_type, timeout) :
        Event.__init__(self)
        self.vm_id = vm_id
        self.time = time
        self.cpu = cpu
        self.ram = ram
        self.disk = disk
        self.network = network
        self.request_type = request_type
        self.timeout = timeout

class InterVMComRequest (Event):
    """
    Event with the inter virtual machine communication request
    """
    def __init__(self, vm_list):
        Event.__init__(self)
        self.vm_list = vm_list

class VMReceiver (EventMixin, threading.Thread):
    '''
    Raises an event every time a new request arrives
    TODO: Change request receiver to receive requests from both vmrequester(request generator)
    and from the web platform
        -For testing purposes keep the port for vmrequester opened
            -OR modify the generator to adapt the Web platform behaviour (probably a smarter idea)
        -FOr the web platform, open a new port, a then to allow multiple requests at the same time,
        open a new port for each request. Summary: 1 port to negociate the next port for the request,
        and also to know which vm belongs to each port
            -Keep a track of request -> port relation
    '''
    _eventMixin_events = set([
                          VMRequest,
                          InterVMComRequest,
                          ])
    
    def __init__(self, inithandler=None):
        threading.Thread.__init__(self)
        self.request_history = {}
        self.ip = ""
        self.port = ""
        self.socket_tp = None
        self.vm_counter = 0
        self.vm_sockets = {}
        
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
        
    def notifyVMAllocation(self, vm_id, new_vm_caract, holding_time = None, new_vm_ip = None, core_candidate = None, 
            agg_candidate = None, edge_candidate = None, ouside_host_ip = None):

        # Notify's the state of the allocation
        # -FALSE if the allocation failed
        # -IP Address of Host if allocation sucessfull
        # 
        # When fully integrated with xen, the ip address of virtualmachine should be returned, and not
        # the ip address of the host.

        log.debug("Notifying VM Requester of new VM Allocation...")
        if new_vm_ip == None or core_candidate == None or agg_candidate == None or edge_candidate == None:
            # data = "VM Allocation FAIL - Request Type = %s, CPU = %s, RAM = %s, DISK = %s \n" %  (new_vm_caract[len(new_vm_caract)-1], 
            #         new_vm_caract[0], new_vm_caract[1], new_vm_caract[2])
            data = "FALSE"
        else:
            # data = "VM Allocation SUCESS - Request Type = %s, CPU = %s, RAM = %s, DISK = %s \n CoreS = %s, AggS = %s, EdgeS = %s, HostIP = %s\n" % (new_vm_caract[4], new_vm_caract[0], new_vm_caract[1], 
            #     new_vm_caract[2], core_candidate, agg_candidate, edge_candidate, new_vm_ip)
            data = str(new_vm_ip)

        try :
            self.vm_sockets[vm_id].send(data)
            log.debug("Notifying VM Requester of new VM Allocation... DONE")
        except Exception, e:
            log.debug("Notifying VM Requester of new VM Allocation... FAIL")
            log.error("Trying to notify VM Requester of new VM allocation, but it's disconnected...")

        self.notifyTrafficGenerator(new_vm_ip,new_vm_caract[3],holding_time, 
            ouside_host_ip)
        
    def notifyTrafficGenerator(self, new_vm_ip, bw, holding_time, outside_host_ip):
        '''
        Connects with ERCSMNGenerator to start generating traffic from hosts
        '''
        try:
            #NOtify host to start sending traffic to this new ip
            log.debug("Notifying Outside host to start sending traffic for new VM...")    
            #s.sendall(str(new_vm_ip)+"/"+str(new_vm_caract[3])+"/"+str(holding_time)+"/"+str(core_candidate))
            #adata = str(new_vm_ip)+"/"+str(new_vm_caract[3])+"/"+str(holding_time)
            #s.sendall(adata)
            self.socket_tp.sendall(pickle.dumps([str(new_vm_ip),bw,holding_time, 
                str(outside_host_ip)]))
            log.debug("Notifying Outside host to start sending traffic for new VM... DONE")
        except Exception, e:
            print e
            log.debug("Notifying Outside host to start sending traffic for new VM... FAIL")
            #TODO: Later put this in a stack and as soon as connected, ask to send traffic
            self.connectToTopologyGenerator()

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
            thread.start_new_thread(self.listenToRequest, (self.clientaddr, self.clientsocket))
            # self.listenToRequest(self.clientaddr, self.clientsocket)
        serversocket.close()    
    
    def listenToRequest(self, clientaddr, clientsocket):
            log.info("IP = %s, Port = %s - New VM Requester Connected ", clientaddr[0] ,clientaddr[1])
            
            while 1:
                try :
                    data = clientsocket.recv(2048)
                except Exception, e:
                    log.info("IP = %s, Port = %s - VM Requester Disconnected ", clientaddr[0] ,clientaddr[1])
                    break
                log.info(data)
                [request_type, subdata] = data.split("/",1)
                log.info(request_type)
                log.info(subdata)
                try :
                    #two types of requests (new vm request / interconnect vms)
                    #later should probably use some xml protocol or something
                    
                    
                    
                    
                    #new vm request arrived
                    if int(request_type) == 1:
                        [cpu, ram, disk, network, request_type, timeout] = subdata.split("/",5)
                        [cpu, ram, disk, network, request_type, timeout] = [int(cpu), int(ram), int(disk), int(network), int(request_type), int(timeout)]

                        #Should use some locking mechanism, to prevent different threads from incrementing at the same time
                        self.vm_counter +=1
                        vm_id = self.vm_counter
                        log.debug("ID = %s, CPU = %s, RAM = %s, Disk = %s, Network = %s, Request Type = %s, Timeout = %s - New VM Request received", vm_id, cpu, ram, disk, network, request_type, timeout)
                        log.info("New Virtual Machine Request Received")
                        self.vm_sockets[vm_id] = clientsocket
                        self.raiseEvent(VMRequest, vm_id, time.time(), cpu, ram, disk, network, request_type, timeout)
                    #new intervm connection request arrived
                    else:
                        vm_list = subdata.split("/", int(request_type)-1)
                        log.debug("#VMs = %s - New Inter VM Communication Request Received", request_type)
                        log.info("New Inter VM Communication Request Received")
                        self.raiseEvent(InterVMComRequest, vm_list)

                except Exception, e:
                    log.warning("Corrupted Request Received")
                    print e
                    break
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
    
