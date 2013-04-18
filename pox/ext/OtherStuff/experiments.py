"""
This module is for experimental purpose only.
I'm not responsible for any damaged caused by it. Just saying...
Now, get back to work!
"""

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.recoco import Timer
import flow_stats as fs

# include as part of the betta branch
from pox.openflow.of_json import *

log = core.getLogger()

#RULE_IDLETIMEOUT = 2
RULE_HARDTIMEOUT = 10

class Experiments (object):
    """
    A Tutorial object is created for each switch that connects.
    A Connection object for that switch is passed to the __init__ function.
    """
    def __init__ (self, connection):
        
        # Keep track of the connection to the switch so that we can
        # send it messages!
        self.connection = connection

        # This binds our PacketIn event listener
        connection.addListeners(self)
        
        self.connections = {}
        # Use this table to keep track of which ethernet address is on
        # which switch port (keys are MACs, values are ports).
        self.mac_to_port = {}
        
    def _handle_ConnectionUp (self, event):
        self.connections[event.connection.dpid] = event.connection
        log.debug("New Switch Connected | DPID = %s", event.connection.dpid)

    def send_packet (self, buffer_id, raw_data, out_port, in_port):
        """
        Sends a packet out of the specified switch port.
        If buffer_id is a valid buffer on the switch, use that.    Otherwise,
        send the raw data in raw_data.
        The "in_port" is the port number that packet arrived on.    Use
        OFPP_NONE if you're generating this packet.
        """
        msg = of.ofp_packet_out()
        msg.in_port = in_port
        if buffer_id != -1 and buffer_id is not None:
            # We got a buffer ID from the switch; use that
            msg.buffer_id = buffer_id
        else:
            # No buffer ID from switch -- we got the raw data
            if raw_data is None:
                # No raw_data specified -- nothing to send!
                return
            msg.data = raw_data

        # Add an action to send to the specified port
        action = of.ofp_action_output(port = out_port)
        msg.actions.append(action)

        # Send message to switch
        self.connection.send(msg)


    def act_like_hub (self, packet, packet_in):
        """
        Implement hub-like behavior -- send all packets to all ports besides
        the input port.
        """

        # We want to output to all ports -- we do that using the special
        # OFPP_FLOOD port as the output port.    (We could have also used
        # OFPP_ALL.)
        self.send_packet(packet_in.buffer_id, packet_in.data,
                                         of.OFPP_FLOOD, packet_in.in_port)

        # Note that if we didn't get a valid buffer_id, a slightly better
        # implementation would check that we got the full data before
        # sending it (len(packet_in.data) should be == packet_in.total_len)).


    def act_like_switch (self, packet, packet_in):
        """
        Implement switch-like behavior.
        """

        # Here's some psuedocode to start you off implementing a learning
        # switch.    You'll need to rewrite it as real Python code.

        # Learn the port for the source MAC
        if not self.mac_to_port.has_key(self.connection.dpid):
            log.debug("New switch added to the dictionary = %s", self.connection.dpid)
            self.mac_to_port[self.connection.dpid] = {}
            
        #update or create new port association with the mac        
        self.mac_to_port[self.connection.dpid][packet.src] = packet_in.in_port
        log.debug("DPID = %s MacAddr = %s -- Port = %s", self.connection.dpid, packet.src, packet_in.in_port)
               

        if self.mac_to_port[self.connection.dpid].has_key(packet.dst):
            
            # Send packet out the associated port
            """ DELETE (1) this line (and the below) if you want to send the packet instead of installing a flow rule
            self.send_packet(packet_in.buffer_id, packet_in.data,
                                             self.mac_to_port[self.connection.dpid][packet.dst],
                                             packet_in.in_port)
            DELETE (1)"""
            # Once you have the above working, try pushing a flow entry
            # instead of resending the packet (comment out the above and
            # uncomment and complete the below.)

            log.debug("Installing flow\n DPID = %s\n DST = %s\n PORT= %s\n ",self.connection.dpid,
                    packet.dst,self.mac_to_port[self.connection.dpid][packet.dst])
            
            
            # Maybe the log statement should have source/destination/port?
            msg = of.ofp_flow_mod()
            
            # Set fields to match received packet
            #msg.match = of.ofp_match.from_packet(packet)
            msg.match.dl_dst = packet.dst
            
            #set the action (output port)
            msg.actions.append(of.ofp_action_output(port = self.mac_to_port[self.connection.dpid][packet.dst]))
            
            #Set other fields of flow_mod (timeouts? buffer_id?)
            msg.hard_timeout = RULE_HARDTIMEOUT
            #msg.command = of.OFPFC_ADD
            msg.buffer_id = packet_in.buffer_id
            
            #Add an output action, and send -- similar to send_packet()
            self.connection.send(msg)
            
        else:
            log.debug("Packet flooded")
            # Flood the packet out everything but the input port
            # This part looks familiar, right?
            self.send_packet(packet_in.buffer_id, packet_in.data,
                                             of.OFPP_FLOOD, packet_in.in_port)


    def _handle_PacketIn (self, event):
        """
        Handles packet in messages from the switch.
        """

        packet = event.parsed # This is the parsed packet data.
        if not packet.parsed:
            log.warning("Ignoring incomplete packet")
            return

        packet_in = event.ofp # The actual ofp_packet_in message.

        # Comment out the following line and uncomment the one after
        # when starting the exercise.
        #self.act_like_hub(packet, packet_in)
        self.act_like_switch(packet, packet_in)

#Statistics
# When we get port stats, print stuff out
def _handle_port_stats (event):

    log.debug("Statistics Reply")
    for f in event.stats:
        log.debug("Sent Packets = %s | Received Packet = %s ",f.tx_packets,f.rx_packets)
 
#Wasn't working, traded by flowstats one
def _request_port_stats():
    # Now actually request port stats from all switches
    for connection in core.openflow._connections.values():
        connection.send(of.ofp_stats_request(body=of.ofp_flow_stats_request()))
        log.debug("Statistics Requested to DPID = %s", connection.dpid)
'''
def _request_port_stats ():
    for connection in core.openflow._connections.values():
        connection.send(of.ofp_stats_request(body=of.ofp_flow_stats_request()))
        connection.send(of.ofp_stats_request(body=of.ofp_port_stats_request()))
    log.debug("Sent %i flow/port stats request(s)", len(core.openflow._connections))
'''
def launch ():
    """
    Starts the component
    """
    def start_switch (event):
        log.debug("Controlling %s" % (event.connection,))
        Experiments(event.connection)
        
    core.openflow.addListenerByName("ConnectionUp", start_switch)
    
    '''
    Collect Statistics
    '''
    # Listen for port stats
    core.openflow.addListenerByName("PortStatsReceived", _handle_port_stats)
    Timer(5, _request_port_stats,recurring=True)