from pox.core import core
from pox.lib.util import dpidToStr

log = core.getLogger()

class MyComponent (object):
    def __init__ (self):
	print "bakjdas"
	core.openflow.addListeners(self)

    def _handle_FlowRemoved (self, event):
	log.debug("flow removed")

def launch ():
    print "pppppp"
    mc = MyComponent()
    core.registerNew(MyComponent)
