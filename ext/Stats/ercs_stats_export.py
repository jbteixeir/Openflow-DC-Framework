from pox.core import core
from pox.lib.recoco.recoco import Timer
from ext.Structures.ercs_switch import Switch
import os
import thread
import time

log = core.getLogger()

class ERCSStatsExport(object):
    '''
    Class that saves the statistics about switches and links into files
    '''

    def __init__(self, inithandler = None, topology = None, stats = None, vm_allocation_manager = None):
        
        self.topology = topology
        self.stats = stats
        self.vm_allocation_manager = vm_allocation_manager
        
        self.coredpid = list()
        self.aggdpid = list()
        self.edgedpid = list()
        
        self.corelinks = list()
        self.agglinks = list()
        self.edgelinks = list()
        
        
        self.polling_time = 60
        
        if (inithandler == None) :
            self.switch_stats_dir = "."
            self.link_stats_dir = "."
        else :
            self.getArgsFromIni(inithandler)
        
        if not os.path.exists(self.switch_stats_dir):
            os.makedirs(self.switch_stats_dir)
        if not os.path.exists(self.link_stats_dir):
            os.makedirs(self.link_stats_dir)
        if not os.path.exists(self.host_stats_dir):
            os.makedirs(self.host_stats_dir)
            
        self.core_stats_file = file((self.switch_stats_dir+"/corestats.csv"), "w+")
        self.agg_stats_file = file((self.switch_stats_dir+"/aggstats.csv"), "w+")
        self.edge_stats_file = file((self.switch_stats_dir+"/edgestats.csv"), "w+") 
    
        self.core_links_stats_file = file((self.link_stats_dir+"/corelinkstats.csv"), "w+")
        self.agg_links_stats_file = file((self.link_stats_dir+"/agglinkstats.csv"), "w+")
        self.edge_links_stats_file = file((self.link_stats_dir+"/edgelinkstats.csv"), "w+")

        self.host_stats_file = file((self.host_stats_dir+"/hoststats.csv"), "w+")
        
        thread.start_new_thread(self.export_stats, ())
        
    def getArgsFromIni(self, inithandler):
        try :
            section = "statsexport"
            key = "switchsratiodir"
            self.switch_stats_dir = str(inithandler.read_ini_value(section, key))
            
            key = "linksratiodir"
            self.link_stats_dir = str(inithandler.read_ini_value(section, key))

            key = "hostvmallocationdir"
            self.host_stats_dir = str(inithandler.read_ini_value(section, key))
            
            section = "stats"
            key = "polling_time"
            self.polling_time = float(inithandler.read_ini_value(section, key))
            
            log.debug("Successfully got stats export values")
            
        except Exception, e :
            log.error("INI File doesn't contain expected values")
            print e
            os._exit(0)
            
    def export_stats(self):
        #write file header
        self.writeSwitchFileHeaders()
        self.writeLinkFileHeaders()
        self.writeHostFileHeaders()
        
        
        #write stats on files
        time.sleep(self.polling_time)
        #Start Thread that writes the stats into the files
        thread.start_new_thread(self.export_stats_switches, ())
        thread.start_new_thread(self.export_stats_links, ())
        thread.start_new_thread(self.export_stats_hosts, ())
        
    def writeSwitchFileHeaders(self):
        not_ok = True;
        while not_ok :
            time.sleep(5)
            not_ok = False
            for dpid in self.topology.switches.keys():
                if self.topology.switches[dpid].type == Switch.UNKNOWN:
                    not_ok = True;
            if len(self.topology.switches) == 0:
                not_ok = True;
        
        log.debug("Writing to Switch Stats file header...")
        switch_list = self.topology.switches.keys()
        switch_list.sort()
        for dpid in switch_list:
            if(self.topology.switches[dpid].type == Switch.CORE):
                self.coredpid.append(dpid)
                self.core_stats_file.write(str(dpid)+";")
            if(self.topology.switches[dpid].type == Switch.AGGREGATION):
                self.aggdpid.append(dpid)
                self.agg_stats_file.write(str(dpid)+";")
            if(self.topology.switches[dpid].type == Switch.EDGE):
                self.edgedpid.append(dpid)
                self.edge_stats_file.write(str(dpid)+";")
                
        self.core_stats_file.write("\n")
        self.agg_stats_file.write("\n")
        self.edge_stats_file.write("\n")
        log.debug("Writing to Switch Stats file header... DONE")
        
    def writeLinkFileHeaders(self):
        log.debug("Writing to Link Stats file header...")
        for dpid in self.coredpid:
            for port_id in self.topology.switches[dpid].ports:
                #if this port connects to a non of switch
                if not self.topology.switch_links.has_key(dpid) or (self.topology.switch_links.has_key(dpid) and 
                                                                    not self.topology.switch_links[dpid].has_key(port_id)):
                    pass
                else:
                    dst_dpid = self.topology.switch_links[dpid][port_id][0]
                    dst_port = self.topology.switch_links[dpid][port_id][1]
                    self.core_links_stats_file.write(str(dpid)+"."+str(port_id)+"<->"+str(dst_dpid)+"."+str(dst_port)+";")
                    self.corelinks.append((dpid,port_id, dst_dpid, dst_port))
                    
        self.core_links_stats_file.write("\n")
        
        for dpid in self.aggdpid:
            for port_id in self.topology.switches[dpid].ports:
                if self.topology.switch_links.has_key(dpid) :
                    if self.topology.switch_links[dpid].has_key(port_id) :
                        dst_dpid = self.topology.switch_links[dpid][port_id][0]
                        dst_port = self.topology.switch_links[dpid][port_id][1]
                        if self.topology.switches[dst_dpid].type == Switch.EDGE:
                            self.agg_links_stats_file.write(str(dpid)+"."+str(port_id)+"<->"+str(dst_dpid)+"."+str(dst_port)+";")
                            self.agglinks.append((dpid, port_id, dst_dpid, dst_port))
                            
        self.agg_links_stats_file.write("\n")
                            
        for dpid in self.edgedpid:
            for port_id in self.topology.switches[dpid].ports:
                #if this port connects to a non of switch
                if not self.topology.switch_links.has_key(dpid) or (self.topology.switch_links.has_key(dpid) and 
                                                                    not self.topology.switch_links[dpid].has_key(port_id)):
                    self.edge_links_stats_file.write(str(dpid)+"."+str(port_id)+";")
                    self.edgelinks.append((dpid,port_id))
                    
        self.edge_links_stats_file.write("\n")
        
        log.debug("Writing to Link Stats file header... DONE")
        
    def writeHostFileHeaders(self):
        log.debug("Writing to Host Stats file header...")
        for host in self.topology.hosts:
            self.host_stats_file.write(str(host)+";")

        self.host_stats_file.write("\n")
        log.debug("Writing to Host Stats file header... DONE")

    def export_stats_switches(self):
        while (1):
            for dpid in self.coredpid:
                ratio = self.vm_allocation_manager.getSwitchRatio(dpid)
                self.core_stats_file.write(str(ratio)+";")
                print self.stats.getBitRateByDpid(dpid)
            self.core_stats_file.write("\n")
            for dpid in self.aggdpid:
                ratio = self.vm_allocation_manager.getSwitchRatio(dpid)
                self.agg_stats_file.write(str(ratio)+";")
            self.agg_stats_file.write("\n")
            for dpid in self.edgedpid:
                ratio = self.vm_allocation_manager.getSwitchRatio(dpid)
                self.edge_stats_file.write(str(ratio)+";")
            self.edge_stats_file.write("\n")
            time.sleep(self.polling_time)
    
    def export_stats_links(self):
        while(1):
            for (dpid,port_id, dst_dpid, dst_port) in self.corelinks :
                ratio = self.vm_allocation_manager.getLinkRatio(dpid,port_id)
                self.core_links_stats_file.write(str(ratio)+";")
            self.core_links_stats_file.write("\n")
            
            for (dpid,port_id, dst_dpid, dst_port) in self.agglinks :
                ratio = self.vm_allocation_manager.getLinkRatio(dpid,port_id)
                self.agg_links_stats_file.write(str(ratio)+";")
            self.agg_links_stats_file.write("\n")
            
            for (dpid,port_id) in self.edgelinks :
                ratio = self.vm_allocation_manager.getLinkRatio(dpid,port_id)
                self.edge_links_stats_file.write(str(ratio)+";")
            self.edge_links_stats_file.write("\n")
            
            time.sleep(self.polling_time)

    def export_stats_hosts(self):
        while(1):

            for host in self.topology.hosts:
                if self.vm_allocation_manager.vms_allocated.has_key(host):
                    self.host_stats_file.write(str(len(self.vm_allocation_manager.vms_allocated[host]))+";")
                else:
                    self.host_stats_file.write(str(0)+";")

            self.host_stats_file.write("\n")

            time.sleep(self.polling_time)