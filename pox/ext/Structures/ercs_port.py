from pox.core import core

log = core.getLogger()

class Port(object):
    
    def __init__(self, id, mac_address, ip_addresses):
        self.id = id
        self.mac_address = mac_address
        self.ip_addresses = ip_addresses
    
    '''
    Helful functions
    '''
