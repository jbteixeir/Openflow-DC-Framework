from pox.core import core
from pox.openflow.discovery import LinkEvent
from pox.lib.revent import *
from pox.host_tracker.host_tracker import host_tracker

class EventExperiments (object) :

	def __init__ (self):
		#core.topology.addListeners(self)
		core.openflow_discovery.addListeners(self)
		#host_tracker()

	def _handle_LinkEvent(self, event):
		print "linked changed"

	def _handle_SwitchJoin(self, event):
		print "new switch"

	def _handle_HostJoin(self, event):
		print "new host"

def launch() :

	ee = EventExperiments()
