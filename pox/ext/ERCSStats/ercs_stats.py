'''
Created on Nov 15, 2012

@author: openflow
'''
from __future__ import division
from pox.lib.revent.revent import EventMixin, Event
from pox.core import core
import pox.openflow.libopenflow_01 as openflowlib
import time
import os
import thread
from ext.ERCSTopology import ercs_topology
from pox.lib.recoco.recoco import Timer

log = core.getLogger()

'''
Events
'''

class PortsStats (Event) :

    def __init__ (self, dpid):
        Event.__init__(self)
        self.dpid = dpid
        
class PortsBitRate (PortsStats) :
    
    '''
    bit_rate - Dictionary indexed by port_id that indicates the current bit_rate
    '''
    
    def __init__ (self, dpid, bit_rate_by_port):
        PortsStats.__init__(self, dpid)
        self.bit_rate = bit_rate_by_port

class Stats(EventMixin):
    
    '''
    switch_port_stats_history - Dict of port statistics indexed by dpid
        -list
            tuple(time, bit_rate) // to access do switch_port_stats_history[0][0] for time or switch_port_stats_history[0][1] for bit_rate 
                -time - time which the statistics where collected (precision - Microseconds)
                -bit_rate (in mbps)- Dict of bit_rate indexed by port
                -... (more if needed)
            
    port_requests - Dict of PortRequests indexed by dpid
        
    port_results - dict of PortResult indexed by dpid
        
    _eventMixin_events - Set of Events
        -SwitchStats - Stats about all ports?
        -PortStats - Stats about a specific port of a Switch?
            -PortStatsBitRate
            -... (more if needed)
    
    polling_time - polling time for statistics requests
    
    historical_ponderation - Ponderation factor to take into consideration when returning the statistical values
          
    '''
    POLLINGTIMEDEFAULT = 120
    HISTORICALPONDERATIONDEFAULT = 0.25
    
    _eventMixin_events = set([
         PortsBitRate,
         ])
    
    class PortResult():
        '''
        -stat_entries - list of stat events
        -time_entries - list of time entries 
        '''
        def __init__(self, stat_entries, time_entries):
            self.stat_entries = stat_entries
            self.time_entries = time_entries
    
    class PortRequest():
        '''
        -ports - list of port numbers
        -request_type - type of request (bitrate, ...)
            #1 - bit rate
            #2 - ... (more if needed)
        '''
        BIT_RATE = 1
        
        def __init__(self, ports, request_type):
            self.ports = ports
            self.request_type = request_type
    
    def __init__(self, inithandler = None):
        #Listen to Openflow events (stats events are the ones we want)
        core.openflow.addListeners(self)
        
        self.switch_port_stats_history = {}
        self.port_requests = {}
        self.port_results = {}
        
        if inithandler == None :
            self.askForArgs()
        else :
            self.getArgsFromIni(inithandler)
            
        #request statistics
        self.requestBitRateForAllSwitches()
        #start periodical statistics collection
        thread.start_new_thread(self.requestPeriodicalStats, ())
    
    def requestPeriodicalStats(self):
        while(1) :
            log.debug("Requesting Periodical Stats...")
            self.requestBitRateForAllSwitches()
            log.debug("Requesting Periodical Stats... DONE")
            #log.info(self.switch_port_stats_history)
            time.sleep(self.polling_time)

    
    def askForArgs(self):
        #TODO: Ask if statistics are requested periodically (in this case ask polling time) or as needed.
        #add a flag for this
        self.polling_time = raw_input("Insert polling time (sec) for periodical stats collection (0 for non periodical): ")
        if self.polling_time == "" :
            self.polling_time = self.POLLINGTIMEDEFAULT
            log.info("Polling Time set to default - %s seconds", self.POLLINGTIMEDEFAULT)
        while not ercs_topology.is_number(self.polling_time):
            self.polling_time = raw_input("This is not a valid number, please insert a valid value: ")
        
        self.polling_time = float(self.polling_time)
        
        #if periodical requests
        if self.polling_time != 0:
            #ask if previous statistical data should be taken into consideration when calcutating the new stats
            #only makes sense
            self.historical_ponderation = raw_input("Insert historical stats weight factor (between 0 and 1): ")
            if self.historical_ponderation == "" :
                self.historical_ponderation = self.HISTORICALPONDERATIONDEFAULT
                log.info("Historical Ponderation set to default - %s ", self.HISTORICALPONDERATIONDEFAULT)
            while (not ercs_topology.is_number(self.historical_ponderation)):
                if (float(self.historical_ponderation) > 1) or (float(self.historical_ponderation) < 0):
                    self.historical_ponderation = raw_input("This is not a valid number, please insert a valid value: ")
            
            self.historical_ponderation = float(self.historical_ponderation)
            
        else :
            #In case of non periodical stats, don't take into consideration previous data 
            self.historical_ponderation = 0
    
    def getArgsFromIni(self, inithandler):
        '''
        Get values from the ini file
        '''
        try :
            section = "stats"
            key = "polling_time"
            self.polling_time = float(inithandler.read_ini_value(section, key))
            key = "hist_weight"
            self.historical_ponderation = float(inithandler.read_ini_value(section, key))
        except Exception:
            log.error("INI File doesn't contain expected values")
            os._exit(0)

    def getBitRateByDpid(self, dpid):
        '''
        Help getting statistical data from the all the data
        Return a dictionary with bit rate indexed by port_no belonging to a switch dpid
        '''
        log.debug("Getting bitrate stats...")
        bit_rate_port_stats = {}
        
        if len(self.switch_port_stats_history) == 0 :
            self.requestBitRateForAllSwitches()
            
        while not self.switch_port_stats_history.has_key(dpid) :
            log.debug("DPID = %s - Waiting for stats for this switch", dpid)
            log.debug("#switches = %s - number of switches with stats", len(self.switch_port_stats_history))
            time.sleep(1)
        
        log.debug("#Ports %s - # of ports to check Bitrate", len(self.switch_port_stats_history[dpid][0][1]))
        
        for port_no in self.switch_port_stats_history[dpid][0][1].keys():
            #get the last bit_rate stats
            newest_bit_rate = self.switch_port_stats_history[dpid][len(self.switch_port_stats_history[dpid])-1][1][port_no]

            #get the sum of all bit rate stats except for the last
            bit_rate_sum = 0
            for (time_stamp, bit_rate) in self.switch_port_stats_history[dpid] :
                bit_rate_sum += bit_rate[port_no]

            temp_hist_bit_rate = bit_rate_sum - newest_bit_rate

            if (len (self.switch_port_stats_history[dpid])-1) != 0:
                temp_hist_bit_rate = temp_hist_bit_rate / (len (self.switch_port_stats_history[dpid])-1)
                 
            bit_rate_port_stats[port_no] = (self.historical_ponderation * temp_hist_bit_rate) + ((1-self.historical_ponderation)* newest_bit_rate)
        
        log.debug("#ports = %s - Returning Bitrate stats indexed by port", len(bit_rate_port_stats))
        
        return bit_rate_port_stats
        
    
    def requestBitRateForAllSwitches(self):
        for connection in core.openflow._connections.values():
            self.requestPortStats(connection, [], Stats.PortRequest.BIT_RATE)
    
    def requestPortStats(self, connection, ports, request_type):
        '''
        Requests stats for all the port numbers in ports for the specified connection (switch)
        Stats are returned throught a event. They can also be consulted in the switch_port_stats_history
        '''
        
        log.debug("DPID = %s, Request Type = %s - New Port Request Arrived", connection.dpid, request_type)
        
        #setup the request
        self.port_requests[connection.dpid] = self.PortRequest(ports, request_type)
        #Check if Port stats have been requested, and still being processed
        # if self.port_results.has_key(connection.dpid) :
        #     log.warning("DPID = %s - Statistics Already Requested (wait for result and request again)", connection.dpid)
        #     return
            
        #send request
        request_time = self.sendPortStatsRequest(connection)
        
        #initialize the result variables
        if not self.port_results.has_key(connection.dpid) :
            self.port_results[connection.dpid] = self.PortResult(list(),list())
        
        #record the time in which the request was made
        self.port_results[connection.dpid].time_entries.append(request_time)
        
    def sendPortStatsRequest(self, connection):
        '''
        Request Port Statistics to switch
        Return time which the request taked place
        '''
        # Request port stats from the switch corresponding to this connection
        connection.send(openflowlib.ofp_stats_request(body=openflowlib.ofp_port_stats_request()))
        request_time = time.time()
        log.debug("DPID = %s - Statistics Requested to Switch", connection.dpid)
        
        return request_time
    
    
    def _handle_PortStatsReceived (self, event):
        '''
        Handle Port Statistics
        '''
        
        #Check if there's any request corresponding to this stats
        if self.port_requests.has_key(event.connection.dpid) :
            #check request_type
            log.debug("DPID = %s, Request Type = %s - Received Stats", event.connection.dpid, self.port_requests[event.connection.dpid].request_type)
            if self.port_requests[event.connection.dpid].request_type == 1:
                #handle this type of request
                self.handleBitRatePortStats(event)
        else :
            log.warning("DPID = %s - No request matches this stats", event.connection.dpid)
        

    '''
    Specific statistics handlers 
    '''
            
    def handleBitRatePortStats(self, event) :
        '''
        Handle the Port Statistics related to BitRate
        -Two requests must be made to calculate the Bit Rate
        
        Note: To know the switch this event belongs to -> event.connection.dpid
        '''
        log.debug("DPID = %s - Bit Rate Port Stats Received", event.connection.dpid)
        
        #if there's no results yet
        if len(self.port_results[event.connection.dpid].stat_entries) == 0:
            log.debug("DPID = %s - Received 1/2 Port Stats Results (Bit Rate)", event.connection.dpid)
            if not self.port_results.has_key(event.connection.dpid) :
                #Initialize port_results
                self.port_results[event.connection.dpid] = self.PortResult(list(), list())
            #Save results
            self.port_results[event.connection.dpid].stat_entries.append(event.stats)
            
            #send request
            request_time = self.sendPortStatsRequest(event.connection)
        
            self.port_results[event.connection.dpid].time_entries.append(request_time)
            
        #if this is the reply to the second stats request
        # elif len(self.port_results[event.connection.dpid].stat_entries) >= 1 :
        else:
            log.debug("DPID = %s - Received 2/2 Port Stats Results (Bit Rate)", event.connection.dpid)
            
            #Save results
            self.port_results[event.connection.dpid].stat_entries.append(event.stats)
            
            #Get the time elapsed between the two stats request (in microseconds
            time_elapsed = self.port_results[event.connection.dpid].time_entries[len(self.port_results[event.connection.dpid].time_entries)-1] - self.port_results[event.connection.dpid].time_entries[len(self.port_results[event.connection.dpid].time_entries)-2]
            log.debug("Time Elapsed = %s - Time between stats requests", time_elapsed)

            #initialize temporary dictionary
            bit_rate_by_port = {}
            #Calculate the bit_rate for all the ports
            for s1 in self.port_results[event.connection.dpid].stat_entries[len(self.port_results[event.connection.dpid].stat_entries)-2]:
                for s2 in self.port_results[event.connection.dpid].stat_entries[len(self.port_results[event.connection.dpid].stat_entries)-1]:
                    if s1.port_no == s2.port_no :
                        #should we watch to see if counters are full and restart?
                        bytes_count = (s2.tx_bytes + s2.rx_bytes) - (s1.tx_bytes + s1.rx_bytes)
                        log.debug("(%s+%s)-(%s+%s) = %s", s2.tx_bytes, s2.rx_bytes, s1.tx_bytes,s1.rx_bytes, bytes_count)
                        #obtain the bit_rate for this port in mbps
                        bit_rate = ((bytes_count*8)/(time_elapsed))/1000000
                        log.debug("DPID = %s, Port = %s, Time Elapsed = %s s, Bit Rate = %s mbps - Bit rate Calculated", 
                                  event.connection.dpid, s1.port_no, time_elapsed, bit_rate)
            
                        #save the results in a temporary dictionary
                        bit_rate_by_port[s1.port_no] = bit_rate
                         
            #Raise event with the results specifically for the requested ports
            temp_port_stats = {}
            for port in self.port_requests[event.connection.dpid].ports:
                temp_port_stats[port] = bit_rate_by_port[port]
            
            self.raiseEventNoErrors(PortsBitRate(event.connection.dpid, 
                                                 temp_port_stats))

            #Save the results in switch_port_stats_history
            if not self.switch_port_stats_history.has_key(event.connection.dpid) :
                self.switch_port_stats_history[event.connection.dpid] = list()
            
            self.switch_port_stats_history[event.connection.dpid].append((
                self.port_results[event.connection.dpid].time_entries[len(self.port_results[event.connection.dpid].time_entries)-1], bit_rate_by_port))
            #print "HISTORICAL STATS"
            #print self.switch_port_stats_history
            #print "HISTORICAL STATS END"
            
            #Delete the request and the temporary resuls
            #self.port_requests.__delitem__(event.connection.dpid)
            #self.port_results.__delitem__(event.connection.dpid)
