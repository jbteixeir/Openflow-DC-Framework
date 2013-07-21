#!/usr/bin/python

"""
Simple example of setting network and CPU parameters

NOTE: link params limit BW, add latency, and loss.
There is a high chance that pings WILL fail and that
iperf will hang indefinitely if the TCP handshake fails
to complete.
"""

from mininet.cli import CLI
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.util import dumpNodeConnections, quietRun
from mininet.log import setLogLevel, info
from mininet.node import RemoteController

from time import sleep
from INIHandler import IniHandler

import cPickle as pickle
import os, socket, thread, ipaddr

class SingleSwitchTopo(Topo):
    "Single switch connected to n self.myhosts."
    def __init__(self, n=2, **opts):
        Topo.__init__(self, **opts)
        switch = self.addSwitch('s1')
        for h in range(n):
            # Each host gets 50%/n of system CPU
            host = self.addHost('h%s' % (h + 1),
                                cpu=.5 / n)
            # 10 Mbps, 5ms delay, 10% loss
            self.addLink(host, switch,
                         bw=10, delay='5ms', loss=10, use_htb=True)

class ERCSTopo( Topo ):
    '''
    Tree and fat tree generator for 3 levels. For mininet 2.0
    Outside host -> "internet"(exit point)
    '''
    
    def __init__(self, **opts):
        "Create custom topo."
        # Initialize topology
        Topo.__init__(self, **opts)

        #, self.core_no, core_out_port_no, self.agg_no, agg_out_port_no, self.edge_no, edge_out_port_no, self.host_no):
        #For now only suports hierarquical multiple numbers
        #self.out_no = 1
        #self.core_no = 1
        #self.agg_no = 2
        #self.edge_no = 4
        #self.host_no = 1
        #self.edge_agg_link_no = 1
        #self.agg_core_link_no = 1
        #self.core_out_link_no = 1
        #self.core_bw = 100
        #self.agg_bw = 10
        #self.edge_bw = 1
        #self.out_bw = 400

        self.core_switches = list()
        self.agg_switches = list()
        self.edge_switches = list()
        self.myhosts = list()
        self.outside_hosts = list()
        self.alllinks = {}
        
        #Queue number per switch port and bandwidth (mbps)
        self.queue_bw={}
        #self.queue_bw[1] = 5
        #self.queue_bw[2] = 5

        self.socket_path = ""
        self.udp_ratio = 0.5
        
        inithandler = IniHandler(str(os.path.dirname(os.path.realpath(__file__)))+"/conf.ini")
        self.getArgsFromIni(inithandler)
        self.generateTopology()


        
    def getArgsFromIni(self, inithandler):
        try :
            section = "TopologySwitches"
            key = "core_no"
            self.core_no = int(inithandler.read_ini_value(section, key))
            key = "agg_no"
            self.agg_no = int(inithandler.read_ini_value(section, key))
            key = "edge_no"
            self.edge_no = int(inithandler.read_ini_value(section, key))
            
            section = "TopologyHosts"
            key = "out_no"
            self.out_no = int(inithandler.read_ini_value(section, key))
            key = "host_no"
            self.host_no = int(inithandler.read_ini_value(section, key))
            key = "host_detectable_time"
            self.host_detectable_timeout = int(inithandler.read_ini_value(section, key))
            
            section = "TopologyLinks"
            key = "edgetoagglinkno"
            self.edge_agg_link_no = int(inithandler.read_ini_value(section, key))
            key = "aggtocorelinkno"
            self.agg_core_link_no = int(inithandler.read_ini_value(section, key))
            key = "coretooutlinkno"
            self.core_out_link_no = int(inithandler.read_ini_value(section, key))
            
            section = "SwitchBandwidth"
            key = "core_bw"
            self.core_bw = float(inithandler.read_ini_value(section, key))
            key = "agg_bw"
            self.agg_bw = float(inithandler.read_ini_value(section, key))
            key = "edge_bw"
            self.edge_bw = float(inithandler.read_ini_value(section, key))
            key = "out_bw"
            self.out_bw = float(inithandler.read_ini_value(section, key))
            
            section = "SwitchQueues"
            key = "queue_no"
            queue_no = int(inithandler.read_ini_value(section, key))
            for queue in range(queue_no):
                key = "queue_bw"+str(queue + 1)
                self.queue_bw[queue + 1] = float(inithandler.read_ini_value(section, key))
            
            section = "Traffic"
            key = "udp_ratio"
            self.udp_ratio = float(inithandler.read_ini_value(section, key))
            key = "iperf_port"
            self.iperf_port = int(inithandler.read_ini_value(section, key))

            section = "Socket"
            key = "socket_path"
            self.socket_path = inithandler.read_ini_value(section, key)

        except Exception, e :
            print("INI File doesn't contain valid values format")
            print e
            os._exit(0)
            
    def generateTopology(self):
        #Out self.myhosts (self.myhosts that pretend to be the next thing after the gateway)
        for h in range(self.out_no):
            host_id = 'o%i'% (len(self.myhosts)+len(self.outside_hosts)+1)
            # Each outside host gets 30%/n of system CPU
            host = self.addHost(host_id)
            #host = self.addHost(host_id, cpu=0.5/((self.host_no*self.edge_no)+(self.out_no)))
            
            #set the ip of the outside host so it doesn't belong to the same subnet as the other hosts
            #TODO:net.getNodeByName(host).setIp("10.10.0."+str(h))

            #initialize link record
            self.alllinks[host_id] = list()
            
            #add host records
            self.outside_hosts.append(host_id)
                
        #Core Switches
        for s in range(self.core_no):
            switch_id = 'c%i'%(len(self.core_switches)+len(self.agg_switches)+len(self.edge_switches)+1)
            switch = self.addSwitch(switch_id)
            
            #Add edge switch records
            self.core_switches.append(switch_id)
            
            #initialize link records
            if not self.alllinks.has_key(switch_id):
                self.alllinks[switch_id] = list()
            
            #add link to out
            switch_link_no = 0
            self.outside_hosts.sort()
            for host_id in self.outside_hosts :
                if len(self.alllinks[host_id])<((self.core_no*self.core_out_link_no)/self.out_no):
                    self.addLink(switch_id, host_id, bw=self.out_bw)
                    #add link to record
                    self.alllinks[host_id].append(switch_id)
                    self.alllinks[switch_id].append(host_id)
                    switch_link_no += 1
                    
                if switch_link_no >= self.core_out_link_no:
                    break
            
            
             
            
        #Agg Switches
        for s in range(self.agg_no):
            switch_id = 'a%i'%(len(self.core_switches)+len(self.agg_switches)+len(self.edge_switches)+1)
            switch = self.addSwitch(switch_id)
            
            #Add edge switch records
            self.agg_switches.append(switch_id)
            
            #initialize link records
            if not self.alllinks.has_key(switch_id):
                self.alllinks[switch_id] = list()
            
            #TODO: add link to core
            switch_link_no = 0
            self.core_switches.sort()
            for core_id in self.core_switches :
                if len(self.alllinks[core_id])-self.core_out_link_no<((self.agg_no*self.agg_core_link_no)/self.core_no):
                    self.addLink(switch_id, core_id, bw = self.core_bw)
                    #add link to record
                    self.alllinks[core_id].append(switch_id)
                    self.alllinks[switch_id].append(core_id)
                    switch_link_no += 1
                    
                if switch_link_no >= self.agg_core_link_no:
                    break

                    
        #Edge Switches
        for s in range(self.edge_no):
            switch_id = 'e%i'%(len(self.core_switches)+len(self.agg_switches)+len(self.edge_switches)+1)
            switch = self.addSwitch(switch_id)
            
            #Add edge switch records
            self.edge_switches.append(switch_id)
            
            #initialize link records
            if not self.alllinks.has_key(switch_id):
                self.alllinks[switch_id] = list()
            
            #TODO: add link to agg
            switch_link_no = 0
            self.agg_switches.sort()
            for agg_id in self.agg_switches :
                if len(self.alllinks[agg_id])-self.agg_core_link_no<((self.edge_no*self.edge_agg_link_no)/self.agg_no):
                    mylink = self.addLink(switch_id, agg_id, bw = self.agg_bw)
                    #add link to record
                    self.alllinks[agg_id].append(switch_id)
                    self.alllinks[switch_id].append(agg_id)
                    switch_link_no += 1
                    
                if switch_link_no >= self.edge_agg_link_no:
                    break
            
            #add self.myhosts and connection to self.myhosts
            for h in range(self.host_no):
                host_id = 'h%i' % (len(self.myhosts)+len(self.outside_hosts)+1)
                # Each host gets 50%/n of system CPU
                host = self.addHost(host_id)
                #host = self.addHost(host_id, cpu=0.5/((self.host_no*self.edge_no)+(self.out_no)))
                
                #add link 100 Mbps, 5ms delay, 10% loss
                #self.addLink(host_id, switch_id, bw=10, delay='5ms', loss=10, max_queue_size=1000, use_htb=True
                self.addLink(host_id, switch_id, bw = self.edge_bw)
                
                #initialize link records
                if not self.alllinks.has_key(host_id):
                    self.alllinks[host_id] = list()
                    
                #add link records
                self.alllinks[host_id].append(switch_id)
                self.alllinks[switch_id].append(host_id)
                
                #add host records
                self.myhosts.append(host_id)
            
            #Add hosts until you can separate the host network and the outside host network
            len(self.myhosts)+len(self.outside_hosts)+1

        
def createQueues(ercs_topo, net):
    '''
    -Create queues for each port in the switch
    '''
    for (node1,node2) in ercs_topo.links():
        if node1 in ercs_topo.core_switches and node2 in ercs_topo.agg_switches:
            bw1 = ercs_topo.core_bw
            bw2 = ercs_topo.agg_bw
        elif node1 in ercs_topo.core_switches and node2 in ercs_topo.outside_hosts:
            bw1 = ercs_topo.out_bw
            bw2 = None
        elif node1 in ercs_topo.outside_hosts and node2 in ercs_topo.core_switches:
            bw1 = None
            bw2 = ercs_topo.out_bw
        elif node1 in ercs_topo.agg_switches and node2 in ercs_topo.core_switches:
            bw1 = ercs_topo.agg_bw
            bw2 = ercs_topo.core_bw
        elif node1 in ercs_topo.agg_switches and node2 in ercs_topo.edge_switches:
            bw1 = ercs_topo.agg_bw
            bw2 = ercs_topo.edge_bw
        elif node1 in ercs_topo.edge_switches and node2 in ercs_topo.agg_switches:
            bw1 = ercs_topo.edge_bw
            bw2 = ercs_topo.agg_bw
        elif node1 in ercs_topo.edge_switches and node2 in ercs_topo.myhosts:
            bw1 = ercs_topo.edge_bw
            bw2 = None
        elif node1 in ercs_topo.myhosts and node2 in ercs_topo.edge_switches:
            bw1 = None
            bw2 = ercs_topo.edge_bw

        #Install queues to each switch port
        realnode1 = net.getNodeByName(node1)
        realnode2 = net.getNodeByName(node2)

        (port1, port2) = ercs_topo.port(node1, node2)

        #limit link bandwidth with tc
        if bw1 != None:
            port_name = None
            #get the port interface name
            for port in realnode1.ports:
                if realnode1.ports[port] == port1:
                    port_name = port
                    break
            realnode1.cmd('sudo /sbin/tc class change dev '+str(port_name)+' parent 1: classid 1:ffff htb rate '+str(bw1*1000)+'kbit ceil '+str(bw1*1000)+'kbit')
            print 'sudo /sbin/tc class change dev '+str(port_name)+' parent 1: classid 1:ffff htb rate '+str(bw1*1000)+'kbit ceil '+str(bw1*1000)+'kbit'
        if bw2 != None:
            port_name = None
            #get the port interface name
            for port in realnode2.ports:
                if realnode2.ports[port] == port1:
                    port_name = port
                    break
            realnode2.cmd('sudo /sbin/tc class change dev '+str(port_name)+' parent 1: classid 1:ffff htb rate '+str(bw2*1000)+'kbit ceil '+str(bw2*1000)+'kbit')
            print 'sudo /sbin/tc class change dev '+str(port_name)+' parent 1: classid 1:ffff htb rate '+str(bw2*1000)+'kbit ceil '+str(bw2*1000)+'kbit'

        #add queues
        for queue in ercs_topo.queue_bw:
            if bw1 != None:
                
                print realnode1.cmd('dpctl add-queue tcp:127.0.0.1:6633 '+str(port1)+' '+ str(queue) +' ' + str(int(ercs_topo.queue_bw[queue]*bw1)))
                # print "ask for queue info"
                print 'dpctl add-queue tcp:127.0.0.1:6633 '+str(port1)+' '+ str(queue) +' ' + str(int(ercs_topo.queue_bw[queue]*bw1))
                # print realnode1.cmd('dpctl dump-queue tcp:127.0.0.1:6633 '+str(port1)+' '+ str(queue))
            if bw2 != None:
                
                print realnode2.cmd('dpctl add-queue tcp:127.0.0.1:6633 '+str(port2)+' '+ str(queue) +' ' + str(int(ercs_topo.queue_bw[queue]*bw2)))
                # print "ask for queue info"
                print 'dpctl add-queue tcp:127.0.0.1:6633 '+str(port2)+' '+ str(queue) +' ' + str(int(ercs_topo.queue_bw[queue]*bw2))
                # print realnode2.cmd('dpctl dump-queue tcp:127.0.0.1:6633 '+str(port2)+' '+ str(queue))
        '''                
        for port in switch.ports:
            #supposly the next line is needed in order for the link to be throttle, 
            #but once the use of dpctl is enough ,at least for now, we don't use it
            #switch.cmd('sudo /sbin/tc class change dev '+str(port)+' parent 1: classid 1:ffff htb rate 10000kbit ceil 10000kbit')
            for queue in ercs_topo.queue_bw:
                switch.cmd('dpctl add-queue tcp:localhost '+str(switch.ports[port])+' '+ str(queue) +' ' + str(ercs_topo.queue_bw[queue]))
        '''


    # for switch_name in (ercs_topo.core_switches+ercs_topo.agg_switches+ercs_topo.edge_switches):
    #     #check switch type and set wanted link capacity
    #     if switch_name in ercs_topo.core_switches:
    #         bw = ercs_topo.core_bw
    #     #Install queues to each switch port
    #     switch = net.getNodeByName(switch_name)
    #     for port in switch.ports:
    #         #supposly the next line is needed in order for the link to be throttle, 
    #         #but once the use of dpctl is enough ,at least for now, we don't use it
    #         #switch.cmd('sudo /sbin/tc class change dev '+str(port)+' parent 1: classid 1:ffff htb rate '+str(bw*1000)+'kbit ceil '+str(bw*1000)+'kbit')
    #         print 'sudo /sbin/tc class change dev '+str(port)+' parent 1: classid 1:ffff htb rate '+str(bw*1000)+'kbit ceil '+str(bw*1000)+'kbit'
    #         for queue in ercs_topo.queue_bw:
    #             switch.cmd('dpctl add-queue tcp:localhost '+str(switch.ports[port])+' '+ str(queue) +' ' + str(ercs_topo.queue_bw[queue]))
    

def waitControllertoConnectSwitches():
    '''
    Add remote controller
    '''
    info( '*** Waiting for all switches to connect to the controller' )
    while 'is_connected' not in quietRun( 'ovs-vsctl show' ):
        sleep( 1 )
        info( '.' )
    info( ' Done\n' )

def makeHostDetectable(ercs_topo, hosts, net):
    '''
    Make Host detectable by hosttracker
    '''
    #Should wait for controller to detect all links also?
    #sleep(5)
    for host_name in hosts:
        host = net.getNodeByName(host_name)
        host.sendCmd("timeout " + str(ercs_topo.host_detectable_timeout) + " ping 10.0.0.255 -W 1")
    
    sleep(ercs_topo.host_detectable_timeout)
    for host_name in hosts:
        host = net.getNodeByName(host_name)
        host.monitor()


def waitControllertoConnectTpGenerator(ercs_topo, net, *args):
    info( '*** Waiting controller to connect to topology generator...' )
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        os.remove(ercs_topo.socket_path)
    except OSError:
        pass
    s.bind(ercs_topo.socket_path)
    s.listen(1)

    conn, addr = s.accept()
    print(' Done\n')
    if len(args)==0 :
        thread.start_new_thread(receiveDataFromController, (conn, ercs_topo, net)) 
    else :
        receiveDataFromController(conn, ercs_topo, net)

def receiveDataFromController(conn, ercs_topo, net):
    info( '\n*** Waiting for data from the controller...' )
    hostIperfport = list()
    while 1:
        try:
            #Get the data from the stream
            (host_ip, bw, holding_time, outside_host_ip) = pickle.loads(conn.recv(2048))
            print "*** Received Data!!"
            #print (host_ip, bw, holding_time, ouside_host_ip)
        except Exception, e:
            info('*** Controller Disconnected\n')
            print e
            conn.close()
            while True :
                waitControllertoConnectTpGenerator(ercs_topo, net, 0)
                sleep(1)

        #get a unique port number by the combination of the two ip strings plus the starting port nunmber
        hostIperfport.append(host_ip+outside_host_ip)
        #add the other string because we need to ports, UDP and TCP
        hostIperfport.append(outside_host_ip+host_ip)

        #Get host by ip (get both outside hosts and other host)
        outside_host = getHostNamebyIP(ercs_topo, net, outside_host_ip)
        host = getHostNamebyIP(ercs_topo, net, host_ip)

        #get the ports for iperf
        iperf_udp_port = ercs_topo.iperf_port + hostIperfport.index(host_ip+outside_host_ip) 
        iperf_tcp_port = ercs_topo.iperf_port + hostIperfport.index(outside_host_ip+host_ip)


        #host.monitor()
        #outside_host.monitor()

        #UDP            
        host.cmd("timeout " + str(holding_time + 1) + " iperf -s -u -p " + str(iperf_udp_port) + "&")

        outside_host.cmd("iperf -c "+host_ip+" -u -p "+str(iperf_udp_port)+" -t "+str(holding_time)+
            " -b "+str((bw*ercs_topo.udp_ratio))+"M" + "&")

        print "HostIP = ", host_ip, " |UDPPort=", str(iperf_udp_port), " |TCPPort=", str(iperf_tcp_port)
        print "UDP"
        print("timeout " + str(holding_time + 1) + " iperf -s -u -p " + str(iperf_udp_port))
        print("iperf -c "+host_ip+" -u -p "+str(iperf_udp_port)+" -t "+str(holding_time)+
            " -b "+str((bw*ercs_topo.udp_ratio))+"M")

        # #TCP
        host.cmd("timeout " + str(holding_time + 1) + " iperf -s -p " + str(iperf_tcp_port) + "&")
        outside_host.cmd("iperf -c "+host_ip+" -p "+str(iperf_tcp_port)+" -t "+str(holding_time)+
            " -b "+str((bw*(1-ercs_topo.udp_ratio)))+"M" + "&")

        print "TCP"
        print("timeout " + str(holding_time + 1) + " iperf -s -p " + str(iperf_tcp_port))
        print("iperf -c "+host_ip+" -p "+str(iperf_tcp_port)+" -t "+str(holding_time)+
            " -b "+str((bw*(1-ercs_topo.udp_ratio)))+"M")

        #invert this, put the hosts to generate the traffic instead of being the outside host
        # in order to obtain more throught
        # outside_host.cmd("timeout " + str(holding_time + 1) + " iperf -s -u -p " + str(iperf_udp_port) + "&")
        # host.cmd("iperf -c "+outside_host_ip+" -u -p "+str(iperf_udp_port)+" -t "+str(holding_time)+
        #     " -b "+str((bw*ercs_topo.udp_ratio))+"M" + "&")

        # # #TCP
        # outside_host.cmd("timeout " + str(holding_time + 1) + " iperf -s -p " + str(iperf_tcp_port) + "&")
        # host.cmd("iperf -c "+outside_host_ip+" -p "+str(iperf_tcp_port)+" -t "+str(holding_time)+
        #     " -b "+str((bw*(1-ercs_topo.udp_ratio)))+"M" + "&")

        #Not the best programming logic here, but for now it will stay like this, and it works so...

    #Should close socket after program quitting

def installStaticARPEntry(ercs_topo, net):
    '''
    Install static arp entries for all the outside hosts and hosts
    '''
    #populate the arp table of the hosts
    for host_name in ercs_topo.myhosts:
        host = net.getNodeByName(host_name)
        for outhost_name in ercs_topo.outside_hosts:
            outhost = net.getNodeByName(outhost_name)
            mac = outhost.cmd("ifconfig -a | grep HW | cut -c39-55").rstrip()
            host.cmd("arp -s "+str(outhost.IP())+" "+str(mac))
            #print "arp -s "+str(outhost.IP())+" "+str(mac)

    #populate the arp table of the outside hosts
    for outhost_name in ercs_topo.outside_hosts:
        outhost = net.getNodeByName(outhost_name)
        for host_name in ercs_topo.myhosts:
            host = net.getNodeByName(host_name)
            mac = host.cmd("ifconfig -a | grep HW | cut -c39-55").rstrip()
            outhost.cmd("arp -s "+str(host.IP())+" "+str(mac))
            #print "arp -s "+str(host.IP())+" "+str(mac)
    

def getHostNamebyIP(ercs_topo, net, ip):
    for host_name in ercs_topo.myhosts+ercs_topo.outside_hosts:
        host = net.getNodeByName(host_name)
        for intf in host.intfNames():
            if str(host.IP(intf)) == ip:
                return host
    return None

def runCli(net, *args):
    net.run( CLI, net )

def startTopology():
    #Create network and add queues to switches
    ercs_topo = ERCSTopo()
    net = Mininet(controller = RemoteController, topo=ercs_topo,
                  host=CPULimitedHost, link=TCLink)

    for num in range(ercs_topo.out_no):
        hostname='o%i' % (num+1)
        hostip = '10.128.0.%i' % (num+1)
        net.getNodeByName(hostname).setIP(hostip, 8)

    net.start()

    installStaticARPEntry(ercs_topo,net)

    #sleep(5)
    
    #create queues for each port in each switch
    # info("*** Creating "+str(len(ercs_topo.queue_bw))+" queues for each switch port... ")
    # createQueues(ercs_topo, net)
    # print "Done\n"
    
    #Add remote controller
    waitControllertoConnectSwitches()
    
    '''
    Make Host detectable by hosttracker
    '''
    info("\n*** Making hosts detectable for "+ str(ercs_topo.host_detectable_timeout) +" seconds... ")
    makeHostDetectable(ercs_topo,ercs_topo.myhosts, net)
    print "Done\n"
    
    '''
    Make OutsideHost detectable by hosttracker
    '''
    # raw_input("*** Press enter when all the hosts have been discovered by the controller")
    info("\n*** Making outside hosts detectable for "+ str(ercs_topo.host_detectable_timeout) +" seconds... ")
    makeHostDetectable(ercs_topo,ercs_topo.outside_hosts, net)
    print "Done\n"
    
    '''
    Connecting the controller to the Topology generator
    '''
    waitControllertoConnectTpGenerator(ercs_topo, net)

    '''
    Run Cli
    '''
    info( '\n*** Running CLI\n' )
    CLI( net )

    '''
    Stop Topology
    '''
    net.stop()

    #open thread to wait for controllers to connect

    #rc = RemoteController('rc')
    
    #rc_state = rc.start()
    #rc.stop()
    #scratchnet - try to connect with it


    #net.iperf( )
    '''
    dumpNodeConnections(net.self.myhosts)
    print "Testing network connectivity"
    net.pingAll()
    print "Testing bandwidth between h1 and h4"
    h1, h4 = net.getNodeByName('h1', 'h4')
    net.iperf((h1, h4))
    '''

if __name__ == '__main__':
    setLogLevel('info')
    startTopology()
    #ss = SingleSwitchTopo()
    
    #net = Mininet(controller = RemoteController, topo=ss,
    #             host=CPULimitedHost, link=TCLink)
    #net.start()
