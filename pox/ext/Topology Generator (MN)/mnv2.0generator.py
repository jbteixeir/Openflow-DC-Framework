from mininet.topo import Topo
from mininet import net
class MyTopo( Topo ):
    "Simple topology example. For mininet 2.0"

    def __init__( self ):
        "Create custom topo."

        # Initialize topology
        Topo.__init__( self )

        #, core_no, core_out_port_no, agg_no, agg_out_port_no, edge_no, edge_out_port_no, host_no):
        #For now only suports hierarquical multiple numbers
        '''        
        out_no = 1
        core_no = 4
        agg_no = 8
        edge_no = 12
        host_no = 3
        edge_agg_link_no = 2
        agg_core_link_no = 4
        core_out_link_no = 1
        '''
        out_no = 1
        core_no = 1
        agg_no = 2
        edge_no = 4
        host_no = 1
        edge_agg_link_no = 1
        agg_core_link_no = 1
        core_out_link_no = 1

        core_switches = list()
        agg_switches = list()
        edge_switches = list()
        hosts = list()
        outside_hosts = list()
        alllinks = {}
        
        #Out Hosts (hosts that pretend to be the next thing after the gateway)
        for h in range(out_no):
            host_id = 'o%i'% (len(hosts)+len(outside_hosts)+1)
            # Each outside host gets 30%/n of system CPU
            host = self.addHost(host_id,
               cpu=.3/(out_no))
            
            #initialize link record
            alllinks[host_id] = list()
            
            #add host records
            outside_hosts.append(host_id)
                
        #Core Switches
        for s in range(core_no):
            switch_id = 'c%i'%(len(core_switches)+len(agg_switches)+len(edge_switches)+1)
            switch = self.addSwitch(switch_id)
            
            #Add edge switch records
            core_switches.append(switch_id)
            
            #initialize link records
            if not alllinks.has_key(switch_id):
                alllinks[switch_id] = list()
            
            #add link to out
            switch_link_no = 0
            outside_hosts.sort()
            for host_id in outside_hosts :
                if len(alllinks[host_id])<((core_no*core_out_link_no)/out_no):
                    self.addLink(switch_id, host_id)
                    #add link to record
                    alllinks[host_id].append(switch_id)
                    alllinks[switch_id].append(host_id)
                    switch_link_no += 1
                    
                if switch_link_no >= core_out_link_no:
                    break
        
        #Agg Switches
        for s in range(agg_no):
            switch_id = 'a%i'%(len(core_switches)+len(agg_switches)+len(edge_switches)+1)
            switch = self.addSwitch(switch_id)
            
            #Add edge switch records
            agg_switches.append(switch_id)
            
            #initialize link records
            if not alllinks.has_key(switch_id):
                alllinks[switch_id] = list()
            
            #TODO: add link to core
            switch_link_no = 0
            core_switches.sort()
            for core_id in core_switches :
                if len(alllinks[core_id])-core_out_link_no<((agg_no*agg_core_link_no)/core_no):
                    self.addLink(switch_id, core_id)
                    #add link to record
                    alllinks[core_id].append(switch_id)
                    alllinks[switch_id].append(core_id)
                    switch_link_no += 1
                    
                if switch_link_no >= agg_core_link_no:
                    break
        
        #Edge Switches
        for s in range(edge_no):
            switch_id = 'e%i'%(len(core_switches)+len(agg_switches)+len(edge_switches)+1)
            switch = self.addSwitch(switch_id)
            
            #Add edge switch records
            edge_switches.append(switch_id)
            
            #initialize link records
            if not alllinks.has_key(switch_id):
                alllinks[switch_id] = list()
            
            #TODO: add link to agg#TODO: add link to core
            switch_link_no = 0
            agg_switches.sort()
            for agg_id in agg_switches :
                if len(alllinks[agg_id])-agg_core_link_no<((edge_no*edge_agg_link_no)/agg_no):
                    self.addLink(switch_id, agg_id)
                    #add link to record
                    alllinks[agg_id].append(switch_id)
                    alllinks[switch_id].append(agg_id)
                    switch_link_no += 1
                    
                if switch_link_no >= edge_agg_link_no:
                    break
            
            #add hosts and connection to hosts
            for h in range(host_no):
                host_id = 'h%i' % (len(hosts)+len(outside_hosts)+1)
                # Each host gets 50%/n of system CPU
                host = self.addHost(host_id,
                   cpu=.5/(host_no*edge_no))
                
                #add link 100 Mbps, 5ms delay, 10% loss
                #self.addLink(host_id, switch_id, bw=10, delay='5ms', loss=10, max_queue_size=1000, use_htb=True
                self.addLink(host_id, switch_id)
                
                #initialize link records
                if not alllinks.has_key(host_id):
                    alllinks[host_id] = list()
                    
                #add link records
                alllinks[host_id].append(switch_id)
                alllinks[switch_id].append(host_id)
                
                #add host records
                hosts.append(host_id)
        '''        
        for host in hosts:
            h1 = net.getHostByName(host)
            result = h1.cmd('ping -c1 -t500 10.0.0.1')
            print result
        '''

topos = { 'mytopo': ( lambda: MyTopo() ) }
