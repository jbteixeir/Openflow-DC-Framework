from __future__ import division
from pox.core import core
from ext.VM.vm_request_manager import VMReceiver
from ext.Structures.ercs_switch import Switch
from pox.lib.recoco.recoco import Timer

import os
import threading
import math
import random

log = core.getLogger()

def nextTime(rateParameter):
    return -math.log(1.0 - random.random()) / rateParameter

class VMManager(object):
    '''
    Class that manages the VM allocation.
    
    topology - same as ERCS_Topology (so information about topology is accessible)
    
    vms_requests - list of vm requests
    vms_allocated - dict of (list of allocated vm's) indexed by host_id
                    the list is composed by elements like (cpu, ram, disk)
    
    non_suitable_switches - list of non suitable switches
    
    non_suitable_hosts - list of non suitable hosts
    
    non_suitable_ports - dictionary with a list of non suitable ports, indexed by dpid
    Use the function isNonSuitablePort to verify if Port is non suitable
    (because a link has to ports)
    
    edge_candidate - Edge Switch Candidate Dpid
    edge_port_candidate - Port in each the edge switch connects to the host
    agg_candidate - Aggregation Switch Candidate Dpid
    agg_port_candidate - Port in each the agg switch connects to the edge switch
    core_candidate - Core Switch Candidate Dpid
    core_port_candidate - Port in each the core switch connects to the agg switch
    
    host_candidate - Host Candidate host_id
    
    max_bw_ratio - Maximum Bandwidth ratio for allowing a new vm allocation
    
    last_stats_request_time
    ASK:Policy FF,BF,WF - should i implement a different type of policy according to core/agg/edge switches and hosts?
        Or the same policy to all (once chosen)
    ANSWER: Allow all possible combinations
        
    Algorithm types:
    ND - Network driven algorithm
    SD - Server driven algorithm
    Default algorithm
    DEFAULTALG = ND
    
    Types of policies
    FF = 0
    BF = 1
    WF = 2
    Default policy (for everything, switches and hosts)
    DEFAULTPOL = BF
    
    NOTE: Information related to rules is stored in ercs_rules
    
    TODO: Later on the algorithms, instead of simply returning false in case of failure
        return also the reason for this failure

    TODO: Change to instead of having methods to install rules, simply raise an event of vm allocated
    and also vm removed
    '''
    
    #Types of policies
    FF = 0
    BF = 1
    WF = 2
    #default policy (for everything, switches and hosts)
    DEFAULTPOL = BF
    
    #Best fit ponderation
    BF_CPU = 1
    BF_RAM = 0
    BF_DISK = 0
    
    #Types of algorithm
    ND = 0
    SD = 1
    #default algorithm
    DEFAULTALG = ND
    
    def __init__(self, topology, stats, rules, vmreceiver, inithandler = None, xencommunicator = None):
        #get other classes for information retrieval
        self.topology = topology
        self.stats = stats
        self.rules = rules
        self.vmreceiver = vmreceiver
        
        #Initialize the variables
        #self.vms_requests = list()
        self.vms_allocated = {}
        self.non_suitable_switches = list()
        self.non_suitable_hosts = list()
        self.non_suitable_ports = {}
        
        #initialize non_suitable_ports
        for switch in self.topology.switches :
            self.non_suitable_ports[switch.dpid] = list()
        
        self.edge_candidate = -1
        self.edge_port_candidate = -1
        self.agg_candidate = -1
        self.agg_port_candidate = -1
        self.core_candidate = -1
        self.core_port_candidate = -1
        
        self.host_candidate = -1 
        self.last_stats_request_time = -1
        
        self.host_holding_time = -1

        self.request_type = -1
        
        if inithandler == None :
            #ask for policies, algorithm and ratios
            self.askVMManagerPolAlgRat()
        else :
            self.getArgsFromIni(inithandler)
        
        log.debug("Algorithm = %s, core_policy = %s, agg_policy = %s , edge_policy = %s, host_policy = %s",
            self.current_alg, self.core_policy, self.agg_policy, self.edge_policy, self.host_policy)
        
        #listen to vm request events
        self.vmreceiver.addListeners(self)
    
    def getArgsFromIni(self, inithandler):
        try :
            section = "vmallocation"
            key = "algorithm"
            current_alg = inithandler.read_ini_value(section, key)
            if current_alg == "ND" :
                self.current_alg = self.ND
            elif current_alg == "SD" :
                self.current_alg = self.SD
            else:
                self.current_alg = self.DEFAULTALG
                
            key = "core_policy"
            core_policy = inithandler.read_ini_value(section, key)
            if core_policy == "FF":
                self.core_policy = self.FF
            elif core_policy == "BF":
                self.core_policy = self.BF
            elif core_policy == "WF":
                self.core_policy = self.WF
            else :
                self.core_policy = self.DEFAULTPOL
            key = "agg_policy"
            agg_policy = inithandler.read_ini_value(section, key)
            if agg_policy == "FF":
                self.agg_policy = self.FF
            elif agg_policy == "BF":
                self.agg_policy = self.BF
            elif agg_policy == "WF":
                self.agg_policy = self.WF
            else :
                self.agg_policy = self.DEFAULTPOL
            key = "edge_policy"
            edge_policy = inithandler.read_ini_value(section, key)
            if edge_policy == "FF":
                self.edge_policy = self.FF
            elif edge_policy == "BF":
                self.edge_policy = self.BF
            elif edge_policy == "WF":
                self.edge_policy = self.WF
            else :
                self.edge_policy = self.DEFAULTPOL
            key = "host_policy"
            host_policy = inithandler.read_ini_value(section, key)
            if host_policy == "FF":
                self.host_policy = self.FF
            elif host_policy == "BF":
                self.host_policy = self.BF
            elif host_policy == "WF":
                self.host_policy = self.WF
            else :
                self.host_policy = self.DEFAULTPOL
            
            key = "switch_ratio"
            self.max_bw_switch_ratio = float(inithandler.read_ini_value(section, key))
            key = "link_ratio"
            self.max_bw_link_ratio = float(inithandler.read_ini_value(section, key))
            
            #TODO: Later check value, it cannot be zero
            key = "holding_time"
            self.host_holding_time = int(inithandler.read_ini_value(section, key))
            
            log.debug("Successfully got vm allocation values")
            
        except Exception, e :
            log.error("INI File doesn't contain expected values")
            print e
            os._exit(0)
    
    def askVMManagerPolAlgRat(self):
        '''
        ASk for the type of policy, the algorithm and the ratios
        '''
        #Ask for type of algorithm should be used
        self.current_alg = raw_input("Select the algorithm type for VM allocation (ND-Network Driven, SD - Server Driven, Default - ND):\n")
        while (self.current_alg != "ND" and self.current_alg != "SD" and self.current_alg != "") :
            self.current_alg = raw_input("Please insert a valid option: ")
        if self.current_alg == "ND" :
            self.current_alg = self.ND
        elif self.current_alg == "SD" :
            self.current_alg = self.SD
        else:
            self.current_alg = self.DEFAULTALG
        
        #Ask which policies should be used for each type o switch and for hosts
        #Edge
        self.edge_policy = raw_input("Insert the policy for the edge switch selection (FF-First Fit, BF-Best Fit, WF-WorstFit, Default - BF):\n")
        while (self.edge_policy != "FF" and self.edge_policy != "BF" and self.edge_policy != "WF" and self.edge_policy != "") :
            self.edge_policy = raw_input("Please insert a valid option: ")
        if self.edge_policy == "FF":
            self.edge_policy = self.FF
        elif self.edge_policy == "BF":
            self.edge_policy = self.BF
        elif self.edge_policy == "WF":
            self.edge_policy = self.WF
        else :
            self.edge_policy = self.DEFAULTPOL
        
        #Agg
        self.agg_policy = raw_input("Insert the policy for the aggregation switch selection (FF-First Fit, BF-Best Fit, WF-WorstFit, Default - BF):\n")
        while (self.agg_policy != "FF" and self.agg_policy != "BF" and self.agg_policy != "WF" and self.agg_policy != "") :
            self.agg_policy = raw_input("Please insert a valid option: ")
        if self.agg_policy == "FF":
            self.agg_policy = self.FF
        elif self.agg_policy == "BF":
            self.agg_policy = self.BF
        elif self.agg_policy == "WF":
            self.agg_policy = self.WF
        else :
            self.agg_policy = self.DEFAULTPOL

        #Core
        self.core_policy = raw_input("Insert the policy for the core switch selection (FF-First Fit, BF-Best Fit, WF-WorstFit, Default - BF):\n")
        while (self.core_policy != "FF" and self.core_policy != "BF" and self.core_policy != "WF" and self.core_policy != "") :
            self.core_policy = raw_input("Please insert a valid option: ")
        if self.core_policy == "FF":
            self.core_policy = self.FF
        elif self.core_policy == "BF":
            self.core_policy = self.BF
        elif self.core_policy == "WF":
            self.core_policy = self.WF
        else :
            self.core_policy = self.DEFAULTPOL
        
        #host
        self.host_policy = raw_input("Insert the policy for the host selection (FF-First Fit, BF-Best Fit, WF-WorstFit, Default - BF):\n")
        while (self.host_policy != "FF" and self.host_policy != "BF" and self.host_policy != "WF" and self.host_policy != "") :
            self.host_policy = raw_input("Please insert a valid option: ")
        if self.host_policy == "FF":
            self.host_policy = self.FF
        elif self.host_policy == "BF":
            self.host_policy = self.BF
        elif self.host_policy == "WF":
            self.host_policy = self.WF
        else :
            self.host_policy = self.DEFAULTPOL
        
        #Ask for the Bandwidth switch ratio
        self.max_bw_switch_ratio = raw_input("Insert the maximum switch bandwidth ratio for new VM allocation(between 0 and 1):\n")
        if self.max_bw_switch_ratio == "" :
            self.max_bw_switch_ratio = 0.99
        else :
            while (not self.topology.is_number(self.max_bw_switch_ratio)) : 
                if self.max_bw_switch_ratio < 0 or self.max_bw_switch_ratio > 1:
                    self.max_bw_switch_ratio = raw_input("This is not a valid number, please insert a valid value: ")
        
        
        #Ask for the Bandwidth link ratio
        self.max_bw_link_ratio = raw_input("Insert the maximum link bandwidth ratio for new VM allocation(between 0 and 1):\n")
        if self.max_bw_link_ratio == "" :
            self.max_bw_link_ratio = 0.99
        else :
            while (not self.topology.is_number(self.max_bw_link_ratio)) :
                if self.max_bw_link_ratio < 0 or self.max_bw_link_ratio < 1:
                    self.max_bw_link_ratio = raw_input("This is not a valid number, please insert a valid value: ")
                    
    def _handle_VMRequest(self, event):
        '''
        Method handling the requests
        '''
        log.info("Request ID = %s, Request Type = %s, CPU = %s, RAM = %s, DISK = %s, NETWORK = %s, TIMEOUT = %s - New VM Request Arrived", event.vm_id, event.request_type, event.cpu, event.ram, event.disk, event.network, event.timeout)
        
        self.request_type = event.request_type
        if self.current_alg == self.ND :
            log.debug("Trying to allocate VM through Network-Driven Algorithm")
            vm_allocation_result = self.networkDrivenAlgorithm(event.vm_id, (event.cpu, event.ram, event.disk, event.network, event.request_type, event.timeout))
        elif self.current_alg == self.SD :
            log.debug("Trying to allocate VM through Server-Driven Algorithm")
            vm_allocation_result = self.serverDrivenAlgorithm(event.vm_id, (event.cpu, event.ram, event.disk, event.network, event.request_type, event.timeout))
        
        '''    
        if vm_allocation_result == False :
            log.info("VM Allocation Failed")
            self.vmreceiver.notifyVMAllocation(None, None)
        else :
            log.info("CPU = %s, RAM = %s, DISK = %s, Host IP = %s - VM Successfully allocated", event.cpu, event.ram, event.disk, vm_allocation_result)
            self.vmreceiver.notifyVMAllocation(vm_allocation_result, (event.cpu, event.ram, event.disk))
        '''

    '''
    Algorithms
    '''
    def networkDrivenAlgorithm(self, vm_id ,requirements):
        '''
        Runs the Network Driven Algorithm for VirtualMachine Placement
        Objective:
            - Find the proper path according to the current policy
            - Find the proper Host to allocate the VM
            - Notify the VM Requester
            
        Returns:
            -host ip address in case of success
            -False - in case of failure 
        '''
        
        log.debug("Requirements = %s - Running ND Algorithm to allocate new VM...", requirements)
        host_allocated = False
        
        try:
            #Find a core switch
            self.core_candidate = self.getSwitch(Switch.CORE, self.core_policy, requirements[3])
            while self.core_candidate != None and host_allocated == False :
                log.debug("DPID = %s - A candidate core switch was found", self.core_candidate)
                #find a suitable core link
                
                self.core_port_candidate = self.getLink(self.core_policy, self.core_candidate, requirements[3])
                while self.core_port_candidate != None and host_allocated == False:
                    log.debug("DPID = %s, PORT = %s - A candidate core switch port was found", self.core_candidate, self.core_port_candidate)
                    #get the aggregation switch correspondent to this link
                    self.agg_candidate = self.topology.switch_links[self.core_candidate][self.core_port_candidate][0]
                    #check if the aggregation switch has a ratio <= max_ratio
                    if self.getSwitchRatioWithSafeMargin(self.agg_candidate, requirements[3]) <= self.max_bw_switch_ratio :
                        log.debug("DPID = %s - A candidate aggregation switch was found", self.agg_candidate)
                        #find a suitable aggregation link
                        self.agg_port_candidate = self.getLink(self.agg_policy, self.agg_candidate, requirements[3])
                        while self.agg_port_candidate != None and host_allocated == False:
                            log.debug("DPID = %s, PORT = %s - A candidate agg switch port was found", self.agg_candidate, self.agg_port_candidate)
                            #get the edge switch correspondent to this link
                            self.edge_candidate = self.topology.switch_links[self.agg_candidate][self.agg_port_candidate][0]
                            #check if the edge switch has a ratio <= max_ratio
                            if self.getSwitchRatioWithSafeMargin(self.edge_candidate, requirements[3]) <= self.max_bw_switch_ratio :
                                log.debug("DPID = %s - A candidate edge switch was found", self.edge_candidate)
                                #find a suitable host that is connected to this dpid
                                self.host_candidate = self.getHostConnectedToDPID(self.host_policy, requirements, self.edge_candidate)
                                if self.host_candidate == None :
                                    log.debug("EDGE_DPID = %s - No suitable host was found for this edge switch", self.edge_candidate)
                                    #add edge switch to the non suitable
                                    self.non_suitable_switches.append(self.edge_candidate)
                                    #add port to the non suitable ports
                                    if not self.non_suitable_ports.has_key(self.agg_candidate):
                                        self.non_suitable_ports[self.agg_candidate] = list()
                                    self.non_suitable_ports[self.agg_candidate].append(self.agg_port_candidate)
                                    
                                    #find a new agg_port_cadidate
                                    self.agg_port_candidate = self.getLink(self.agg_policy, self.agg_candidate, requirements[3])
                                else :
                                    self.edge_port_candidate = self.topology.host_links[self.host_candidate][1][1]
                                    host_allocated = True
                                
                            else :
                                log.debug("EDGE_DPID = %s - No suitable edge switch was found for this link", self.edge_candidate)
                                #add port to the non suitable ports
                                if not self.non_suitable_ports.has_key(self.agg_candidate):
                                        self.non_suitable_ports[self.agg_candidate] = list()
                                self.non_suitable_ports[self.agg_candidate].append(self.agg_port_candidate)
                                #find a new agg_port_cadidate
                                self.agg_port_candidate = self.getLink(self.agg_policy, self.agg_candidate, requirements[3])
                                
                        #if no suitable agg ports where found
                        if self.agg_port_candidate == None :
                            log.debug("AGG_DPID = %s - No suitable agg switch was found for this link", self.agg_candidate)
                            #add port to the non suitable ports
                            if not self.non_suitable_ports.has_key(self.core_candidate):
                                        self.non_suitable_ports[self.core_candidate] = list()
                            self.non_suitable_ports[self.core_candidate].append(self.core_port_candidate)
                            #find a new core_port_cadidate
                            self.core_port_candidate = self.getLink(self.core_policy, self.core_candidate, requirements[3])
                            
                    else :
                        log.debug("AGG_DPID = %s - No suitable agg switch was found for this link", self.agg_candidate)
                        #add port to the non suitable ports
                        if not self.non_suitable_ports.has_key(self.core_candidate):
                                        self.non_suitable_ports[self.core_candidate] = list()
                        self.non_suitable_ports[self.core_candidate].append(self.core_port_candidate)
                        #find a new core_port_cadidate
                        self.core_port_candidate = self.getLink(self.core_policy, self.core_candidate, requirements[3])
                        
                #if no suitable core ports where found
                if self.core_port_candidate == None :
                    log.debug("DPID = %s - No suitable core links were found for this switch", self.core_candidate)
                    self.non_suitable_switches.append(self.core_candidate)
                    #find a new core_switch
                    self.core_candidate = self.getSwitch(Switch.CORE, self.core_policy, requirements[3])
                    
            #If a core switch is not found
            if self.core_candidate == None :
                log.debug("No suitable core switch was found")
                self.vmreceiver.notifyVMAllocation(vm_id, requirements)
                #reinitialize all the variables
                self.cleanVariables()
                return False
        
        except Exception, e :
            print "Something went wrong"
            print e
            #reinitialize all the variables
            self.cleanVariables()
        
        log.debug("Requirements = %s, HostID = %s - Running ND Algorithm to allocate new VM... DONE", requirements, self.host_candidate)
        
        try :
            log.debug("CoreSwitch = %s->%s->%s, AggSwitch = %s->%s->%s, EdgeSwitch = %s->%s->%s, HostID = %s", 
                    self.topology.out_hosts[self.core_candidate].keys()[0], self.core_candidate, self.core_port_candidate, 
                    self.topology.switch_links[self.core_candidate][self.core_port_candidate][1], self.agg_candidate, 
                    self.agg_port_candidate, self.topology.switch_links[self.agg_candidate][self.agg_port_candidate][1], 
                    self.edge_candidate, self.edge_port_candidate, self.host_candidate)
        except Exception, e :
			print "Something went wrong after allocating VM"
			print e

        # add to the allocated list
        self.vms_allocated[self.host_candidate].append(requirements)
        # set holding time
        #TODO: Allow to update the holding_time
        holding_time = requirements[4]
        threading.Timer(holding_time, self.removeVMAllocation, [self.host_candidate, requirements]).start()

        #install the rules
        self.installVMRules()
        
        #notify the VM Requester
        host_ip = self.topology.hosts[self.host_candidate].ports[self.topology.hosts[self.host_candidate].ports.keys()[0]].ip_addresses[0]

        self.vmreceiver.notifyVMAllocation(vm_id, requirements, holding_time, host_ip, self.core_candidate, 
            self.agg_candidate, self.edge_candidate, self.topology.out_hosts[self.core_candidate][self.topology.out_hosts[self.core_candidate].keys()[0]][0][1])
        
        #reinitialize all the variables
        self.cleanVariables()
        
        #remove from the request list
        #del(self.vms_requests[0])
        
        return host_ip
     
    def serverDrivenAlgorithm(self, vm_id, requirements):
        '''
        Runs the Server Driven Algorithm for VirtualMachine Placement
        Objective:
            - Find the proper Host to allocate the VM
            - Find the proper path according to the current policy
            - Notify the VM Requester
            
        Returns:
            -host ip address in case of success
            -False - in case of failure 
        '''
        
        core_found = False
        
        log.debug("Requirements = %s - Running SD Algorithm to allocate new VM...", requirements)
        self.host_candidate = self.getHost(self.host_policy, requirements)
        try :
            while self.host_candidate != None and not core_found:
                #get the switch and switch port to which this host is connected
                (self.edge_candidate, self.edge_port_candidate) = self.topology.host_links[self.host_candidate][1]
                #check if the edge switch as an acceptable ratio
                if self.switchHasEnoughResources(self.edge_candidate, requirements[3]) :
                    log.debug("DPID = %s - A candidate edge switch was found", self.edge_candidate)
                    #check if the connection between this host and the edge switch as an acceptable ratio
                    if self.linkHasEnoughResources(self.edge_candidate, self.edge_port_candidate) :
                        log.debug("DPID = %s, PORT = %s - A candidate edge switch port was found", self.edge_candidate, self.edge_port_candidate)
                        #get the agg link (by the edge part)
                        agg_link_edge = self.getLink(self.agg_policy, self.edge_candidate, requirements[3])
                        while agg_link_edge != None and not core_found:
                            #get the switch and switch port to which the agg link by the edge part was chosen
                            (self.agg_candidate, self.agg_port_candidate) = self.topology.switch_links[self.edge_candidate][agg_link_edge]
                            #check if the agg switch as an acceptable ratio
                            if self.switchHasEnoughResources(self.agg_candidate, requirements[3]):
                                log.debug("DPID = %s - A candidate agg switch was found", self.agg_candidate)
                                #check if the connection between the edge and agg switch as an acceptable ratio
                                if self.linkHasEnoughResources(self.agg_candidate, self.agg_port_candidate) :
                                    log.debug("DPID = %s, PORT = %s - A candidate agg switch port was found", self.agg_candidate, self.agg_port_candidate)
                                    #get the core link (by the agg part)
                                    core_link_agg = self.getLink(self.core_policy, self.agg_candidate, requirements[3])
                                    while core_link_agg != None and not core_found:
                                        #get the switch and switch port to which the core link by the agg part was chosen
                                        (self.core_candidate, self.core_port_candidate) = self.topology.switch_links[self.agg_candidate][core_link_agg]
                                        #check if the agg switch as an acceptable ratio
                                        if self.switchHasEnoughResources(self.core_candidate, requirements[3]) :
                                            log.debug("DPID = %s - A candidate core switch was found", self.core_candidate)
                                            #check if the connection between the agg and core switch doesn't have an acceptable ratio
                                            if not self.linkHasEnoughResources(self.core_candidate,self.core_port_candidate) :
                                                log.debug("DPID = %s, PORT = %s - Core Link doesn't have enough resources", self.core_candidate, self.core_port_candidate)
                                                #add the port to the non suitable ports
                                                self.non_suitable_ports[self.core_candidate].append(self.core_port_candidate)
                                                #get a new core link (by the agg part)
                                                core_link_agg = self.getLink(self.core_policy, self.agg_candidate, requirements[3])
                                            else :
                                                log.debug("DPID = %s, PORT = %s - A candidate core switch port was found", self.core_candidate, self.core_port_candidate)
                                                core_found = True
                                        else:
                                            log.debug("DPID = %s - Core Switch doesn't have enough resources", self.core_candidate)
                                            #add the core switch to the non suitable switches
                                            self.non_suitable_switches.append(self.core_candidate)
                                            #get a new core link (by the agg part)
                                            core_link_agg = self.getLink(self.core_policy, self.agg_candidate, requirements[3])
    
                                    if core_link_agg == None :                                    
                                        log.debug("No suitable core link was found")
                                        #add the port to the non suitable ports
                                        self.non_suitable_ports[self.agg_candidate].append(core_link_agg)
                                        #add the edge switch to the non suitable switches
                                        self.non_suitable_switches.append(self.edge_candidate)
                                        #get a new agg link
                                        agg_link_edge = self.getLink(self.agg_policy, self.edge_candidate, requirements[3])
                                else :
                                    log.debug("DPID = %s, Port = %s - Aggregation Link doesn't have enough resources", self.agg_candidate, self.agg_port_candidate)
                                    #add the port to the non suitable ports
                                    self.non_suitable_ports[self.agg_candidate].append(self.agg_port_candidate)
                                    #get a new agg link
                                    agg_link_edge = self.getLink(self.agg_policy, self.edge_candidate, requirements[3])
                            else :
                                log.debug("DPID = %s - Aggregation Switch doesn't have enough resources", self.agg_candidate)
                                #add the aggregation switch to the non suitable switches
                                self.non_suitable_switches.append(self.agg_candidate)
                                #add the edge port to the non suitable ports
                                self.non_suitable_ports[self.edge_candidate].append(agg_link_edge)
                                #get a new agg link
                                agg_link_edge = self.getLink(self.agg_policy, self.edge_candidate, requirements[3])
                        if agg_link_edge == None :
                            log.debug("No suitable aggregation link was found")
                            #add the port to the non suitable ports
                            self.non_suitable_ports[self.edge_candidate].append(agg_link_edge)
                            #add the edge switch to the non suitable switches
                            self.non_suitable_switches.append(self.edge_candidate)
                            #add the host to the non suitable hosts
                            self.non_suitable_hosts.append(self.host_candidate)
                            #get a new host_candidate
                            self.host_candidate = self.getHost(self.host_policy, requirements)
                    
                    else :
                        log.debug("DPID = %s, Port = %s - Edge Link doesn't have enough resources", self.edge_candidate, self.edge_port_candidate)
                        #add the port to the non suitable ports
                        self.non_suitable_ports[self.edge_candidate].append(self.edge_port_candidate)
                        #add the host to the non suitable hosts
                        self.non_suitable_hosts.append(self.host_candidate)
                        #get a new host_candidate
                        self.host_candidate = self.getHost(self.host_policy, requirements)
                else :
                    log.debug("DPID = %s - Edge Switch doesn't have enough resources", self.edge_candidate)
                    #add the edge switch to the non suitable switches
                    self.non_suitable_switches.append(self.edge_candidate)
                    #add the host to the non suitable hosts
                    self.non_suitable_hosts.append(self.host_candidate)
                    #get a new host_candidate
                    self.host_candidate = self.getHost(self.host_policy, requirements)
                    
            if self.host_candidate == None :
                log.debug("No suitable host was found")
                log.debug("Requirements = %s - Running SD Algorithm to allocate new VM... FAIL", requirements)
                self.vmreceiver.notifyVMAllocation(vm_id, requirements)
                return False
            
        except Exception, e :
                print "Something went wrong"
                print e
    
        log.debug("Requirements = %s, HostID = %s - Running SD Algorithm to allocate new VM... DONE", requirements, self.host_candidate)
        
        log.debug("CoreSwitch = %s->%s->%s, AggSwitch = %s->%s->%s, EdgeSwitch = %s->%s->%s, HostID = %s", 
                  self.topology.out_hosts[self.core_candidate].keys()[0], self.core_candidate, self.core_port_candidate, 
                  self.topology.switch_links[self.core_candidate][self.core_port_candidate][1], self.agg_candidate, 
                        self.agg_port_candidate, self.topology.switch_links[self.agg_candidate][self.agg_port_candidate][1], 
                        self.edge_candidate, self.edge_port_candidate, self.host_candidate)
        
        # add to the allocated list
        self.vms_allocated[self.host_candidate].append(requirements)
        # set holding time
        #TODO: Allow to update the holding_time
        holding_time = nextTime(1/self.host_holding_time)
        threading.Timer(holding_time, self.removeVMAllocation, [self.host_candidate, requirements]).start()
        
        #install the rules
        self.installVMRules()
        
        #notify the VM Requester
        host_ip = self.topology.hosts[self.host_candidate].ports[self.topology.hosts[self.host_candidate].ports.keys()[0]].ip_addresses[0]
        self.vmreceiver.notifyVMAllocation(vm_id, requirements, holding_time, host_ip, self.core_candidate, 
            self.agg_candidate, self.edge_candidate, self.topology.out_hosts[self.core_candidate][self.topology.out_hosts[self.core_candidate].keys()[0]][0][1])
        
        #reinitialize all the variables
        self.cleanVariables()
        
        #remove from the request list
        #del(self.vms_requests[0])
        
        return host_ip

    def installVMRules(self):
        '''
        Install the Rules for the new allocated VM
        '''
        
        log.debug("Installing new VM Rules...")
        
        host_ip = self.topology.hosts[self.host_candidate].ports[self.topology.hosts[self.host_candidate].ports.keys()[0]].ip_addresses[0]
        
        
        if self.topology.out_hosts.has_key(self.core_candidate):
            if len(self.topology.out_hosts[self.core_candidate].keys()) !=0:
                core_port_out = self.topology.out_hosts[self.core_candidate].keys()[0]
            else:
                log.error("Dpid = %s - Could not find out port for core", self.core_candidate)
        else:
            log.error("Dpid = %s - Could not find out port for core", self.core_candidate)
            
        #get the output agg port
        agg_port_out = self.topology.switch_links[self.core_candidate][self.core_port_candidate][1]
        #get the output agg port
        edge_port_out = self.topology.switch_links[self.agg_candidate][self.agg_port_candidate][1]
        
        #install the rules for the newly allocated host
        self.rules.installHostRules(self.host_candidate, host_ip, self.core_candidate, self.core_port_candidate, core_port_out, self.agg_candidate, 
                         self.agg_port_candidate, agg_port_out, self.edge_candidate, self.edge_port_candidate, edge_port_out, self.request_type)
            
        log.debug("Installing nem VM Rules... DONE")

    def cleanVariables(self):
        '''
        clear all the temporary variables
        '''
        log.debug("Cleaning temporary variables...")
        self.core_candidate = -1
        self.core_port_candidate = -1
        self.agg_candidate = -1
        self.agg_port_candidate = -1
        self.edge_candidate = -1
        self.edge_port_candidate = -1
        self.host_candidate = -1
        self.non_suitable_switches = list()
        self.non_suitable_hosts = list()
        self.non_suitable_ports = {}
        log.debug("Cleaning temporary variables... DONE")
        
    '''
    Host Related Methods
    '''
    def getHost(self, policy_type, requirements):
        '''
        Get a host based on the policy_type and the requirements specified
        Return the host_id or None in case no suitable host was found
        
        Types of policy:
        FF, BF, WF
        
        Requirements:
        Object of the type VMRequest (event)
        '''
        #FirstFit
        if policy_type == self.FF :
            return self.firstFitHost(self.topology.hosts.keys(), (requirements[0],requirements[1],requirements[2]))
        #BestFit
        elif policy_type == self.BF :
            return self.bestFitHost(self.topology.hosts.keys(), (requirements[0],requirements[1],requirements[2]))
        #WorstFit
        elif policy_type == self.WF :
            return self.worstFitHost(self.topology.hosts.keys(), (requirements[0],requirements[1],requirements[2]))

    def getHostConnectedToDPID(self, policy_type, requirements, dpid):
        '''
        Get a host that is connected to this dpid based on the policy_type and the requirements specified
        Return the host_id or None in case no suitable host was found
        
        Types of policy:
        FF, BF, WF
        
        Requirements:
        Object of the type VMRequest (event)
        '''
        log.debug("DPID = %s, Policy = %s, Requirements = %s - Getting host based on policy...", dpid, policy_type, requirements)
        hosts_id = list()
        for host in self.topology.hosts.values() :
            for port in self.topology.host_links[host.id].keys() :
                if dpid == self.topology.host_links[host.id][port][0] :
                    hosts_id.append(host.id)
        
        #FirstFit
        if policy_type == self.FF :
            host_id = self.firstFitHost(hosts_id, (requirements[0],requirements[1],requirements[2]))
        #BestFit
        elif policy_type == self.BF :
            host_id = self.bestFitHost(hosts_id, (requirements[0],requirements[1],requirements[2]))
        #WorstFit
        elif policy_type == self.WF :
            host_id = self.worstFitHost(hosts_id, (requirements[0],requirements[1],requirements[2]))
        
        log.debug("DPID = %s, Policy = %s, Requirements = %s, HostID = %s - Getting host based on policy...", dpid, policy_type, requirements, host_id)
        return host_id
    
    def hostFreeResources (self, host_id):
        '''
        Check how much resources this host as left
        '''
        log.debug("HostID = %s - Checking host free resources...", host_id)
        #log.debug(self.vms_allocated)
        
        #check how many resources were allocated
        if self.vms_allocated.has_key(host_id) :
            allocated_cpu = sum([vms_allocated[0] for vms_allocated in self.vms_allocated[host_id]])
            allocated_ram = sum([vms_allocated[1] for vms_allocated in self.vms_allocated[host_id]])
            allocated_disk = sum([vms_allocated[2] for vms_allocated in self.vms_allocated[host_id]])
        else :
            #initialize allocated vm list for this host
            self.vms_allocated[host_id] = list()
            allocated_cpu = 0
            allocated_ram = 0
            allocated_disk = 0
            
        #check how many free resources this host has
        free_cpu = self.topology.hosts[host_id].hardware[0] - allocated_cpu
        free_ram = self.topology.hosts[host_id].hardware[1] - allocated_ram
        free_disk = self.topology.hosts[host_id].hardware[2] - allocated_disk
        
        log.debug("HostID = %s, FreeCPU = %s, FreeRam = %s, FreeDisk = %s - Checking host free resources... DONE", host_id, free_cpu, free_ram, free_disk)
        
        return (free_cpu, free_ram, free_disk)

    def hostHasEnoughResources(self, host_id, requirements):
        '''
        Check if a host has enough free resources to handle this requirements
        Return True in case it has, otherwise False
        Return -1 in case of unexpected error
        '''
        log.debug("HostID = %s - Checking if host has enough resources...", host_id)
        #check if host exists
        if not self.topology.hosts.has_key(host_id) :
            log.error("Host ID = %s - Checking if host has enough resources, but host doesn't exist")
            return -1
        #check if this host has resources allocated
        if self.vms_allocated.has_key(host_id) :
            (free_cpu, free_ram, free_disk) = self.hostFreeResources ( host_id)
            
            #check if the free resources are enough for the request
            if (free_cpu >= requirements[0]) and (free_ram >= requirements[1]) and (free_disk >= requirements[2]) :
                enough_Res = True
            else :
                enough_Res = False
        elif ((self.topology.hosts[host_id].hardware[0] >= requirements[0]) and 
              (self.topology.hosts[host_id].hardware[1] >= requirements[1]) and
              (self.topology.hosts[host_id].hardware[2] >= requirements[2])) :
            
            self.vms_allocated[host_id] = list()
            enough_Res = True
        else :
            enough_Res = False
        
        log.debug("HostID = %s - EnoughRes = %s - Checking if host has enough resources... DONE", host_id, enough_Res)
        
        return enough_Res

    '''
    Host Policies
    '''
    def firstFitHost(self, hosts_id ,requirements):
        '''
        Find the first host who fulfills the VM requirements
        Return the host_id in case one is found, else returns None
        '''
        log.debug("Requirements = %s - Getting FirstFit Host...", requirements)
        
        first_host_id = None
        
        for host_id in hosts_id:
            #if host is suitable (used by the algorithm
            if host_id not in self.non_suitable_hosts :
                if self.hostHasEnoughResources(host_id, requirements) :
                    log.debug("Requirements = %s HostID = %s - Getting FirstFit Host... DONE", requirements, host_id)
                    first_host_id = host_id
        
        if first_host_id == None:
            log.debug("Requirements = %s HostID = %s - Getting FirstFit Host... FAIL", requirements, first_host_id)
        else:
            log.debug("Requirements = %s HostID = %s - Getting FirstFit Host... DONE", requirements, first_host_id)
            
        return first_host_id
    
    def bestFitHost(self, hosts_id, requirements):
        '''
        Find the host that best fits these requirements
        Return the host_id in case one is found, else returns None
        '''
        log.debug("Requirements = %s - Getting BestFit Host...", requirements)
        best_host_id = None
        #less ratio is better fit
        best_host_ratio = None
        
        #go through all hosts
        for host_id in hosts_id:
            #if host is suitable (used by the algorithm
            if host_id not in self.non_suitable_hosts :
                #retrieve how many free resources it has
                (free_cpu, free_ram, free_disk) = self.hostFreeResources ( host_id)
                #check if they are enough to fulfill the requirements
                if (free_cpu >= requirements[0]) and (free_ram >= requirements[1]) and (free_disk >= requirements[2]) :
                    #check if it is a best fit than the previouslly best (case exists
                    if best_host_id == None :
                        best_host_id = host_id
                        best_host_ratio = free_cpu*self.BF_CPU + free_ram*self.BF_RAM + free_disk*self.BF_DISK
                    else :
                        #calculate the cadidate ratio
                        candidate_ratio = free_cpu*self.BF_CPU + free_ram*self.BF_RAM + free_disk*self.BF_DISK
                        if best_host_ratio >= candidate_ratio :
                            #New best fit founded
                            best_host_id = host_id
                            best_host_ratio = candidate_ratio
        
        if best_host_id == None:
            log.debug("Requirements = %s, HostID = %s - Getting BestFit Host... FAIL", requirements, best_host_id)
        else:
            log.debug("Requirements = %s, HostID = %s - Getting BestFit Host... DONE", requirements, best_host_id)
            
        return best_host_id
        
    def worstFitHost(self, hosts_id, requirements):
        '''
        Find the host that worstly fits these requirements
        Return the host_id in case one is found, else returns None
        
        The fact that all hosts are checked, is on purpose.
            Why do you do it then?
            Because Hosts might have different characteristics
        
        '''
        log.debug("Requirements = %s - Getting WorstFit Host... ", requirements)
        worst_host_id = None
        #higher ratio is worst fit
        worst_host_ratio = None
        
        #go through all hosts
        for host_id in hosts_id:
            #if host is suitable (used by the algorithm
            if host_id not in self.non_suitable_hosts :
                #retrieve how many free resources it has
                (free_cpu, free_ram, free_disk) = self.hostFreeResources ( host_id)
                #check if they are enough to fulfill the requirements
                if (free_cpu >= requirements[0]) and (free_ram >= requirements[1]) and (free_disk >= requirements[2]) :
                    #check if it is a best fit than the previouslly best (case exists
                    if worst_host_id == None :
                        worst_host_id = host_id
                        worst_host_ratio = free_cpu*self.BF_CPU + free_ram*self.BF_RAM + free_disk*self.BF_DISK
                    else :
                        #calculate the cadidate ratio
                        candidate_ratio = free_cpu*self.BF_CPU + free_ram*self.BF_RAM + free_disk*self.BF_DISK
                        if worst_host_ratio < candidate_ratio :
                            #New worst fit founded
                            worst_host_id = host_id
                            worst_host_ratio = candidate_ratio
        
        if worst_host_id == None:
            log.debug("Requirements = %s, HostID = %s - Getting WorstFit Host... FAIL", requirements, worst_host_id)
        else:
            log.debug("Requirements = %s, HostID = %s - Getting WorstFit Host... DONE", requirements, worst_host_id)
            
        return worst_host_id
    
    def removeVMAllocation(self, host_id, requirements):
        '''
        Function to remove the VMAllocation, because holdingtime expired
        '''
        log.debug("HostId = %s - Removing VM allocation...", host_id)
        if self.vms_allocated.has_key(host_id):
            for index in range(len(self.vms_allocated[host_id])):
                if self.vms_allocated[host_id][index] == requirements:
                    del self.vms_allocated[host_id][index]
                    log.debug("HostId = %s - Removing VM allocation... DONE", host_id)
                    return
            log.debug("HostId = %s - Removing VM allocation...(VM not find in host) FAIL") 
        else:
            log.debug("HostId = %s - Removing VM allocation...(but host doesn't have any VM's allocated) FAIL")
    
    '''
    Switch Related Methods
    '''
    def getSwitch(self, switch_type, policy_type, network_margin):
        '''
        Gets a switch based on the policy_type specified
        Return the dpid of the switch or None case no suitable switch was found
        
        Types of policy:
        FF, BF, WF
        '''
        log.debug("SwitchType = %s, PolicyType = %s - Trying to get switch... ", switch_type, policy_type)
        #FirstFit
        if policy_type == self.FF :
            dpid = self.firstFitSwitch(switch_type, network_margin)
            if dpid == None :
                log.debug("SwitchType = %s, PolicyType = %s, DPID = %s - Trying to get switch... FAIL", switch_type, policy_type, dpid)
            else:
                log.debug("SwitchType = %s, PolicyType = %s, DPID = %s - Trying to get switch... DONE", switch_type, policy_type, dpid)
            return dpid
        #BestFit
        elif policy_type == self.BF :
            dpid = self.bestFitSwitch(switch_type, network_margin)
            if dpid == None :
                log.debug("SwitchType = %s, PolicyType = %s, DPID = %s - Trying to get switch... FAIL", switch_type, policy_type, dpid)
            else:
                log.debug("SwitchType = %s, PolicyType = %s, DPID = %s - Trying to get switch... DONE", switch_type, policy_type, dpid)
            return dpid
        #WorstFit
        elif policy_type == self.WF :
            dpid = self.worstFitSwitch(switch_type, network_margin)
            if dpid == None :
                log.debug("SwitchType = %s, PolicyType = %s, DPID = %s - Trying to get switch... FAIL", switch_type, policy_type, dpid)
            else:
                log.debug("SwitchType = %s, PolicyType = %s, DPID = %s - Trying to get switch... DONE", switch_type, policy_type, dpid)
            return dpid
        else :
            log.debug("PolicyType = %s - Unexpected policy entered", policy_type)

    def firstFitSwitch(self, switch_type, network_margin):
        '''
        Find the switch that first fits taking into account the type of algorithm
        Also takes into consideration the non_suitable_switches
        Return the dpid and port in case one is found, else returns None EX:(return (dpid) || None)
        '''
        
        log.debug("SwitchType = %s - Finding FirstFit Switch... ", switch_type)
        #get the dict of switches which match this swith_type
        switches = self.topology.getSwitchesByType(switch_type)
        
        if len(switches) == 0:
            log.debug("SwitchType = %s - No switches of this type were found", switch_type)
        else :
            log.debug("sSwitchType = %s - %s switches of this type were found", switch_type, len(switches))
        
        switch_ratio = -1
        
        #for each switch of the type requested
        for switch in switches.values() :
            
            #check if switch is not in the non suitable switches
            if (switch.dpid not in self.non_suitable_switches) :
                #calculate the switch ratio
                #TODO: Change to switch ratio with margin
                #switch_ratio = self.getSwitchRatioWithSafeMargin(switch.dpid, network_margin)
                switch_ratio = self.getSwitchRatio(switch.dpid)
                
            if (switch_ratio <= self.max_bw_switch_ratio) and switch_ratio != -1 :
                log.debug("SwitchType = %s, DPID = %s - Finding BestFit Switch... DONE", switch_type, switch.dpid)
                return switch.dpid
        
        #If no suitable switch of this type was found
        log.debug("SwitchType = %s - Finding BestFit Switch... FAIL", switch_type)
        return None
    
    def bestFitSwitch(self, switch_type, network_margin):
        '''
        Find the switch that best fits
        Return the dpid and port in case one is found, else returns None
        '''
        log.debug("SwitchType = %s - Finding BestFit Switch... ", switch_type)
        
        #get the dict of switches which match this swith_type
        switches = self.topology.getSwitchesByType(switch_type)
        
        if len(switches) == 0:
            log.debug("SwitchType = %s - No switches of this type were found", switch_type)
        else :
            log.debug("SwitchType = %s - # %s switches of this type were found", switch_type, len(switches))
        
        #dictionary of switch ratio's indexed by dpid
        switch_ratio = {}
        #for each switch of the type requested
        for switch in switches.values() :

            #check if switch is not in the non suitable switches
            if (switch.dpid not in self.non_suitable_switches) :
                
                #get the switch ratio
                #TODO: Change to switch ratio with margin
                #temp_switch_ratio = self.getSwitchRatioWithSafeMargin(switch.dpid, network_margin)
                temp_switch_ratio = self.getSwitchRatio(switch.dpid)

                if (temp_switch_ratio <= self.max_bw_switch_ratio) and temp_switch_ratio != -1 :
                    switch_ratio[switch.dpid] = temp_switch_ratio

        #If suitable switch of this type was found
        if len(switch_ratio) != 0 :
            bf = max(switch_ratio.values())
            for dpid in switch_ratio.keys() :
                if switch_ratio[dpid] == bf :
                    log.debug("SwitchType = %s, DPID = %s - Finding BestFit Switch... DONE", switch_type, dpid)
                    return dpid
                
        else :
            log.debug("SwitchType = %s - Finding BestFit Switch... FAIL", switch_type)
            return None
    
    def worstFitSwitch(self, switch_type, network_margin):
        '''
        Find the witch that worst fits
        Return the dpid and port in case one is found, else returns None
        '''
        
        log.debug("SwitchType = %s - Finding WorstFit Switch... ", switch_type)
        #get the dict of switches which match this swith_type
        switches = self.topology.getSwitchesByType(switch_type)
        
        if len(switches) == 0:
            log.debug("SwitchType = %s - No switches of this type were found", switch_type)
        else :
            log.debug("sSwitchType = %s - %s switches of this type were found", switch_type, len(switches))
        
        #dictionary of switch ratio's indexed by dpid
        switch_ratio = {}
        #for each switch of the type requested
        for switch in switches.values() :
            
            #check if switch is not in the non suitable switches
            if (switch.dpid not in self.non_suitable_switches) :
                #get the switch ratio
                #TODO: Change to switch ratio with margin
                #temp_switch_ratio = self.getSwitchRatioWithSafeMargin(switch.dpid, network_margin)
                temp_switch_ratio = self.getSwitchRatio(switch.dpid)
                    
                if (temp_switch_ratio <= self.max_bw_switch_ratio) and temp_switch_ratio != -1 :
                    switch_ratio[switch.dpid] = temp_switch_ratio
                else:
                    log.debug("DPID = %s, ratio = %s, max = %s - Switch ratio < then max bw ratio for new allocation", switch.dpid,
                        temp_switch_ratio, self.max_bw_switch_ratio)
            else :
                log.debug("DPID = %s - Switch belongs to nonsuitableswitch list", switch.dpid)
        
        #If no suitable switch of this type was found
        if len(switch_ratio) != 0 :
            wf = min(switch_ratio.values())
            for dpid in switch_ratio :
                if switch_ratio[dpid] == wf :
                    log.debug("SwitchType = %s, DPID = %s - Finding WorstFit Switch... DONE", switch_type, dpid)
                    return dpid
        else :
            log.debug("SwitchType = %s - Finding WorstFit Switch... FAIL", switch_type)
            return None
    
    def switchHasEnoughResources(self, dpid, network_margin):
        '''
        Check if switch has enough resources to allocate another VM
        Return True in case it has, otherwise False
        '''
        if self.getSwitchRatioWithSafeMargin(dpid, network_margin) <= self.max_bw_switch_ratio :
            return True
        else :
            return False
        pass

    def getSwitchRatio(self, dpid):
        '''
        Return the Ratio of the switch with this dpid
        '''
        try :
            #initialize variables
            switch_in_bw_ratio = 0
            switch_in_port_count = 0
            switch_out_bw_ratio = 0
            switch_out_port_count = 0
            
            #get the switch belonging to this dpid
            switch = self.topology.switches[dpid]
            
            log.debug("DPID = %s, #PORTS = %s ", dpid, len(switch.ports.values()))
        
            
            #check if it has a port that has enough resources
            for port in switch.ports.values() :
                #if this is an edge or core switch
                if switch.type == Switch.EDGE or switch.type == Switch.CORE:
                    if self.topology.switch_links.has_key(switch.dpid):
                        #check the ports connected to hosts (or to non openflow switches)
                        if not self.topology.switch_links[switch.dpid].has_key(port.id) :
                            log.debug("Adding in port ratio")
                            #increment the counter
                            switch_in_port_count += 1
                            #add the ratio of this port
                            switch_in_bw_ratio += self.getLinkRatio(switch.dpid, port.id)
                        else :
                            log.debug("Adding out port ratio")
                            #increment the counter
                            switch_out_port_count += 1
                            #add the ratio of this port
                            switch_out_bw_ratio += self.getLinkRatio(switch.dpid, port.id)
                else :
                    if self.topology.switch_links.has_key(switch.dpid):
                        #get the switch dpid to which this port connects
                        dst_dpid = self.topology.switch_links[switch.dpid][port.id][0]
                        #check if this link has interest to the algorithm
                        if self.topology.switches[dst_dpid].type == Switch.CORE :
                            log.debug("Adding in port ratio")
                            #increment the counter
                            switch_in_port_count += 1
                            #add the ratio of this port
                            switch_in_bw_ratio += self.getLinkRatio(switch.dpid, port.id)
                        else :
                            log.debug("Adding out port ratio")
                            #increment the counter
                            switch_out_port_count += 1
                            #add the ratio of this port
                            switch_out_bw_ratio += self.getLinkRatio(switch.dpid, port.id)
                        
            #TODO: TEMPORARY! Just until we found a way of discovering a core switch even if it has a "host" connected
            #ATENTION: NOT ACCURATE RESULT IN CASE OF CORE SWITCH
            if switch.type == Switch.CORE :
                if switch_out_port_count != 0:
                    #calculate the switch ratio
                    switch_out_ratio = switch_out_bw_ratio / switch_out_port_count
                    #calculate the switch ratio
                    switch_ratio = switch_out_ratio
                    
                    log.debug("DPID = %s, Ratio = %s - Getting switch ratio... DONE", dpid, switch_ratio)
                    
                    return switch_ratio
                else :
                    log.error("DPID = %s, No outbound port for this switch was found", dpid)
                    log.error("DPID = %s - Getting switch ratio... FAIL(no valid ports found)", dpid)
                    return None
                
            if switch_in_port_count != 0 :
                if switch_out_port_count != 0:
                    #calculate the switch ratio
                    switch_in_ratio = switch_in_bw_ratio / switch_in_port_count
                    switch_out_ratio = switch_out_bw_ratio / switch_out_port_count
                    #calculate the switch ratio
                    switch_ratio = (switch_in_ratio + switch_out_ratio) / 2
                    
                    log.debug("DPID = %s, Ratio = %s - Getting switch ratio... DONE", dpid, switch_ratio)
                    
                    return switch_ratio
                else :
                    log.error("DPID = %s, No outbound port for this switch was found", dpid)
                    log.error("DPID = %s - Getting switch ratio... FAIL(no valid ports found)", dpid)
                    return None
            else :
                    log.error("DPID = %s, No inbound port for this switch was found", dpid)
                    log.error("DPID = %s - Getting switch ratio... FAIL(no valid ports found)", dpid)
                    return None
        except Exception, e:
            print "Exception in getSwitchRatio"
            print e

    def getSwitchRatioWithSafeMargin(self, dpid, network_margin):
        '''
        Return the Ratio of the switch with this dpid
        Takes into account the bandwidth network_margin for new allocation
        '''
        try :
            #initialize variables
            switch_in_bw_ratio = 0
            switch_in_port_count = 0
            switch_out_bw_ratio = 0
            switch_out_port_count = 0
            
            #get the switch belonging to this dpid
            switch = self.topology.switches[dpid]
            
            log.debug("DPID = %s, #PORTS = %s ", dpid, len(switch.ports.values()))
            
            #flag to know if network margin has been added to one out and one in switch
            added_in_nm = 0
            added_out_nm = 0
            
            #check if it has a port that has enough resources
            for port in switch.ports.values() :
                #if this is an edge or core switch
                if switch.type == Switch.EDGE or switch.type == Switch.CORE:
                    if self.topology.switch_links.has_key(switch.dpid):
                        #check the ports connected to hosts ( to non openflow switches)
                        if not self.topology.switch_links[switch.dpid].has_key(port.id) :
                            log.debug("Adding in port ratio")
                            #increment the counter
                            switch_in_port_count += 1
                            #add the ratio of this port
                            if added_in_nm == 0:
                                switch_in_bw_ratio += self.getLinkRatioWithSafeMargin(switch.dpid, port.id, network_margin)
                                added_in_nm +=1
                            else:
                                switch_in_bw_ratio += self.getLinkRatio(switch.dpid, port.id)
                        else :
                            log.debug("Adding out port ratio")
                            #increment the counter
                            switch_out_port_count += 1
                            #add the ratio of this port
                            if added_out_nm == 0:
                                switch_out_bw_ratio += self.getLinkRatioWithSafeMargin(switch.dpid, port.id, network_margin)
                                added_out_nm +=1
                            else:
                                switch_out_bw_ratio += self.getLinkRatio(switch.dpid, port.id)
                else :
                    if self.topology.switch_links.has_key(switch.dpid):
                        #get the switch dpid to which this port connects
                        dst_dpid = self.topology.switch_links[switch.dpid][port.id][0]
                        #check if this link has interest to the algorithm
                        if self.topology.switches[dst_dpid].type == Switch.CORE :
                            log.debug("Adding in port ratio")
                            #increment the counter
                            switch_in_port_count += 1
                            #add the ratio of this port
                            if added_in_nm == 0:
                                switch_in_bw_ratio += self.getLinkRatioWithSafeMargin(switch.dpid, port.id, network_margin)
                                added_in_nm +=1
                            else:
                                switch_in_bw_ratio += self.getLinkRatio(switch.dpid, port.id)
                        else :
                            log.debug("Adding out port ratio")
                            #increment the counter
                            switch_out_port_count += 1
                            #add the ratio of this port
                            if added_out_nm == 0:
                                switch_out_bw_ratio += self.getLinkRatioWithSafeMargin(switch.dpid, port.id, network_margin)
                                added_out_nm +=1
                            else:
                                switch_out_bw_ratio += self.getLinkRatio(switch.dpid, port.id)
                        
            #TODO: TEMPORARY! Just until we found a way of discovering a core switch even if it has a "host" connected
            #ATENTION: NOT ACCURATE RESULT IN CASE OF CORE SWITCH
            '''
            if switch.type == Switch.CORE :
                if switch_out_port_count != 0:
                    #calculate the switch ratio
                    switch_out_ratio = switch_out_bw_ratio / switch_out_port_count
                    #calculate the switch ratio
                    switch_ratio = 2 * switch_out_ratio
                    
                    log.debug("DPID = %s, Ratio = %s - Getting switch ratio... DONE", dpid, switch_ratio)
                    
                    return switch_ratio
                else :
                    log.error("DPID = %s, No outbound port for this switch was found", dpid)
                    log.error("DPID = %s - Getting switch ratio... FAIL(no valid ports found)", dpid)
                    return None
            '''
            if switch_in_port_count != 0 :
                if switch_out_port_count != 0:
                    #calculate the switch ratio
                    switch_in_ratio = (switch_in_bw_ratio) / switch_in_port_count
                    switch_out_ratio = (switch_out_bw_ratio) / switch_out_port_count
                    #calculate the switch ratio
                    switch_ratio = (switch_in_ratio + switch_out_ratio)/2
                    
                    log.debug("DPID = %s, Ratio = %s - Getting switch ratio... DONE", dpid, switch_ratio)
                    
                    return switch_ratio
                else :
                    log.error("DPID = %s, No outbound port for this switch was found", dpid)
                    log.error("DPID = %s - Getting switch ratio... FAIL(no valid ports found)", dpid)
                    return None
            else :
                    log.error("DPID = %s, No inbound port for this switch was found", dpid)
                    log.error("DPID = %s - Getting switch ratio... FAIL(no valid ports found)", dpid)
                    return None
        except Exception, e:
            print "Exception in getSwitchRatioWithMargin"
            print e
    
    '''
    Link Related Methods
    '''
    def isNonSuitablePort(self, dpid, port):
        '''
        Check if a port is a non suitable port
        Returns True in case of non suitable port, False otherwise
        '''
        log.debug("DPID = %s, Port = %s - Checking if is non suitable port...", dpid, port)
        non_suitable = False
        try :
            if self.non_suitable_ports.has_key(dpid):
                if port not in self.non_suitable_ports[dpid]:
                    #check the other side of the link
                    if self.topology.switch_links.has_key(dpid):
                        if self.topology.switch_links[dpid].has_key(port):
                            (dpid2, port2) = self.topology.switch_links[dpid][port]
                            if self.non_suitable_ports.has_key(dpid2):
                                if port2 in self.non_suitable_ports[dpid2]:
                                    non_suitable = True
                            else:
                                self.non_suitable_ports[dpid2] = list()
                else:
                    non_suitable = True
            else:
                self.non_suitable_ports[dpid] = list()
            
            log.debug("DPID = %s, Port = %s, NonSuitable = %s - Checking if is non suitable port... DONE", dpid, port, non_suitable)
            return non_suitable
        except Exception, e:
            print "Exception in isNonSuitablePort"
            print e

    def getLink(self, policy_type, dpid, network_margin):
        '''
        Gets a link according to the policy type specified
        Returns the port corresponding to that link
        '''
        log.debug("DPID = %s - Getting Candidate Port...", dpid)
        if policy_type == self.FF :
            port = self.firstFitLink(dpid, network_margin)
        elif policy_type == self.BF :
            port = self.bestFitLink(dpid, network_margin)
        elif policy_type == self.WF :
            port = self.worstFitLink(dpid, network_margin)
        
        if port == None :
            log.debug("DPID = %s, Port = %s - Getting Candidate Port... FAIL(no good port found)", dpid, port)
            return None
        else :
            log.debug("DPID = %s, Port = %s - Getting Candidate Port... DONE", dpid, port)
            return port[1]

    def getRelevantPorts(self, dpid):
        '''
        Get a list of ports that matter to this DPID
        Takes into consideration the type of algorithm chosen
        return list of port numbers
        '''
        log.debug("DPID = %s - Getting relevant ports...", dpid)
        try :
            relevant_ports = list()
            #get all the ports that matter from the switch with this dpid
            if self.current_alg == self.ND :
                #if this is a CORE Switch
                if self.topology.switches[dpid].type == Switch.CORE :
                    for port in self.topology.switches[dpid].ports.values():
                        #if it is an important port
                        if self.topology.switch_links.has_key(dpid):
                            if self.topology.switch_links[dpid].has_key(port.id) :
                                #check if it is a suitable port
                                if not self.isNonSuitablePort(dpid, port.id) :
                                    relevant_ports.append(port.id)
                #if this is a AGGREGATION Switch            
                if self.topology.switches[dpid].type == Switch.AGGREGATION :
                    for port in self.topology.switches[dpid].ports.values():
                        #if this port leads to a edge switch, than this port is relevant
                        if self.topology.switch_links.has_key(dpid):
                            if self.topology.switch_links[dpid].has_key(port.id):
                                if self.topology.switches[self.topology.switch_links[dpid][port.id][0]].type == Switch.EDGE :
                                    #check if it is a suitable port
                                    if not self.isNonSuitablePort(dpid, port.id) :
                                        relevant_ports.append(port.id)
                #if this is a EDGE Switch
                if self.topology.switches[dpid].type == Switch.EDGE :
                    for port in self.topology.switches[dpid].ports.values():
                        #if it is an important port (doesn't link to any switch, just hosts)
                        if self.topology.switch_links.has_key(dpid):
                            if not self.topology.switch_links[dpid].has_key(port.id) :
                                #check if it is a suitable port
                                if not self.isNonSuitablePort(dpid, port.id) :
                                    relevant_ports.append(port.id)
            else :
                #if this is a CORE Switch - It cannot be a Core switch
                if self.topology.switches[dpid].type == Switch.CORE :
                    log.error("DPID = %s - Cannot get relevant ports for Core Switch in SD Algorithm", dpid)
                    return relevant_ports
                #if this is a AGGREGATION Switch      
                if self.topology.switches[dpid].type == Switch.AGGREGATION :
                    for port in self.topology.switches[dpid].ports.values():
                        #if this port leads to a core switch, than this port is relevant
                        if self.topology.switch_links.has_key(dpid):
                            if self.topology.switch_links[dpid].has_key(port.id):
                                if self.topology.switches[self.topology.switch_links[dpid][port.id][0]].type == Switch.CORE :
                                    #check if it is a suitable port
                                    if not self.isNonSuitablePort(dpid, port.id) :
                                        relevant_ports.append(port.id)
                #if this is a EDGE Switch
                if self.topology.switches[dpid].type == Switch.EDGE :
                    for port in self.topology.switches[dpid].ports.values():
                        #if it is an important port (doesn't link to any host, just switches)
                        if self.topology.switch_links.has_key(dpid):
                            if self.topology.switch_links[dpid].has_key(port.id) :
                                #check if it is a suitable port
                                if not self.isNonSuitablePort(dpid, port.id) :
                                    relevant_ports.append(port.id)
                                    
            log.debug("DPID = %s, #Relv.Ports = %s - Getting relevant ports... DONE", dpid, len(relevant_ports))
            return relevant_ports
        except Exception, e:
            print "Exception in getRelevantPorts"
            print e

    def firstFitLink(self, dpid, network_margin):
        '''
        Gets the first link that fits
        Takes into account the kind of link and the switch for the policy is applied
        Returns the port belonging to dpid which represent the link
        
        NOTE: TO be able to choose, it looks into self.current_alg
        '''
        
        #get relevant ports for this dpid
        relevant_ports = self.getRelevantPorts(dpid)
        
        #check if there's a port that has a ratio equal or minus then the max_bw_link_ratio
        for port_id in relevant_ports :
            if not self.isNonSuitablePort(dpid, port_id) :
                if self.getLinkRatioWithSafeMargin(dpid, port_id, network_margin)<= self.max_bw_link_ratio :
                    return (dpid, port_id)
        
        return None

    def bestFitLink(self, dpid, network_margin):
        '''
        Gets the best link that fits
        Takes into account the kind of link and the switch for the policy is applied
        Returns the port belonging to dpid which represent the link 
        
        NOTE: TO be able to choose, it looks into self.current_alg
        '''
        log.debug("DPID = %s - Getting BestFit Link...", dpid)
        try :
            #get relevant ports for this dpid
            relevant_ports = self.getRelevantPorts(dpid)
            
            #initialize variables
            best_fit = None
            best_fit_ratio = 0
            #check if there's a port that has a ratio equal or minus then the max_bw_link_ratio
            for port_id in relevant_ports :
                if not self.isNonSuitablePort(dpid, port_id) :
                    #get the current bandwidth usage for this dpid and port
                    curr_ratio = self.getLinkRatioWithSafeMargin(dpid, port_id, network_margin)
                    if curr_ratio  <= self.max_bw_link_ratio :
                        #see if it's a better fit
                        if curr_ratio >= best_fit_ratio :
                            best_fit = (dpid, port_id)
                            best_fit_ratio = curr_ratio
                            
            log.debug("DPID = %s, BFPortID = %s - Getting BestFit Link... DONE", dpid, best_fit)
            return best_fit
        except Exception, e:
            print "Exception in bestFitLink"
            print e

    def worstFitLink(self, dpid, network_margin):
        '''
        Gets the worst link that fits
        Takes into account the kind of link and the switch for the policy is applied
        Returns the port belonging to dpid which represent the link 
        
        NOTE: TO be able to choose, it looks into self.current_alg
        '''
        #get relevant ports for this dpid
        relevant_ports = self.getRelevantPorts(dpid)
        
        #initialize variables
        best_fit = None
        best_fit_ratio = 10
        #check if there's a port that has a ratio equal or minus then the max_bw_link_ratio
        for port_id in relevant_ports :
            if not self.isNonSuitablePort(dpid, port_id) :
                #get the current bandwidth usage for this dpid and port
                curr_ratio = self.getLinkRatioWithSafeMargin(dpid, port_id, network_margin)
                if curr_ratio  <= self.max_bw_link_ratio :
                    #see if it's a worst fit
                    if curr_ratio < best_fit_ratio :
                        best_fit = (dpid, port_id)
                        best_fit_ratio = curr_ratio
        
        return best_fit

    def getLinkRatio(self, dpid, port_id):
        '''
        Check the bandwidth usage for the specified dpid
        Return the current usage ratio
        '''
        # if it is a edge or core switch it might not have a of switch o the other side of the link
        log.debug("DPID = %s, Port = %s - Getting Link Ratio...", dpid, port_id)

        if self.topology.switches[dpid].type != Switch.AGGREGATION :
            #if this port connects to a non of switch
            if not self.topology.switch_links.has_key(dpid) or (self.topology.switch_links.has_key(dpid) and 
                                                                not self.topology.switch_links[dpid].has_key(port_id)):
                if self.topology.switches[dpid].type == Switch.CORE :
                    link_capacity = self.topology.outside_link_capacity
                    
                #IF it is a edge switch and connects to a host
                else :
                    link_capacity = self.topology.edge_link_capacity
                
                dst_switch = self.topology.switches[dpid]
            else :
                if self.topology.switches[dpid].type != Switch.EDGE :
                    dst_dpid = dpid
                else:
                    dst_dpid = self.topology.switch_links[dpid][port_id][0]
                    
                if self.topology.switches.has_key(dst_dpid) :
                    dst_switch = self.topology.switches[dst_dpid]
                else :
                    log.error("DPID = %s, PORT = %s - Switch to each this link connects doesn't exist", dpid, port_id)
                    return None
                
                #get the link capacity
                log.debug("Switch_type = %s - Getting link capacity...", dst_switch.type)
                if dst_switch.type == Switch.CORE :
                    link_capacity = self.topology.core_link_capacity
                elif dst_switch.type == Switch.AGGREGATION :
                    link_capacity = self.topology.agg_link_capacity
                elif dst_switch.type == Switch.EDGE :
                    link_capacity = self.topology.edge_link_capacity
                elif dst_switch.type == Switch.UNKNOWN :
                    log.error("Trying to get link capacity from switch of type UNKNOWN")
                    return None
                else :
                    log.error("Invalid Switch type")
                    return None
                    
        else :
            if self.topology.switch_links.has_key(dpid) :
                if self.topology.switch_links[dpid].has_key(port_id) :
                    dst_dpid = self.topology.switch_links[dpid][port_id][0]
                else :
                    log.error("DPID = %s, PORT = %s - Link doesn't exist", dpid, port_id)
                    return None
            else :
                log.error("DPID = %s - Switch doesn't have any link", dpid)
                return None
            
            if self.topology.switches.has_key(dst_dpid) :
                dst_switch = self.topology.switches[dst_dpid]
            else :
                log.error("DPID = %s, PORT = %s - Switch to each this link connects doesn't exist", dpid, port_id)
                return None
            
            #get the link capacity
            log.debug("Switch_type = %s - Getting link capacity...", dst_switch.type)
            if dst_switch.type == Switch.CORE :
                link_capacity = self.topology.core_link_capacity
            elif dst_switch.type == Switch.AGGREGATION :
                link_capacity = self.topology.agg_link_capacity
                log.warning("Connections between aggregations switches not working yet")
            elif dst_switch.type == Switch.EDGE :
                link_capacity = self.topology.agg_link_capacity
            elif dst_switch.type == Switch.UNKNOWN :
                log.error("Trying to get link capacity from switch of type UNKNOWN")
                return None
            else :
                log.error("Invalid Switch type")
                return None
            
            
        log.debug("Switch_type = %s, Link Capacity = %s - Getting link capacity... DONE", dst_switch.type, link_capacity)
                
        bit_rate = self.stats.getBitRateByDpid(dpid)
        
        if len(bit_rate) == 0 or (not bit_rate.has_key(port_id)) :
            log.debug("DPID = %s, Port = %s- No stats for this switch have been collected yet", dpid, port_id)
            log.debug("DPID = %s, Port = %s - Getting Link Ratio... FAIL", dpid, port_id)
            return 0
        else :
            link_ratio = bit_rate[port_id]/link_capacity
            log.debug("DPID = %s, Port = %s, Link ratio = %s(%s/%s) - Getting Link Ratio... DONE", dpid, port_id, link_ratio, bit_rate[port_id], link_capacity)
            
            return link_ratio

    def getLinkRatioWithSafeMargin(self, dpid, port_id, network_margin):
        '''
        Check the bandwidth usage for the specified dpid
        Takes into consideration the safe network_margin bandwidth for new host to be allocated
        Return the current usage ratio
        '''
        # if it is a edge or core switch it might not have a of switch o the other side of the link
        log.debug("DPID = %s, Port = %s - Getting Link Ratio...", dpid, port_id)
        
        if self.topology.switches[dpid].type != Switch.AGGREGATION :
            #if this port connects to a non of switch
            if not self.topology.switch_links.has_key(dpid) or (self.topology.switch_links.has_key(dpid) and 
                                                                not self.topology.switch_links[dpid].has_key(port_id)):
                if self.topology.switches[dpid].type == Switch.CORE :
                    link_capacity = link_capacity = self.topology.outside_link_capacity
                    log.debug("Core Link capacity = %s", link_capacity)
                #IF it is a edge switch
                else :
                    link_capacity = self.topology.edge_link_capacity
                
                dst_switch = self.topology.switches[dpid]
            else :
                if self.topology.switches[dpid].type != Switch.EDGE :
                    dst_dpid = dpid
                else:
                    dst_dpid = self.topology.switch_links[dpid][port_id][0]
                
                if self.topology.switches.has_key(dst_dpid) :
                    dst_switch = self.topology.switches[dst_dpid]
                else :
                    log.error("DPID = %s, PORT = %s - Switch to each this link connects doesn't exist", dpid, port_id)
                    return None
                
                #get the link capacity
                log.debug("Switch_type = %s - Getting link capacity...", dst_switch.type)
                if dst_switch.type == Switch.CORE :
                    link_capacity = self.topology.core_link_capacity
                elif dst_switch.type == Switch.AGGREGATION :
                    link_capacity = self.topology.agg_link_capacity
                elif dst_switch.type == Switch.EDGE :
                    link_capacity = self.topology.edge_link_capacity
                elif dst_switch.type == Switch.UNKNOWN :
                    log.error("Trying to get link capacity from switch of type UNKNOWN")
                    return None
                else :
                    log.error("Invalid Switch type")
                    return None
                    
        else :
            if self.topology.switch_links.has_key(dpid) :
                if self.topology.switch_links[dpid].has_key(port_id) :
                    dst_dpid = self.topology.switch_links[dpid][port_id][0]
                else :
                    log.error("DPID = %s, PORT = %s - Link doesn't exist", dpid, port_id)
                    return None
            else :
                log.error("DPID = %s - Switch doesn't have any link", dpid)
                return None
            
            if self.topology.switches.has_key(dst_dpid) :
                dst_switch = self.topology.switches[dst_dpid]
            else :
                log.error("DPID = %s, PORT = %s - Switch to each this link connects doesn't exist", dpid, port_id)
                return None
            
            #get the link capacity
            log.debug("Switch_type = %s - Getting link capacity...", dst_switch.type)
            if dst_switch.type == Switch.CORE :
                link_capacity = self.topology.core_link_capacity
            elif dst_switch.type == Switch.AGGREGATION :
                link_capacity = self.topology.agg_link_capacity
                log.warning("Connections between aggregations switches not working yet")
            elif dst_switch.type == Switch.EDGE :
                link_capacity = self.topology.agg_link_capacity
            elif dst_switch.type == Switch.UNKNOWN :
                log.error("Trying to get link capacity from switch of type UNKNOWN")
                return None
            else :
                log.error("Invalid Switch type")
                return None
            
            
        log.debug("Switch_type = %s, Link Capacity = %s - Getting link capacity... DONE", dst_switch.type, link_capacity)
                
        bit_rate = self.stats.getBitRateByDpid(dpid)
        
        if len(bit_rate) == 0 or (not bit_rate.has_key(port_id)) :
            log.debug("DPID = %s, Port = %s- No stats for this switch have been collected yet", dpid, port_id)
            log.debug("DPID = %s, Port = %s, Link ratio = %s - Getting Link Ratio... FAIL", dpid, port_id)
            return 0
        else :
            #Calculate the link ratio and take into consideration the safe network_margin 
            link_ratio = (bit_rate[port_id]+ network_margin)/link_capacity
            log.debug("DPID = %s, Port = %s, Link ratio = %s((%s+%s)/%s)  - Getting Link Ratio... DONE", 
                dpid, port_id, link_ratio, bit_rate[port_id], network_margin, link_capacity)
            
            return link_ratio

    def linkHasEnoughResources(self, dpid, port):
        '''
        Check if a link has enough resources to allocate another VM
        Return True in case it has, otherwise False
        '''
        if self.getLinkRatio(dpid, port) <= self.max_bw_link_ratio :
            return True
        else :
            return False
