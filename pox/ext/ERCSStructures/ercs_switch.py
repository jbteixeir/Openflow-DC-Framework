from pox.lib.revent.revent import Event



class Switch(object):
    '''
    connection - connection from event.connection (used to reach the switch,
                     maybe dpid can be used for the same purpose) can be reached also by core.openflow._connection.values()
    dpid - dpid of the switch 
    ports - Dictionary with all the ports of the switch (Port class)
    type - Type of switch ( Unknown(0), Core(1), Aggregation(2), Edge(3))
    '''
    #Switch type static definition
    UNKNOWN = 0
    CORE = 1
    AGGREGATION = 2
    EDGE = 3
    
    def __init__(self, connection ,dpid, ports, switch_type):
        self.connection = connection
        self.dpid = dpid
        self.ports = ports
        self.type = switch_type
        
class SwitchEvent (Event):
    
    def __init__ (self, dpid, connection):
        Event.__init__(self)
        self.dpid = dpid
        self.connection = connection
        
class SwitchJoin(SwitchEvent):
    '''
    Should be raised every time a new Switch is discovered
    '''
    def __init__(self, dpid, connection):
        SwitchEvent.__init__(self, dpid, connection)
        self.dpid = dpid
        self.connection = connection
        
class SwitchTimeout(SwitchEvent):
    '''
    Should be raised every time a new Switch leaves
    Maybe timeout on ports? or Switch time out only when all ports timeout?
    '''
    def __init__(self, dpid, connection):
        SwitchEvent.__init__(self, dpid, connection)
        self.dpid = dpid
        self.connection = connection