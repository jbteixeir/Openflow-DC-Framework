from pox.core import core

log = core.getLogger()

class XenCommunicator(object):
	'''
	Connects with Xen Hypervisor of each host through ssh 

	REQUIREMENT: Previously configured Xen on each host
	To serve the most various configurations allows to use xen-live-cd ready to use vm's,
	or create new vm's.
	'''

	def __init__(self, inithandler=None):
		#User and pass should be moved to th host class. 
		#This info might be diferent for each host, altought it would be a pain to configure them all,
		#so for now we assume is the same for all of them

		if inithandler == None :
            #self.askForArgs()
            #Not yet implemented
			pass
		else :
			self.getArgsFromIni(inithandler)

	def getArgsFromIni(self, inithandler):
		
		try :
			section = "credencials"
			key = "username"
			self.username = inithandler.read_ini_value(section, key)
			key = "password"
			self.password = inithandler.read_ini_value(section, key)

			log.debug("Successfully got host credencials")
		except Exception, e :
			print e
			log.error("INI File doesn't contain expected values")
			os._exit(0)

	def createVM(self, host_ip, vm_details, host_port = None):

		'''
		vm_detail = (cpu, ram, disk)
		'''

		if host_port == None:
			host_port = 22

		livecd = True
		#please create your own method for retrieving different vm host names, according to your
		#naming policy
		vm_host_name = "new_vm"

		#In case of LiveCD
		if livecd :
			#Create the vm configuration file
			#This informatino should be later moved to the host class
			script = "mkdir /home/" + username + "/VMConfigFiles; "
			script += "echo " + self.createNewVMConfFile(vm_details) + " > "+conf_filename+"; "

			#create the vm
			script += "xm create -c /home/" + username + "/VMConfigFiles/" + conf_filename +" name=" + vm_host_name + "; "
		#In case of User setup hosts
		else:
			script = self.createNewVMImage(vm_details, vm_host_name)

			script += "create -c /etc/xen/"+vm_host_name+".cfg; "

		#logout
		script += "exit;"

		#send the command
		commands.getstatusoutput ("sshpass -p '"+password+"' ssh "+str(username)+"@"+str(host_ip)+" -p "+str(host_port)+" '"+script)

		
		#return vm_id || vm_ip || at least enought info to remotely acess it?
		#TODO: Return something
		
	
	def removeVM(self, host_ip, vm_id, host_port = None):
		#TODO: Remove a Virtual Machine
		if port == None:
			port = 22

	def createNewVMConfFile(self, vm_details):
		conf_file = """kernel = '/boot/vmlinuz-2.6.16-xen'
					ramdisk = '/boot/vmlinuz-2.6.16-xen.img'
					disk = ['cow:/mnt/cdrom/rootfs.img "+vm_details[2]+",sda1,w']
					root = '/dev/sda ro'
					extra = 'ramdisk_size=32758 selinux=0 quiet'
					memory = "+ vm_details[1]
					vif = ['']"""
		return conf_file

	def createNewVMImage(self, vm_details, vm_host_name):
		'''
		creates a new virtual machine image
		'''
		#TODO: still missing disk space

		command = "xen-create-image --hostname="+vm_host_name+"   --memory="+vm_details[1]+"mb   --vcpus="+vm_details[0]+"   --lvm=vg0   --dhcp   --pygrub   --dist=squeeze"

		return command
