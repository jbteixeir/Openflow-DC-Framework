import pox.openflow.libopenflow_01 as openflowlib
from pox.lib.addresses import IPAddr
from pox.core import core
from ext.Structures.ercs_switch import Switch
from pox.lib.addresses import EthAddr

log = core.getLogger()

class SwitchRule(object):
    """
    A Switch rule that applies for vm communication or intervm communication
    """
    def __init__(self, rule, dpid, outport, srcip = None, dstip = None):
        """
        @param rule A openflowlib.ofp_flow_mod() type of rule
        @param dpid Dpid of the switch
        @param outport Outport port for the traffic
        @param srcip Source IP of the virtualmachine (if srcip and dstip are both specified 
            this is a inter vm communication rule)
        @param dstip Destination IP of the virtualmachine (if srcip and dstip are both specified 
            this is a inter vm communication rule)
        """
        self.rule = rule
        self.dpid = dpid
        self.outport = outport
        self.srcip = srcip
        self.dstip = dstip        

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
    vm_rules - Dict. of rules indexed by host_id
        ->list of SwitchRule
          - -Useful in case supernetting is done and then host leaves and a rule for each host needs to be replaced or new subnet calculated...

    inter_vm_rules - Dict. of rules indexed by host_id1, host_id2
        ->list of SwitchRules
          
    supernetting - flag to enable or disable supernetting when installing the rules in the switches
    ercs_topology - instance of ERCSTopology.ercs_topology
    '''
    
    SUPERNET = 0
    supernetting = SUPERNET
    vm_rules = {}
    inter_vm_rules = {}
    
    def __init__(self, vm_rules, inter_vm_rules, supernetting, ercs_topology):
        self.vm_rules = vm_rules
        self.inter_vm_rules = inter_vm_rules
        self.supernetting = supernetting
        self.ercs_topology = ercs_topology

        core.openflow.addListeners(self)
        core.openflow_discovery.addListeners(self)

    def installHostRules(self, host_id, host_ip, core_id, core_port_in, core_port_out, agg_id, 
                         agg_port_in, agg_port_out, edge_id, edge_port_in, edge_port_out, queue_type):
        '''
        Install a rule in all switches to give the host connectivity
        Take in consideration supernetting (or not)
        '''
        log.info("Installing all rules for each switch type...")
        #if supernetting flag is activated
        if self.supernetting :
            #Not implemented yet
            pass
        
        #if supernetting flag is not activated
        else :
            
            #edge rules
            (in_edge_rule, out_edge_rule) = self.installHostRuleOnSwitch(host_id, host_ip, edge_id, edge_port_in, edge_port_out, queue_type)
            
            #aggregation rules
            (in_agg_rule, out_agg_rule) = self.installHostRuleOnSwitch(host_id, host_ip, agg_id, agg_port_in, agg_port_out, queue_type)
            
            #core rules
            (in_core_rule, out_core_rule) = self.installHostRuleOnSwitch(host_id, host_ip, core_id, core_port_in, core_port_out, queue_type)
            
            #check if any error occured
            # if (edge_rules == None) or (agg_rules == None) or (core_rules == None) :
            #     log.info("Installing all rules for each switch type... Fail")
            #     return
            
            #store all of the rules in the dictionary
            if not self.vm_rules.has_key(host_id):
                self.vm_rules[host_id] = list()

            self.vm_rules[host_id].append(SwitchRule(in_edge_rule, edge_id, edge_port_in, host_ip))
            self.vm_rules[host_id].append(SwitchRule(out_edge_rule, edge_id, edge_port_out, host_ip))

            self.vm_rules[host_id].append(SwitchRule(in_agg_rule, core_id, agg_port_in, host_ip))
            self.vm_rules[host_id].append(SwitchRule(out_agg_rule, core_id, agg_port_out, host_ip))

            self.vm_rules[host_id].append(SwitchRule(in_core_rule, edge_id, core_port_in, host_ip))
            self.vm_rules[host_id].append(SwitchRule(out_core_rule, edge_id, core_port_out, host_ip))
        
        log.info("Installing all rules for each switch type... Done")
            
    def installHostRuleOnSwitch(self, host_id, host_ip, switch_id, switch_port_in, switch_port_out, queue_type):
        '''
        Install rules for one switch related to one host
        Returns the switch_rules (so they later can be added to self.vm_rules (or other things))
        '''
        log.debug("Dpid = %s - Installing rules for this switch... ", switch_id)
        #verify that the switches in which we are trying to implement the rule exist
        if not self.ercs_topology.switches.has_key(switch_id):
            log.debug("Dpid = %s - Installing rules for this switch... (switch not found in topology) Fail", switch_id)
            return None
        
        #inbound rule
        in_rule = openflowlib.ofp_flow_mod()
        #TODO: should priority be set in case later supernetting is done?
        #default openflow priority 32768
        in_rule.priority = 32769
        in_rule.match.dl_type = 0x800
        in_rule.match.nw_dst = host_ip
        #in_rule.actions.append(openflowlib.ofp_action_enqueue(port = switch_port_in, queue_id = queue_type))
        in_rule.actions.append(openflowlib.ofp_action_output(port = switch_port_in))
        # if self.ercs_topology.switches[switch_id].type == Switch.EDGE:
        #     in_rule.actions.append(openflowlib.ofp_action_dl_addr.set_dst(EthAddr(str(self.ercs_topology.hosts[host_id].ports.keys()[0]))))
        #     print str(self.ercs_topology.hosts[host_id].ports.keys()[0])
        #print "Port in",switch_port_in, "->", queue_type
        
        #outbound rule
        out_rule = openflowlib.ofp_flow_mod()
        #TODO: should priority be set in case later supernetting is done?
        out_rule.priority = 32769
        out_rule.match.dl_type = 0x800
        out_rule.match.nw_src = host_ip
        #out_rule.actions.append(openflowlib.ofp_action_enqueue(port = switch_port_out, queue_id = queue_type))
        out_rule.actions.append(openflowlib.ofp_action_output(port = switch_port_out))
        #print "POrt out",switch_port_out
        #print "Port out",switch_port_in, "->", queue_type
        
        #install the rules in the switch
        try:        
            if self.ercs_topology.switches.has_key(switch_id):
                #print self.ercs_topology.switches[switch_id].connection
                self.ercs_topology.switches[switch_id].connection.send(in_rule)
                self.ercs_topology.switches[switch_id].connection.send(out_rule)
                log.debug("Dpid = %s - Installing rules for this switch... Done", switch_id)
            else :
                log.error("Dpid = %s - Trying to install rule in switch, but switch doesn't exist", switch_id)
        except Exception, e:
            log.debug("Dpid = %s - Installing rules for this switch... Fail", switch_id)
            print e

        #return both rules
        return (in_rule, out_rule)

    def deleteHostRules(self, host_ip):
        """
        TODO: Delete a host rule
        """
        del(self.vm_rules[host_id])

        #TODO: Delete rule form switches

    '''
    Rules between VMs
    '''
    def installInterVMRules(self, vm1_ip, vm2_ip, route_port_list):
        """
        Install rules between two VMs so they can communicate inside de DC
        @param vm1_ip IP Address of one virtual machine
        @param vm2_ip IP Address of the other virtual machine
        @param route_port_list List of routing decisions (dpid, port1, port2)
        """
        for (dpid, port1, port2) in link_list:
            log.debug("Dpid = %s - Installing rules for this switch... ", dpid)
            #rule
            vm1_rule = openflowlib.ofp_flow_mod()
            vm1_rule.priority = 32769
            vm1_rule.match.dl_type = 0x800
            vm1_rule.match.nw_dst = vm1_ip
            vm1_rule.match.nw_src = vm2_ip
            vm1_rule.actions.append(openflowlib.ofp_action_output(port = port1))

            vm2_rule = openflowlib.ofp_flow_mod()
            vm2_rule.priority = 32769
            vm2_rule.match.dl_type = 0x800
            vm2_rule.match.nw_src = vm1_ip
            vm2_rule.match.nw_dst = vm2_ip
            vm2_rule.actions.append(openflowlib.ofp_action_output(port = port2))

            #install the rules in the switch
            try:
                if self.ercs_topology.switches.has_key(dpid):
                    self.ercs_topology.switches[dpid].connection.send(vm1_rule)
                    self.ercs_topology.switches[dpid].connection.send(vm2_rule)
                    log.debug("Dpid = %s - Installing rules for this switch... Done", dpid)
                else :
                    log.error("Dpid = %s - Trying to install rule in switch, but switch doesn't exist", dpid)
            except Exception, e:
                log.debug("Dpid = %s - Installing rules for this switch... Fail", dpid)
                print e
            
            #Initialize inter_vm_rules if necessary
            if(not self.inter_vm_rules.has_key(vm1_ip)):
                self.inter_vm_rules[vm1_ip] = {}
                self.inter_vm_rules[vm1_ip][vm2_ip] = list()
            elif(not self.inter_vm_rules[vm1_ip].has_key(vm2_ip)):
                self.inter_vm_rules[vm1_ip][vm2_ip] = list()

            if(not self.inter_vm_rules.has_key(vm2_ip)):
                self.inter_vm_rules[vm2_ip] = {}
                self.inter_vm_rules[vm2_ip][vm1_ip] = list()
            elif(not self.inter_vm_rules[vm2_ip].has_key(vm1_ip)):
                self.inter_vm_rules[vm2_ip][vm1_ip] = list()

            #Save the rules
            self.inter_vm_rules[vm2_ip][vm1_ip].append(SwitchRule(vm1_rule, dpid, port1, vm2_ip, vm1_ip))
            self.inter_vm_rules[vm2_ip][vm1_ip].append(SwitchRule(vm2_rule, dpid, port2, vm1_ip, vm2_ip))
            self.inter_vm_rules[vm1_ip][vm2_ip].append(SwitchRule(vm1_rule, dpid, port1, vm2_ip, vm1_ip))
            self.inter_vm_rules[vm1_ip][vm2_ip].append(SwitchRule(vm2_rule, dpid, port2, vm1_ip, vm2_ip))

    def deleteInterVMRule(self, vm1_ip, vm2_ip):
        """
        Delete a rule between two VMs
        """
        del(self.inter_vm_rules[vm2_ip][vm1_ip])
        del(self.inter_vm_rules[vm1_ip][vm2_ip])

        #TODO: Delete rules from switches

        pass

    '''
    Handle Switch/Link fail
    '''
    def _handle_LinkEvent(self, event):
        """
        TODO: Raised when a link goes down. Checks which rules are affected,
              installs alternative routes and delete the old ones
        """
        pass

    def _handle_SwitchTimeout(self, event):
        """
        TODO: Raised when a switch goes down. Checks which rules are affected,
              installs alternative rules and delete the old ones
        """

        pass

    def checkAffectedRules(self, event):
        """
        TODO: Check which rules are affected by the link or switch and install alternative path if possible
                If not possible, raise a warning.
        TODO: Watch out for supernetting rules
        TODO: Watch out for interVMRules
        """
        pass

    def installAlternativeRules(self, event):
        pass
        