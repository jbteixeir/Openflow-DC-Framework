from pox.core import core
from pox.lib.recoco.recoco import Timer
import thread

log = core.getLogger()

class MigrationManager(object):

	def __init__(self):
		#Start Migration detection in case where we want if the vm distribuition is according to the
		#allocation policy - Keep the policy in the DC
		Timer(10, self.check_vm_distribution, recurring=True)

	'''
	When to migrate
	'''
	def check_vm_distribuition(self, min_change_ratio):
		"""
		Checks all the vms in the DC to see if they are according to the defined allocation policy.
		If not, an event is raised
		TODO: specify the event
		@param min_change_ratio Mininum ratio of vms that should migrate, in order to start the process of reorganizing the vms in the DC
		"""
		#For each vm
			#subtract the requirements (for the server and switches) in which it is
			#add the requirements (for the server and switches)for the previous analysed vm's 
			#that would change place

			#run the policy algorithm
			#if the vm changes place
				#save this information (vm_id, host_id and switches choosen)

		#If more than x% of vm's change place then migrate them
		#(or migrate just enough vm to get the desired percentage)

		#already got the which and where, so calculate the path and start the migration
		#POSSIBLE ISSUE: allocations have already taken place, and the previous calculated which 
		#and where no longer apply
		pass

	def check_network_hotspot(self, max_link_ratio, max_switch_ratio):
		"""
		Checks the switch/link ratio and sets and even for migration in case it is higher than a threshold
		TODO: Checks the switch/link ratio proactively
		@param max_link_ratio Maximum link ratio allowed before raising an migration event
		@param max_switch_ratio Maximum switch ratio allowed before raising an migration event
		"""
		#for each switch
			#for each link
				#check the collected statistics and see if it link ratio higher that the max_link_ratio

			#check the collected statistics and see if it switch ratio is higher that the max_link_ratio

		#How to choose which to move?
		#Move the vm which is causing the overload (need hypervisor stats for this)
		#will this bring QoE problems?
		pass

	def check_server_hotspot(self):
		"""
		Depends on the hypervisor and the stats it's able to return (for sure it can return stats per server)
		TODO: Should exist a super class for the hypervisor and then subclasses which specify the 
		interaction to provide the stats per server and per vm.
		"""
		pass

	'''
	Which vms to migrate
	'''

	'''
	Where to move
	'''

	'''
	Which path to do the migration
	'''
	def get_migration_path(self, orig_server, dst_server):
		pass

	'''
	Start the migration
	'''