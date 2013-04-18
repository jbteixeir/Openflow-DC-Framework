import pox.openflow.libopenflow_01 as openflowlib
from pox.lib.addresses import IPAddr
from pox.core import core
from ext.ERCSStructures.ercs_switch import Switch
from pox.lib.addresses import EthAddr

log = core.getLogger()

class HostRules(object):
    '''
    Class which holds the rules related to one host
    core_rules - host rules that are allocated in the core switches
    agg_rules  - host rules that are allocated in the agg switches
    edge_rules - host rules that are allocated in the edge switches
    '''
    
    class HostRuleForSwitch(object):
        '''
        Rules corresponding to a specific host
        inbound  - rule for the inbound traffic
        outbound - rule for the outbound traffic
        '''
        inbound_rule = openflowlib.ofp_flow_mod()
        outbound_rule = openflowlib.ofp_flow_mod()
        
        def __init__(self, inbound_rule, outbound_rule):
            self.inbound_rule = inbound_rule
            self.outbound_rule = outbound_rule
    
    core_rules = HostRuleForSwitch
    agg_rules = HostRuleForSwitch
    edge_rules = HostRuleForSwitch
    
    def __init__(self, core_rules, agg_rules, edge_rules):
        self.core_rules = core_rules
        self.agg_rules = agg_rules
        self.edge_rules = edge_rules
        

class Rules(object):
    '''
    Class containing the rules installed to the OF switches
    Allows also their installation or removal/edition
    *Should it aggregate the rules or not? If no advantage - statistics per flow (useful if later gonna do some shapper)
        No aggregation for now, maybe later
    *otherwise less rules, less memory used (should read more bibliography and decided based on that
    *No backup rules are made, because of the nature of the algorithm used(algorithm for the placement of the virtual machines
    * (Yes! Keep one back up rule for each host. 
        To decide what kind look for statistics regularly and install rules / update them(after installed)
        Should it automatically update the rules based on topology changes?
            NO, not useful because we won't have any changes
            Except if it is switches, and in this case only for backup
    
    #variables
    host_rules - Dict. of rules indexed by host_id
          - -Useful in case supernetting is done and then host leaves and a rule for each host needs to be replaced or new subnet calculated...
          
    supernetting - flag to enable or disable supernetting when installing the rules in the switches
    ercs_topology - instance of ERCSTopology.ercs_topology
    '''
    
    SUPERNET_OFF = 0
    SUPERNET_ON = 1
    
    host_rules = {}
    supernetting = SUPERNET_OFF
    
    def __init__(self, host_rules, supernetting, ercs_topology):
        self.host_rules = host_rules
        self.supernetting = supernetting
        self.ercs_topology = ercs_topology
        
        log.info("ERCS Rules - ready")

    def installAllHostRules(self, host_id, host_ip, core_id, core_port_in, core_port_out, agg_id, 
                         agg_port_in, agg_port_out, edge_id, edge_port_in, edge_port_out, queue_type):
        '''
        Install a rule in all switches to give the host connectivity
        Take in consideration supernetting (or not)
        '''
        log.debug("Installing all rules for each switch type...")
        #if supernetting flag is activated
        if self.supernetting :
            #Not implemented yet
            pass
        
        #if supernetting flag is not activated
        else :
            
            #edge rules
            edge_rules = self.installHostRule(host_id, host_ip, edge_id, edge_port_in, edge_port_out, queue_type)
            
            #aggregation rules
            agg_rules = self.installHostRule(host_id, host_ip, agg_id, agg_port_in, agg_port_out, queue_type)
            
            #core rules
            core_rules = self.installHostRule(host_id, host_ip, core_id, core_port_in, core_port_out, queue_type)
            
            #check if any error occured
            if (edge_rules == None) or (agg_rules == None) or (core_rules == None) :
                log.debug("Installing all rules for each switch type... Fail")
                return
            
            #store all of the rules in the dictionary
            self.host_rules[host_id] = HostRules(core_rules, agg_rules, edge_rules)
        
        log.debug("Installing all rules for each switch type... Done")
            
    def installHostRule(self, host_id, host_ip, switch_id, switch_port_in, switch_port_out, queue_type):
        '''
        Install rules for one switch related to one host
        Returns the switch_rules (so they later can be added to self.host_rules (or other things))
        '''
        log.debug("Dpid = %s - Installing rules for this switch... ", switch_id)
        #verify that the switches in which we are trying to implement the rule exist
        if not self.ercs_topology.switches.has_key(switch_id):
            log.debug("Dpid = %s - Installing rules for this switch... (switch not found in topology) Fail", switch_id)
            return None
        
        #inbound rule
        in_msg = openflowlib.ofp_flow_mod()
        #TODO: should priority be set in case later supernetting is done?
        #default openflow priority 32768
        in_msg.priority = 32769
        in_msg.match.dl_type = 0x800
        in_msg.match.nw_dst = host_ip
        #in_msg.actions.append(openflowlib.ofp_action_enqueue(port = switch_port_in, queue_id = queue_type))
        in_msg.actions.append(openflowlib.ofp_action_output(port = switch_port_in))
        # if self.ercs_topology.switches[switch_id].type == Switch.EDGE:
        #     in_msg.actions.append(openflowlib.ofp_action_dl_addr.set_dst(EthAddr(str(self.ercs_topology.hosts[host_id].ports.keys()[0]))))
        #     print str(self.ercs_topology.hosts[host_id].ports.keys()[0])
        #print "Port in",switch_port_in, "->", queue_type
        
        #outbound rule
        out_msg = openflowlib.ofp_flow_mod()
        #TODO: should priority be set in case later supernetting is done?
        out_msg.priority = 32769
        out_msg.match.dl_type = 0x800
        out_msg.match.nw_src = host_ip
        #out_msg.actions.append(openflowlib.ofp_action_enqueue(port = switch_port_out, queue_id = queue_type))
        out_msg.actions.append(openflowlib.ofp_action_output(port = switch_port_out))
        #print "POrt out",switch_port_out
        #print "Port out",switch_port_in, "->", queue_type
        
        #store the rules
        switch_rules = HostRules.HostRuleForSwitch(in_msg, out_msg)
        try:        
            #install the rules i the switch
            if self.ercs_topology.switches.has_key(switch_id):
                #print self.ercs_topology.switches[switch_id].connection
                self.ercs_topology.switches[switch_id].connection.send(in_msg)
                self.ercs_topology.switches[switch_id].connection.send(out_msg)
                log.debug("Dpid = %s - Installing rules for this switch... Done", switch_id)
            else :
                log.error("Dpid = %s - Trying to install rule in switch, but switch doesn't exist", switch_id)
        except Exception, e:
            log.debug("Dpid = %s - Installing rules for this switch... Fail", switch_id)
            print e
        return switch_rules