'''
Created on Nov 9, 2012

@author: Jose Teixeira
'''

from pox.core import core
from ext.ERCSStructures.ercs_switch import Switch
from ext.ERCSStructures.ercs_host import Host
from ext.ERCSStructures.ercs_port import Port

import pox.openflow.libopenflow_01 as of

import struct
import socket
import thread
import time
import threading
import sys
import os

from pox.lib.packet.ethernet import ethernet
from pox.lib.packet.ipv4 import ipv4
from pox.lib.packet.arp import arp
from pox.lib.recoco.recoco import Sleep
from pox.lib.addresses import IPAddr, EthAddr

log = core.getLogger()

class Topology(object):
    '''
    classdocs
    
    switches - Dict of switches indexed by dpid
    hosts - Dict of hosts indexed by host_id -> (len(self.hosts)+1)
    switch_links - Dict of switch links indexed by (dpid). 
                   Each entry gives a dict index by port 
                   which than gives (dpid, port) which is connected to
                       
    host_links - Dict of host links indexed by (host_id). 
                 Each entry gives a dict index by port
                 which than gives (dpid, ports) which is connected to
     
    out_hosts -  Dict of outside hosts indexed by [dpid]. 
                 Each entry gives a dict index by [port]
                 which than gives (host_mac, host_ip) which is connected to
    
     
        
    edge_link_capacity |
    agg_link_capacity  |> Capacity of the link
    core_link_capacity |
    
    host_hardware - (cpu, ram, disk) host hardware caracteristics
    '''
    CORELINKDEFAULT = 10000
    AGGLINKDEFAULT = 1000
    EDGELINKDEFAULT = 100
    
    HOSTCPUDEFAULT = 24
    HOSTRAMDEFAULT = 32
    HOSTDISKDEFAULT = 2000
    
    ALLHOSTSSLEEPTIME = 30
    
    ALLHOSTSDISCOVERED = False

    ARPRULESINSTALLED = False
    
    def __init__(self, inithandler = None):
        '''
        Constructor
        '''
        self.switches = {}
        self.hosts = {}
        self.switch_links = {}
        self.host_links = {}
        self.out_hosts = {}
    
        
        #Add Listener for openflow, Topology, host_tracker
        core.openflow.addListeners(self)
        core.openflow_discovery.addListeners(self)
        core.host_tracker.addListeners(self)
        
        if inithandler == None :
            self.askForArgs()
        else :
            self.getArgsFromIni(inithandler)
        
        #ask if all the hosts have been discovered, so we can tell that the other switch are core switches
        #TODO: Fix bugs
        t2 = threading.Thread(target=self.allHostsDiscovered, args=())
        t2.daemon = True
        t2.start()
        #t2.join()
        #thread.start_new_thread(self.allHostsDiscovered, ())
        
        #TODO: Figure out a way of discovering the hosts automatically. The think below doesn't work        
        #thread.start_new_thread(self.pingHostsFromPool, (self.host_ip_pool[0], self.host_ip_pool[1]))
    
    '''
    Experiences
    
    def _handle_PacketIn (self, event):
        """
        Handles packet in messages from the switch.
        """
    '''
    '''
    Auxiliary methods
    '''
    def askForArgs(self):
        '''
        Ask for values 
        '''
        #Ask for the link capacity in the different type of links
        #core
        self.core_link_capacity = raw_input("Please insert link capacity between core and agg switches (Mbps): ")
        if self.core_link_capacity == "":
            self.core_link_capacity = self.CORELINKDEFAULT
            log.info("Core Link Capacity set to default - %s Mbps", self.CORELINKDEFAULT)
        while not is_number(self.core_link_capacity):
            self.core_link_capacity = raw_input("This is not a valid number, please insert a valid value: ")
        #Agg
        self.agg_link_capacity = raw_input("Please insert link capacity between agg and edge switches (Mbps): ")
        if self.agg_link_capacity == "":
            self.agg_link_capacity = self.AGGLINKDEFAULT
            log.info("Core Link Capacity set to default - %s Mbps", self.AGGLINKDEFAULT)
        while not is_number(self.agg_link_capacity):
            self.agg_link_capacity = raw_input("This is not a valid number, please insert a valid value: ")
        #edge
        self.edge_link_capacity = raw_input("Please insert link capacity between edge switches and hosts (Mbps): ")
        if self.edge_link_capacity == "" :
            self.edge_link_capacity = self.EDGELINKDEFAULT
            log.info("Core Link Capacity set to default - %s Mbps", self.EDGELINKDEFAULT)
        while not is_number(self.edge_link_capacity):
            self.edge_link_capacity = raw_input("This is not a valid number, please insert a valid value: ")
            
        
        #Ask for the host caracteristics
        #cpu
        cpu = raw_input("Please insert the host cpu characteristics : ")
        if cpu == "" :
            cpu = self.HOSTCPUDEFAULT
            log.info("Host CPU Capacity set to default - %s Cores", self.HOSTCPUDEFAULT)
        while not is_number(cpu):
            cpu = raw_input("This is not a valid number, please insert a valid value: ")
        #ram
        ram = raw_input("Please insert the host ram characteristics : ")
        if ram == "" :
            ram = self.HOSTRAMDEFAULT
            log.info("Host RAM Capacity set to default - %s GB", self.HOSTRAMDEFAULT)
        while not is_number(ram):
            ram = raw_input("This is not a valid number, please insert a valid value: ")
        #disk
        disk = raw_input("Please insert the host disk characteristics : ")
        if disk == "" :
            disk = self.HOSTDISKDEFAULT
            log.info("Host DISK Capacity set to default - %s GB", self.HOSTDISKDEFAULT)
        while not is_number(disk):
            disk = raw_input("This is not a valid number, please insert a valid value: ")
        
        self.host_hardware = (cpu, ram, disk)
        
        #Ask for host Ip pool so hosts can be discovered
        #TODO: Verify if it is a host pool
        '''
        self.host_ip_pool = raw_input("Please insert the host ip pool(ex:10.0.0.0 10.0.0.1): ")
        if len(self.host_ip_pool.split(" ", 1)) == 2 :
            self.host_ip_pool = (self.host_ip_pool.split(" ", 1)[0], self.host_ip_pool.split(" ", 1)[1])
        else :
            self.host_ip_pool = ("","")
        while not isIP(self.host_ip_pool[0]) or not isIP(self.host_ip_pool[1]) or not isValidIpPool(self.host_ip_pool[0], self.host_ip_pool[1]):
            self.host_ip_pool = raw_input("Please insert a valid host ip pool: ")
            if len(self.host_ip_pool.split(" ", 1)) == 2 :
                self.host_ip_pool = (self.host_ip_pool.split(" ", 1)[0], self.host_ip_pool.split(" ", 1)[1])
            else :
                self.host_ip_pool = ("","")
        '''
    
    def getArgsFromIni(self, inithandler):
        '''
        Get values from the ini file
        '''
        try :
            section = "topology"
            key = "outside_link"
            self.outside_link_capacity = float(inithandler.read_ini_value(section, key))
            key = "core_link"
            self.core_link_capacity = float(inithandler.read_ini_value(section, key))
            key = "agg_link"
            self.agg_link_capacity = float(inithandler.read_ini_value(section, key))
            key = "edge_link"
            self.edge_link_capacity = float(inithandler.read_ini_value(section, key))
            
            print self.core_link_capacity
            log.debug("Successfully got topology values")
            
            section = "host"
            key = "cpu"
            cpu = int(inithandler.read_ini_value(section, key))
            key = "ram"
            ram = int(inithandler.read_ini_value(section, key))
            key = "disk"
            disk = int(inithandler.read_ini_value(section, key))
            
            self.host_hardware = (cpu, ram, disk)
            
            log.debug("Successfully got host values")
            
        except Exception, e :
            log.error("INI File doesn't contain expected values")
            print e
            os._exit(0)
    
    def addHost(self, ports):
        '''
        Creates a new Host
        returns the new host id
        '''
        new_host_id = len(self.hosts)+1
        self.hosts[new_host_id] = Host(new_host_id, ports, self.host_hardware)
        
        return new_host_id
        
        
    def getHostIdByMacAddress(self, mac_address):
        '''
        Get and Host ID based on an Mac Address
        Return a matching Host ID
        Note: Checks for duplicates
        '''
        host_id = None
        #TODO: should i check for duplicate entries?
        for temp_host_id in self.hosts.keys() :
            if mac_address in self.hosts[temp_host_id].ports.keys() :
                if host_id != None :
                    log.debug("Host1 ID = %s, Host2 ID = %s - Hosts with the same Mac were found", host_id, temp_host_id)
                host_id = temp_host_id
            
        return host_id
    
    def getSwitchDpidByMacAddress(self, mac_address):
        '''
        Get switch Dpid by Mac Address
        return the switch dpid
        '''
        #TODO: should i check for duplicate entries?
        for switch in self.switches :
            if mac_address in switch.ports.keys() :
                return switch.dpid
        
        return None
    
    def pingHostsFromPool(self, start_ip, end_ip):
        '''
        Transforms a pool into a list of ips
        Returns the list
        '''
        curr_ip = ip2int(start_ip)
        while(curr_ip <= ip2int(end_ip)) :
            #ping this ip 
            log.debug("IP = %s - Pinging...", int2ip(curr_ip))
            self.pingHost(int2ip(curr_ip))
            #increment currIp
            curr_ip = curr_ip+1
        
    
    def pingHost(self, ip_address):
        r = arp() # Builds an "ETH/IP any-to-any ARP packet
        r.opcode = arp.REQUEST
        #r.hwdst = EthAddr("ff:ff:ff:ff:ff:ff")
        r.protodst = IPAddr(ip_address)
        # src is ETHER_ANY, IP_ANY
        e = ethernet(type=ethernet.ARP_TYPE, src=r.hwsrc, dst=r.hwdst)
        e.set_payload(r)
        while len(self.switches.keys()) == 0 :
            Sleep(1)
               
        dpid = self.switches.keys()[0]
        log.debug("%i sending ARP REQ to %s %s",
                dpid, str(r.hwdst), str(r.protodst))
        msg = of.ofp_packet_out(data = e.pack(),
                               action = of.ofp_action_output(port = of.OFPP_FLOOD))
        
        if not core.openflow.sendToDPID(dpid, msg.pack()):
            log.debug("%i ERROR sending ARP REQ to %s %s",
                    dpid, str(r.hwdst), str(r.protodst))
    '''
    Host related events / methods
    '''
    def makeHostsDiscoverable(self):
        '''
        Pings all the hosts in the pool so that the host_tracker can find them.
        '''
        pass
    
    def _handle_HostJoin(self, event):
        if not self.ALLHOSTSDISCOVERED :
            #Get the host Id by the mac address
            host_id = self.getHostIdByMacAddress(event.host_mac_address)
            #if host doesn't exists yet
            if host_id == None :
                #add new host
                new_host_id = self.addHost({})
                self.hosts[new_host_id].addPort(event.host_mac_address, [event.host_ip_address])
                log.debug("HostId = %s - New Host Added", new_host_id)
            #if host exists
            else :
                #Check if host already has this port
                if event.host_mac_address in self.hosts[host_id].ports.keys() :
                    #check if this port doesn't have the ip address
                    if event.host_ip_address not in self.hosts[host_id].ports[event.host_mac_address].ip_addresses :
                        self.hosts[host_id].ports[event.host_mac_address].ip_addresses.append(event.host_ip_address)
                        log.debug("HostId = %s, PortId = %s, IpAddress %s - New Ip Address Added to Host", 
                                  new_host_id,self.hosts[host_id].ports[event.host_mac_address].id, event.host_ip_address)
                else :
                    #add port with ip address to the host
                    self.hosts[host_id].addPort( event.host_mac_address, [event.host_ip_address])
                    log.debug("HostId = %s, PortId = %s, IpAddress %s - New Port & Ip Address Added to Host", 
                                  new_host_id,self.hosts[host_id].ports[event.host_mac_address].id, event.host_ip_address)
            
            #Add Host link
            if host_id == None :
                host_id = self.getHostIdByMacAddress(event.host_mac_address)
                
            self.addHostLink(host_id, self.hosts[host_id].ports[event.host_mac_address].id, event.dpid, event.port)
        
        else :
            #Some of these might be core output ports. The rest are new hosts
            if self.switches.has_key(event.dpid):
                if self.switches[event.dpid].type == Switch.CORE :
                    if not self.out_hosts.has_key(event.dpid):
                        self.out_hosts[event.dpid] = {}
                    if not self.out_hosts[event.dpid].has_key(event.port):
                        self.out_hosts[event.dpid][event.port] = list()
                        log.debug("DPID = %s, Port = %s, Mac = %s, IP = %s - A core output port "+
                            "was found", event.dpid, event.port, event.host_mac_address, event.host_ip_address)
                    else:
                        self.out_hosts[event.dpid][event.port] = list()
                        log.debug("DPID = %s, Port = %s, Mac = %s, IP = %s - The host IP and Mac"+
                            " core output port was found", event.dpid, event.port, 
                            event.host_mac_address, event.host_ip_address)

                    self.out_hosts[event.dpid][event.port].append((event.host_mac_address, 
                        event.host_ip_address))
                    #for all the core swithes which don't have yet an output host ip and mac, set this one
                    #This is needed in case a output host is connected do multiple switches
                    #TODO: doesn't work yet if you have two outside hosts connecting to four different core switches
                    #for all the output ports previously detected, add the ip and mac of outside host
                    for dpid in self.out_hosts.keys():
                        for port in self.out_hosts[dpid].keys():
                            if [(None, None)] == self.out_hosts[dpid][port]:
                                self.out_hosts[dpid][port].append((event.host_mac_address, event.host_ip_address))
                                log.debug("DPID = %s, Port = %s, Mac = %s, IP = %s - The host IP and Mac"+
                                    " core output port was found", dpid, port, 
                                    event.host_mac_address, event.host_ip_address)
                                        

                else:
                    log.debug("DPID = %s, Port = %s - Trying to add host, but all hosts have already been discovered", 
                              event.dpid, event.port)
                '''                    
                #add the rest of the core output ports
                for dpid in self.switches.keys():
                    if self.switches[dpid].type == Switch.CORE:
                        for port_id in self.switches[dpid].ports.keys():
                            if not self.switch_links[dpid].has_key(port_id):
                                if not self.out_hosts.has_key(dpid):
                                    self.out_hosts[dpid] = {}
                                    if not self.out_hosts[dpid].has_key(port):
                                        self.out_hosts[dpid][port] = list()
                                
                                self.out_hosts[dpid][port_id].append((event.host_mac_address, event.host_ip_address))
                                log.debug("DPID = %s, Port = %s, Mac = %s, IP = %s - A core output port was found", dpid, 
                                    port_id, event.host_mac_address, event.host_ip_address)
                '''
                #Check if the mac and ip of all outside hosts have been discovered
                #If so, install arp rules in all switches
                #doesn't work with fat tree because of the loops
                miss_host_info = False
                for out_host in self.out_hosts:
                    for port in self.out_hosts[out_host]:
                        if self.out_hosts[out_host][port] == ('Unknown','Unknown') :
                            miss_host_info = True
                if miss_host_info == False:
                    #self.installArpRules()
                    pass
            else :
                log.debug("Trying to add host, but it doesn't connect to any known switch")

        
    def addHostLink(self, host_id, host_port_id, dpid, port):
        '''
        Add the host link 
        '''
        #if host doesn't exist in host_links
        if  not self.host_links.has_key(host_id) :
            self.host_links[host_id] = {host_port_id: (dpid, port)}
            log.debug("HostId = %s, HostPort = %s, Dpid = %s, Port = %s - New Host and Host Link Added",host_id, host_port_id, dpid, port)
        #If Host exists, but this port in the hostLink no
        elif not self.host_links[host_id].has_key(host_port_id) :
            self.host_links[host_id][host_port_id] = (dpid, port)
            log.debug("HostId = %s, HostPort = %s, Dpid = %s, Port = %s - New Host Link Added",host_id, host_port_id, dpid, port)
        #If host and port already exist, but are conencted to another switch or switch port
        elif self.host_links[host_id][host_port_id] !=  (dpid, port):
            (old_dpid, old_port) = self.host_links[host_id][host_port_id]
            self.host_links[host_id][host_port_id] = (dpid, port)
            log.debug("HostId = %s, HostPort = %s, Old_Dpid = %s, Old_Port = %s,"+ 
                      "New_Dpid = %s, New_Port = %s, - Host Link Updated",host_id, host_port_id, old_dpid, old_port, dpid, port)
        
        #start classifying the switches
        self.classifySwitchType(dpid)
        
    
    def _handle_HostMove(self, event):
        #TODO: We should do something or not?
        #At least change the host link
        pass
    
    def _handle_HostTimeout(self, event):
        
        #TODO: What should be done?
        #remove the entry from host links and from hosts?
        #Uninstall all the rules?
        
        pass
    
    '''
    Switch related events / methods
    '''
    def _handle_ConnectionUp(self, event):
        self._handle_SwitchJoin(event.dpid, event.connection, event.ofp.ports)
    
    def _handle_SwitchJoin(self, dpid, connection, ports):
        #If dpid already registered in the switches dictionary
        if dpid in self.switches.keys() :
            #Check if connection still the same
            if connection != self.switches[dpid].connection:
                log.debug("DPID =  %s - Connection Updated", dpid)
                #update connection
                self.switches[dpid].connection = connection
            #Check if it has a new port
            for port in ports :
                #only add if port wasn't already added
                if not self.switches[dpid].ports.has_key(port.port_no) :
                    #only add if port doesn't connect to controller
                    if port.port_no != 65534 :
                        self.switches[dpid].ports[port.port_no] = Port(port.port_no,port.hw_addr,list())
                        log.debug("DPID =  %s, Port_No = %s, Mac = %s - New Port Added", dpid, port.port_no, port.hw_addr)
                    else :
                        log.debug("DPID = %s - Port to controller detected (not adding to topology)", dpid)
        else :
            
            
            if len(ports) == 1 and ports[0].port_no == 65534:
                log.debug("DPID = %s - False Switch detected (not adding to topology)", dpid)
                return
            else:
                #Register a new switch
                log.debug("DPID =  %s - New Switch Registered", dpid)
                self.switches[dpid] = Switch(connection, dpid, {}, Switch.UNKNOWN)
                
            #Add ports to switch
            for port in ports :
                #only add if port doesn't connect to controller
                if port.port_no != 65534 :
                    self.switches[dpid].ports[port.port_no] = Port(port.port_no,port.hw_addr,list())
                    log.debug("DPID =  %s, Port_No = %s, Mac = %s - New Port Added", dpid, port.port_no, port.hw_addr)
                else :
                    log.debug("DPID = %s - Port to controller detected (not adding to topology)", dpid)
    
    def _handle_SwitchTimeout(self, event):
        '''
        TODO: more complex than what you might think at the begining, because every port of a switch should be checked, no?
        '''
        pass
    
    def _handle_LinkEvent(self, event):

        if event.added == True :
            #NOTE: Link detection is half duplex so we'll only add 'half' link each time
            #      Although double check could be maid
            #if switch doesn't exist in the switch_links
            if self.switch_links.has_key(event.link.dpid1) == False :
                self.switch_links[event.link.dpid1]={event.link.port1: (event.link.dpid2, event.link.port2)}
                #self.switch_links[event.link.dpid2]={event.link.port2: (event.link.dpid1, event.link.port1)}
                log.debug("Dpid1 = %s, Port1 = %s, Dpid2 = %s, Port2 = %s - New Switch and New link detected",
                          event.link.dpid1, event.link.port1, event.link.dpid2, event.link.port2)
            #If switch has been added, but this link specifically not
            elif self.switch_links[event.link.dpid1].has_key(event.link.port1) == False :
                self.switch_links[event.link.dpid1][event.link.port1] = (event.link.dpid2, event.link.port2)
                #self.switch_links[event.link.dpid2][event.link.port2] = (event.link.dpid1, event.link.port1)
                log.debug("Dpid1 = %s, Port1 = %s, Dpid2 = %s, Port2 = %s - New link detected",
                          event.link.dpid1, event.link.port1, event.link.dpid2, event.link.port2)
            #Else check if this port is connected to a different switch dpid or diferent switch port
            else:
                #Check each direction of the link (1)
                if self.switch_links[event.link.dpid1][event.link.port1] != (event.link.dpid2, event.link.port2):
                    self.switch_links[event.link.dpid1][event.link.port1] = (event.link.dpid2, event.link.port2)
                    #self.switch_links[event.link.dpid2][event.link.port2] = (event.link.dpid1, event.link.port1)
                    log.debug("Dpid1 = %s, Port1 = %s, Dpid2 = %s, Port2 = %s - Link Updated (connects to new dpid or new port)",
                          event.link.dpid1, event.link.port1, event.link.dpid2, event.link.port2)
        #link timeout
        else :
            log.debug("Link removed")
    
    def _handle_PortStatus (self, event):
        '''
        Port status change in some switch
        '''
        # Only process 'sane' ports
        if event.port <= of.OFPP_MAX:
            if event.added :
                if not self.switches[event.dpid].ports.has_key(event.ofp.desc.port_no) and event.ofp.desc.port_no != 65534 :
                    self.switches[event.dpid].ports[event.ofp.desc.port_no] = Port(event.ofp.desc.port_no,event.ofp.desc.hw_addr,list())
                    log.debug("Dpid =  %s, Port_No = %s, Mac = %s - New Port Added", 
                              event.dpid, event.ofp.desc.port_no, event.ofp.desc.hw_addr)
                else:
                    log.debug("Dpid =  %s, Port_No = %s, Mac = %s - Adding port, but port already exists or connects to controller", 
                              event.dpid, event.ofp.desc.port_no, event.ofp.desc.hw_addr)
            elif event.deleted :
                if self.switches[event.dpid].ports.has_key(event.ofp.desc.port_no) :
                    del(self.switches[event.dpid].ports[event.ofp.desc.port_no])
                    log.debug("Dpid =  %s, Port_No = %s, Mac = %s - Port Deleted", 
                              event.dpid, event.ofp.desc.port_no, event.ofp.desc.hw_addr)
                else :
                    log.debug("Dpid =  %s, Port_No = %s, Mac = %s - Deleting port, but port doesn't exist", 
                              event.dpid, event.ofp.desc.port_no, event.ofp.desc.hw_addr)
            elif event.modified :
                log.debug("Dpid =  %s, Port_No = %s, Mac = %s - Port Definitions changed (Reason= Admin Down/Up, Ip Change, ...)", 
                          event.dpid, event.ofp.desc.port_no, event.ofp.desc.hw_addr)
    
    def classifySwitchType(self, edgedpid):
        '''
        Classifies the switch's based on being connected to host.
        Relations
            -Directly connected to host - Edge switch
            -Shares a Switch_link with a Edge Swith - Aggregation Switch
            -After all this to have been identified, the rest are core switches
        '''
        #set this switch type
        if self.switches[edgedpid].type == Switch.UNKNOWN :
            self.switches[edgedpid].type = Switch.EDGE
            log.debug("DPID = %s, Switch Type = %s - New Switch Classified", edgedpid, self.switches[edgedpid].type)
        
        #Find switches which share a switch link with this one
        if self.switch_links.has_key(edgedpid) :
            for port in self.switch_links[edgedpid].keys() :
                (dpid2, port2) = self.switch_links[edgedpid][port]
    
                if self.switches[dpid2].type == Switch.UNKNOWN :
                    #set the switch type to Aggregation
                    self.switches[dpid2].type = Switch.AGGREGATION
                    log.debug("DPID = %s, Switch Type = %s - New Switch Classified", dpid2, self.switches[dpid2].type)
                    
                #check the previous classification
                elif not self.switches[dpid2].type == Switch.AGGREGATION :
                    log.warning("DPID = %s, Switch Type = %s, New Type = %s - Bad Switch classification detected ", 
                        dpid2, self.switches[dpid2].type, Switch.EDGE)
                    #don't uncomment the next line because this was now suppose to happen
                    #self.switches[dpid2].type = Switch.AGGREGATION
                
    def getSwitchesByType(self, switch_type):
        '''
        Return a dict of switches based on their switch_type
        In case none exists, return an empty dictionary
        '''
        log.debug("SwitchType = %s - Getting Switches by type", switch_type)
        
        temp_switches = {}
        for dpid in self.switches:
            switch = self.switches[dpid]
            #log.debug("Running throught all switches")
            if switch.type == switch_type :
                #log.debug("Found a switch of this type")
                temp_switches[dpid] = switch
                
        log.debug("#Switch = %s - Returning switch dict", len(temp_switches))
        return temp_switches
        
    def isPortToHost(self, dpid, port):
        '''
        Check if this switch port connects to a host
        '''
        for key in self.host_links.keys() :
            if self.host_links[key][0] == dpid and self.host_links[key][1] == port:
                return True
        
        return False
    
    def installArpRules(self):
        if self.ARPRULESINSTALLED == False :
            for switch in self.switches.values():
                fm = of.ofp_flow_mod()
                fm.priority = 0x7000 # Pretty high
                fm.match.dl_type = ethernet.ARP_TYPE
                fm.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
                switch.connection.send(fm)
            self.ARPRULESINSTALLED == True


    def allHostsDiscovered(self):
        '''
        Asks if all the hosts have been discovered
        If so, then we can classify the remaining switches as core switches, 
            otherwise wait x seconds and ask again
        '''
        
        str = "Have all the hosts been discovered? (Current Host count = %i) (Y/N): " % len(self.hosts)
        sys.stdin.flush()
        all_hosts_discovered = raw_input(str)
             
        while all_hosts_discovered == "N" or all_hosts_discovered == "n" or all_hosts_discovered == "" :
            time.sleep(self.ALLHOSTSSLEEPTIME)
            str = "Have all the hosts been discovered? (Current Host count = %i) (Y/N): " % len(self.hosts)
            sys.stdin.flush()
            all_hosts_discovered = raw_input(str)
        
        if all_hosts_discovered == "Y" or all_hosts_discovered == "y" :
            self.ALLHOSTSDISCOVERED = True
            core_switch_count = 0
            agg_switch_count = 0
            edge_switch_count = 0

            #classify the switches edge switch and aggregation in case a link has only been 
            #discovered after a host already connected
            for switch in self.switches.values() :
                if switch.type == Switch.EDGE :
                    edge_switch_count +=1
                    self.classifySwitchType(switch.dpid)
            for switch in self.switches.values() :
                if switch.type == Switch.AGGREGATION :
                    agg_switch_count +=1
                #check all the switch without a type and set the type to core
                if switch.type == Switch.UNKNOWN :
                    switch.type = Switch.CORE
                    core_switch_count += 1
            
            log.info("\nTopology Information:\nCore Switches = %i\nAggregation Switches = %i\nEdge Switches = %i\nHosts = %i",
                     core_switch_count, agg_switch_count, edge_switch_count, len(self.hosts))
             
            #add the rest of the core output ports
            for dpid in self.switches.keys():
                if self.switches[dpid].type == Switch.CORE:
                    for port_id in self.switches[dpid].ports.keys():
                        if not self.switch_links[dpid].has_key(port_id):
                            if not self.out_hosts.has_key(dpid):
                                self.out_hosts[dpid] = {}
                                if not self.out_hosts[dpid].has_key(port_id):
                                    self.out_hosts[dpid][port_id] = list()
                            
                            self.out_hosts[dpid][port_id].append((None, None))
                            log.debug("DPID = %s, Port = %s, Mac = %s, IP = %s - A core output port was found", dpid, 
                                port_id, "Unknown", "Unknown")
            
        return
        
def isValidIpPool(ipaddress1, ipaddress2):
    '''
    Check if it is a valid Ip Pool
    ipaddress1 and ipaddress2 must be strings in the format "xx.xx.xx.xx"
    '''
    
    ipaddress1 = ipaddress1.split(".",3)
    ipaddress2 = ipaddress2.split(".",3)
    
    if int(ipaddress1[0]) <= int(ipaddress2[0]) :
        if int(ipaddress1[1]) <= int(ipaddress2[1]) :
            if int(ipaddress1[2]) <= int(ipaddress2[2]) :
                if int(ipaddress1[3]) <= int(ipaddress2[3]) :
                    return True
    
    return False

def ip2int(addr):                                                               
    return struct.unpack("!I", socket.inet_aton(addr))[0]                       

def int2ip(addr):                                                               
    return socket.inet_ntoa(struct.pack("!I", addr))  

def isIP(ipaddress):
    '''
    Check if Ip address is in the correct form
    IPv4 Only (for now)
    '''
    for no in ipaddress.split(".",3) :
        if (not is_number(no)) :
            log.debug("Bad IP Address")
            return False
        elif not ((int(no) >= 0) and (int(no) <= 255)):
            log.debug("Bad IP Address")
            return False
        
    return True

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False
                
def launch():
    Topology()
