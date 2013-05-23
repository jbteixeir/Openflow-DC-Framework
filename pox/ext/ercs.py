'''
How to use the different ERCS Modules

###
ERCS
    Main Module, used to call the other modules, including the one's that not belong to ERCS, but that ERCS takes into consideration
    
ERCS Topology
    This Module discovers the topology (switches(ERCS Switch), hosts(ERCS Host), and their links(unidirectional - which means for any link there will be two entries)). 
    Everything is handled automatically.
    TODO: Timer to after discovering all host, identify the core switches
    For more information check the class ercs_topology. In there you can see what kind of data structures were used.

ERCS Rules
    Module cable of implementing the rules in the switches (oriented to the ERCS VM algorithm).
    All the rules are saved for future usage, and can be accessed through the right variables.
    Supernetting for aggregation and core switch's is available (although not right now) 
        -when instanciating simply put Rules.SUPERNET_ON option.
    TO install the rules for one host simply call rules.installAllHostRules(...)
    TODO: Supernetting to Agg and Core switches
    For more information check the class ercs_rules. In there you can see what kind of data structures were used.
    
ERCS Stats
    Module that retrieves statistics about the switches.
    For now only port statistics are available, and due to the nature of ERCS Algorithm, only bitrate is calculated.
    Possibility for other type of statistics to be included later.
    To request Bit Rate Statistics simply call stats.requestPortStats(connection, ports, Stats.PortRequest.BIT_RATE), where
        -connection - the connection of the switch which you want statistics for
        -ports - list of port numbers belonging to the switch which you want the bit rate
        -Stats.PortRequest.BIT_RATE - type of statistics requested (for now only Bitrate available)

    To receive the statistics listen to the ercs_stats module for PortsBitRate event's. In this event it is returned the 
    statistics for the requested ports. For more detail check the PortsBitRate class on ercs_stats

ERCS Switch
    Class where all the information about any switch is kept. This includes connection, dpid, ports and type(core,agg,edge)
    For more information please check ercs_switch

ERCS Host
    Class where all the information about a host is kept. This includes id, ports, and firsttimeout.
    For more information please check ercs_host

ERCS Port
    Class where all the information about a host is kept. This includes id, mac_address, ip_addresses(list of ip addresses 
    because of virtual interfaces)
    Class used by ERCS Switch and ERCS Host
    For more information please check ercs_port
    
ERCS VMReceiver
    
    TODO: (Currently not working) try UDP instead of TCP
    TODO: Raise the event
    *currently only support ipv4 (maybe later IPv6
'''
from ext.Stats.ercs_stats import Stats
from ext.Stats.ercs_stats_export import ERCSStatsExport
from ext.Topology.ercs_topology import Topology
from ext.Rules.ercs_rules import Rules
from pox.core import core
from ext.VM.vm_request_handler import VMReceiver
from ext.VM.vm_manager import VMManager
from ext.Topology import ercs_topology
from ext.INIHandler.INIHandler import IniHandler
from ext.XenCommunicator.xen_communicator import XenCommunicator
import thread



log = core.getLogger()

class ERCS():
    
    def __init__(self):
        
        #Start INIHandler
        log.info("INIHandler - Initializing...")
        self.inihandler = IniHandler()
        log.info("INIHandler - Ready")
        #Start ERCS Topology
        #TODO: choose the core switches
        log.info("ERCS Topology - Initializing...")
        self.topology = Topology(self.inihandler)
        log.info("ERCS Topology - Ready")
        
        #Start ERCS Statistics
        log.info("ERCS Stats - Initializing...")
        self.stats = Stats(self.inihandler)
        log.info("ERCS Stats - Ready")
        
        #Start ERCS Rules
        #TODO: Automatically adapt the rules in case a switch fails
        #TODO: Supernetting in the agg and core switches
        log.info("ERCS Rules - Initializing...")
        self.rules = Rules({}, Rules.SUPERNET_OFF, self.topology)
        log.info("ERCS Rules - Ready")
        
        #Start the ERCS VM Request Receiver
        #TODO: Send confirmation of VM Request received and VM Installed so later can send traffic
        log.info("ERCS VM Receiver - Initializing...")
        self.vmreceiver = VMReceiver(self.inihandler)
        log.info("ERCS VM Receiver - Ready")
        
        #Initialize the Xen Communicator
        log.info("Xen Communicator - Initializing...")
        self.xencommunicator = XenCommunicator(self.inihandler)
        log.info("Xen Communicator - Ready")

        #Start the ERCS VM Allocator
        #If you want to use xen instead of simulating the allocation add self.xencommunicator in the 
        #end of the arguments
        log.info("ERCS VM Manager - Initializing...")
        self.vmmanager = VMManager(self.topology, self.stats, self.rules, self.vmreceiver, 
            self.inihandler)
        log.info("ERCS VM Manager - Ready")
        
        #run the ERCS VM Request Receicer
        #This thread closes when the main thread closes
        self.vmreceiver.daemon = True
        self.vmreceiver.start()
        
        #Start the ERCS Stats Exporter
        log.info("ERCS Stats Exporter - Initializing...")
        self.statsexporter = ERCSStatsExport(self.inihandler, self.topology, self.stats, self.vmmanager)
        log.info("ERCS Stats Exporter - Ready")

    
def launch():
    
    import pox.topology
    pox.topology.launch()
    import pox.openflow.discovery
    pox.openflow.discovery.launch()
    import pox.openflow.topology
    pox.openflow.topology.launch()
    #import pox.forwarding.l2_pairs
    #pox.forwarding.l2_pairs.launch()
    #import pox.misc.arp_responder
    #pox.misc.arp_responder.launch()
    import pox.host_tracker.host_tracker
    pox.host_tracker.host_tracker.launch()
    
    ERCS()
