
class XenCommunicator(object):
	'''
	Connects with Xen Hypervisor of each host

	hosts - dictionary index by host ip's which gives the tuple (username, password)
		*username - username of the machine with xen
		*password - password
	'''

	def __init(self, username, password, hosts = None):
		#User and pass should be moved to th host class. This info might be diferent for each host,
		#altought it would be a pain to configure them all
		self.username = username
		self.password = password
		self.hosts = hosts

	def createVM(self, host_ip, vm_details, host_port = None):

		'''
		vm_detail = (cpu, ram, disk)
		'''

		if host_port = None:
			host_port = 22

		username = self.hosts[host_ip][0]
		password = self.hosts[host_ip][1]

		#Create the vm configuration file
		#This informatino should be later moved to the host class

		script = "mkdir /home/" + username + "/VMConfigFiles;"
		script += "echo " + self.createNewVMConfFile(vm_details) + " > "+conf_filename+";"

		#create the vm
		script += "xm create -c /home/" + username + "/VMConfigFiles/" + conf_filename + " name=" + vm_name + ";"

		#logout
		script += "exit;"

		#send the command
		commands.getstatusoutput ("sshpass -p '"+password+"' ssh "+str(username)+"@"+
			str(host_ip)+" -p "+str(host_port)+" '"+script+"")

		'''
		#return vm_id & vm_ip || at least enought info to acess it?
		'''
	
	def removeVM(self, host_ip, host_port = None, vm_id):
		if port = None:
			port = 22

	def createNewVMConfFile(self, vm_details):
		conf_file = "kernel = '/boot/vmlinuz-2.6.16-xen'" +
					"ramdisk = '/boot/vmlinuz-2.6.16-xen.img'" +
					"disk = ['cow:/mnt/cdrom/rootfs.img 30,sda1,w']" +
					"root = '/dev/sda ro'" +
					"extra = 'ramdisk_size=32758 selinux=0 quiet'" +
					"memory = 96" +
					"vif = ['']"
		return conf_file
