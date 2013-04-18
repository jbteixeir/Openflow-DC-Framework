
from pox.openflow.discovery import Discovery

#Timeout for an event to be raised since last topology change
TIMEOUT_NOTIFY = 6

class DiscoveryNotifier(Discovery):
    
    def __init__(self):
        Discovery.__init__(self)
        
    def _expireLinks (self):
        '''
        Called periodially by a timer to expire links that haven't been
        refreshed recently.
        '''
        super().curtime = super().time.time()
    
        deleteme = []
        for link,timestamp in self.adjacency.iteritems():
          if super().curtime - timestamp > super().LINK_TIMEOUT:
            deleteme.append(link)
            super().log.info('link timeout: %s.%i -> %s.%i' %
                     (super().dpidToStr(link.dpid1), link.port1,
                      super().dpidToStr(link.dpid2), link.port2))
    
        if deleteme:
          super().self._deleteLinks(deleteme)