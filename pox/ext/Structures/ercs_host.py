from pox.lib.revent.revent import Event
from pox.core import core
from ext.Structures.ercs_port import Port
import time

log = core.getLogger()

class Host(object):
    '''
    id - unique id for hosts
    ports - Dictionary with all the ports of the host indexed by mac address (ext.ercs_port Port Class)
    firsttimeout - Indicates the time that the first timeout occurred in the last time
    
    cpu - amount of cpu this host has
    ram - amount of ram this host has
    disk - amount of disk this host has
    
    TODO: watch out for subinterfaces
    '''
    
    def __init__(self, id, ports, (cpu, ram, disk)):
        self.id = id
        self.ports = ports
        self.firsttimeout = -1
        
        self.hardware = (cpu, ram, disk)
    
    def addPort(self, port_mac_address, port_ip_addresses):
        '''
        '''
        #check if a port with this mac address hasn't been added
        if port_mac_address not in self.ports.keys() :
            port_id = len(self.ports)+1
            self.ports[port_mac_address] = Port(port_id, port_mac_address, port_ip_addresses)
            log.debug("Mac Address = %s - New Port added", self.ports[port_mac_address].mac_address)
        #check if (in case of already having this port) has new ipaddresses
        else :
            log.debug("Adding port to host but Port Already exists")
            #for all Ip Addresses in port_ip_addresses
            for ip_address in port_ip_addresses :
                #add this Ip Address (verificaitions done by the function addIpAdressToPort
                self.ports[port_mac_address].addIpAddressToPort(port_mac_address,ip_address)
                log.debug("Mac Address = %s , Ip Address = %s - Adding new Ip Address to port", port_mac_address, ip_address)
                    
    def addIpAddressToPort(self, port_mac_address, ip_address):
        '''
        Add an Ip Address to a specific port of this host
        In case the port doesn't exist, new port is added
        '''
        #If no port with this Mac Address exists
        if port_mac_address not in self.ports.keys() :
            #add new port to self.ports
            log.debug("Host doesn't know this port, adding port...")
            self.addPort(Port(-1, port_mac_address, [ip_address]))
        else :
            #if Ip Address already exists
            if ip_address in self.ports[port_mac_address].ip_addresses :
                log.debug("Mac Address = %s , Ip Address = %s - Ip Address already exist in this port", port_mac_address, ip_address)
            else :
                self.ports[port_mac_address].ip_addresses.append(ip_address)
                log.debug("Mac Address = %s , Ip Address = %s - Adding new Ip Address to port", port_mac_address, ip_address)
            
    
    def timeout(self):
        '''
        set first timeout
        '''
        self.firsttimeout = time.time()
            
    
    def timeSinceTimeout(self):
        '''
        time since Timeout (in seconds)
        '''
        return time.time() - self.firsttimeout
        
class HostEvent (Event):
    
    def __init__ (self, host_mac_address):
        Event.__init__(self)
        self.host_mac_address = host_mac_address
        
class HostJoin(HostEvent):
    '''
    Should be raised every time a new Host is discovered
    '''
    def __init__(self, host_mac_address, host_ip_address, dpid, port):
        '''
        dpid - dpid of the switch directly connected to this host
        port - port of the switch with dpid = dpid directly connected to this host
        host_mac_address - Mac Address of the host
        host_ip_address - IP Address of the host 
        '''
        HostEvent.__init__(self, host_mac_address)
        self.host_mac_address = host_mac_address
        self.host_ip_address = host_ip_address
        self.dpid = dpid
        self.port = port

class HostMove(HostEvent):
    '''
    Should be raised every time a host registered in a different switch then the one expected
    '''
    def __init__(self, host_mac_address, dpid, port):
        '''
        dpid - dpid of the switch directly connected to this host
        port - port of the switch with dpid = dpid directly connected to this host
        host_mac_address - Mac Address of the host
        '''
        #TODO: Should we check for duplicates?
        HostEvent.__init__(self, host_mac_address)
        self.host_mac_address = host_mac_address
        self.dpid = dpid
        self.port = port
        

class HostTimeout(HostEvent):
    '''
    Should be raised every time there's a time out
    '''
    def __init__(self, host_mac_address, host_ip_address) :
        '''
        host_mac_address - Mac Address of the host
        host_ip_address - IP Address of the host 
        '''
        HostEvent.__init__(self, host_mac_address)
        self.host_mac_address = host_mac_address
        self.host_ip_address = host_ip_address