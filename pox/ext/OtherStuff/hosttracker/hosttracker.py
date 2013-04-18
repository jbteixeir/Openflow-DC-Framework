from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.revent.revent import *

from pox.host_tracker import *
from pox.topology import HostJoin, HostLeave
from pox.openflow.discovery import *

from pox.lib.packet.ethernet import ethernet
from pox.lib.packet.ipv4 import ipv4
from pox.lib.packet.arp import arp

from pox.lib.recoco.recoco import Timer

log = core.getLogger()

class HostTracker (EventMixin, host_tracker):
    
    _eventMixin_events = set([
                              HostJoin,
                              HostLeave,
                              ])

    
    def __init__(self) :
        super.__init__()
        EventMixin.__init__(self)
        
        
    def _handle_PacketIn (self, event):
        """
        @Overide
        Populate MAC and IP tables based on incoming packets.
        Handles only packets from ports identified as not switch-only.
        If a MAC was not seen before, insert it in the MAC table;
        otherwise, update table and enry.
        If packet has a source IP, update that info for the macEntry (may require
        removing the info from antoher entry previously with that IP address).
        It does not forward any packets, just extract info from them.
        """
        dpid = event.connection.dpid
        inport = event.port
        packet = event.parse()
        if not packet.parsed:
            log.warning("%i %i ignoring unparsed packet", dpid, inport)
            return
    
        if packet.type == ethernet.LLDP_TYPE:    # Ignore LLDP packets
            return
        # This should use Topology later 
        if core.openflow_discovery.isSwitchOnlyPort(dpid, inport):
            # No host should be right behind a switch-only port
            log.debug("%i %i ignoring packetIn at switch-only port", dpid, inport)
            return
    
        log.debug("PacketIn: %i %i ETH %s => %s", dpid, inport, str(packet.src), str(packet.dst))
    
        # Learn or update dpid/port/MAC info
        macEntry = self.getMacEntry(packet.src)
        if macEntry == None:
            # there is no known host by that MAC
            # should we raise a NewHostFound event (at the end)?
            macEntry = MacEntry(dpid,inport,packet.src)
            self.entryByMAC[packet.src] = macEntry
            log.info("Learned %s", str(macEntry))
        elif macEntry != (dpid, inport, packet.src):    
            # there is already an entry of host with that MAC, but host has moved
            # should we raise a HostMoved event (at the end)?
            log.info("Learned %s moved to %i %i", str(macEntry), dpid, inport)
            # if there has not been long since heard from it...
            if time.time() - macEntry.lastTimeSeen < timeoutSec['entryMove']:
                log.warning("Possible duplicate: %s at time %i, now (%i %i), time %i",
                            str(macEntry), macEntry.lastTimeSeen(),
                            dpid, inport, time.time())
            # should we create a whole new entry, or keep the previous host info?
            # for now, we keep it: IP info, answers pings, etc.
            macEntry.dpid = dpid
            macEntry.inport = inport
    
        macEntry.refresh()
    
        (pckt_srcip, hasARP) = self.getSrcIPandARP(packet.next)
        if pckt_srcip != None:
            self.updateIPInfo(pckt_srcip,macEntry,hasARP)
                    
        return
                