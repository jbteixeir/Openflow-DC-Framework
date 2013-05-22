'''
Class: Topology
This modules contains all the data structurs with the topology information
-Switches
-Links
-Link Capacity
'''

from pox.core import core
from pox.openflow.discovery import Discovery
from pox.lib.util import dpidToStr

import time
import datetime

log = core.getLogger()

TIMEOUT = 10

class Topology (object) :
    
    #List of Openflow Switches (dpid's)
    switches = set()
    
    #Structure of the links (from Openflow.Discovery)
    #Link = namedtuple("Link",("dpid1","port1","dpid2","port2"))
    links = set()
    
    #capacity of the link (in mbps) between 2 dpid's
    #Example | links_capacity[dpid1][port1][dpid2][port2] = xxx 
    links_capacity = {}

    def __init__(self):
        
        # Add all links and switches
        for l in core.openflow_discovery.adjacency:
            self.switches.add(l.dpid1)
            self.switches.add(l.dpid2)
            self.links.add(l)
            
        print "WORKED!!"

    #While the switches don't support sending information about the link capacity
    #we cannot infer which switches are ES,AC & CS
    #Conclusion, ask the admin to say which dpid's are which
    def explicitSwitchDefinition (self, switchType):
        
        if switchType == 1 :
            switchTypeName = "Egde"
        elif switchType == 2 :
            switchTypeName = "Aggregation"
        elif switchType == 3 :
            switchTypeName = "Core"
        else :
            log.error("Invalid Argument")
            return -1
             
        log.info("Please indicate which dpid's (separated by space) belong to %s Switches:" %switchTypeName)
        sinput = raw_input()
        switches = sinput.split()
        
        #Convert dpid to integer and verify its validity
        for sw in switches:
            try:
                #convert to integer
                sw = int(sw)
                #check if dpid exists
                if(sw not in self.switches):
                    log.error("There is no switches with dpid = %s!" %sw)
                    return -1
                #TODO: check if dpid isn't in another switch list
            except ValueError:
                log.error("%s is not a valid dpid number!" %sw)
                return -1
        
        if switchType == 1 :
            self.edgeSwitches = switches
        elif switchType == 2 :
            self.aggregationSwitches = switches
        elif switchType == 3 :
            self.coreSwitches = switches   
         
    
    #While the switches don't support sending information about the link capacity
    #We have to explicitly define it
    #Assumes the links are fullduplex with the same bandwidth both ways
    #still needs to be testes (not done because this modules fires before the discovery one :S)
    def explicitSwitchCapacityDefinition (self, switchType):
        for link in self.links:
            try:
                self.links_capacity[link.dpid1][link.port1][link.dpid2][link.port2]
                self.links_capacity[link.dpid2][link.port2][link.dpid1][link.port1]
            except IndexError:
                log.info("Please indicate the link capacity (in mbps) %s.%s <-> %s.%s" %dpidToStr(link.dpid1) % link.port1 
                         %dpidToStr(link.dpid2) % link.port2 )
                try :
                    bw = int(raw_input()[0])
                except ValueError:
                    log.error("%s is not a valid bandwidth number!" %bw)
                    return -1
                
                self.links_capacity[link.dpid1][link.port1][link.dpid2][link.port2] = bw
                self.links_capacity[link.dpid2][link.port2][link.dpid1][link.port1] = bw
                
def launch ():
    """
    Starts the component
    """
    #def _launch():
    tpg = Topology()
    eventtime = datetime.time
    
    def eventtimeout():
        if datetime.time.minute == 10 :
            esd()    
    
    def esd():
        '''
        Get the admin to say which dpid's belong to each kind of router (edge, aggregation, core)
        '''
        var = -1
        while(var == -1):
            var = tpg.explicitSwitchDefinition(1)
        var = -1
        while(var == -1):
            var = tpg.explicitSwitchDefinition(2)
        var = -1
        while(var == -1):
            var = tpg.explicitSwitchDefinition(3)
        
    
        '''
        Get the admin to say which are the links capacities
        '''
        var=-1
        while(var==-1):
            var = tpg.explicitCapacitySwitchDefinition()
        
    '''
    Wait for the event that will start
    Raise and event when discovery module is stabilized
    '''
    core.addListenerByName("core.Discovery", eventtimeout())
