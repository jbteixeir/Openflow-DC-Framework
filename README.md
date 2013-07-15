Openflow-DC-Framework
=====================

Describe the Framework...


CONTROLLER STUFF
----------------
DIR:poxbetta/ext/

**How to develop your own logic:**

VM ALLOCATION/MIGRATION:
  - Under the ext/vm you can find the files vm_allocation_manager & file vm_migration_manager. Both of them are stricly for developing the algoritms for respectively vm allocation and vm migration.
  - Inter virtual machine communication (inside vm allocation manager) for now implements dijkstra algorithm. Change to fit your needs/experiments.

STATISTICS:
  - For now just bit rate, but it can be easily added everything supported by the OF protocol. More info check the ercs_stats file.
  - Exporting Statistics for now it saves in a file everytime new statistics arrive. It is oriented for the algorithms developed for allocation. So change to suit your own. A more general approach should be deployed soon. Maybe Later save in database (the one for the webplatform).

RULES:
  - Rules are installed according to the provided methods.
  - Inter virtual machine rules are also taken into consideration.
  - Check ercs_rules for detailed information

XENCOMMUNICATOR:
  - For now it's not working, but there's an open issue to solve this problem, and also some directives of how to solve it.
  - i.e. - General Hypervisor folder, and then inside developers can catch the events and contact the specific hypervisor.

INITHANDLER:
  - The INITHANDLER reads the 'conf.ini' file and put's it in a dictionary (check any of the modules for examples)

**NOTE**: Event-Oriented programming (So catch events and do what you want with them)


**How to Configure:**

  - There is a file called 'conf.ini' where you can configure the basic things defined by the framework, 
can also add more if one needs.


**How to launch:**

  ./pox.py ercs
  
  with debug,
    ./pox.py ercs log.level --DEBUG


*Requirements:*
  - python
  - python-netaddr
  - ...


EMULATOR STUFF
--------------
DIR:poxbetta/ext/Topology Generator (MN)

**How to develop your own logic:**

TOPOLOGY GENERATOR:
  - Generates tree and fat tree topologies. Use the provided 'conf.ini' file to configure the desired topology.
  - Adding features: 
    - Adding traffic generator is as trivial as launching the generator itself. Meaning that the process of automatically start the traffic generation between hosts it is done automatically. One just needs to specify the command.


**How to install:**

  - Please use mininet provided image, or install mininet manually. (I advise to use the image as it works out of the box)


**How to launch:**

  ./tpgeneratormn2.0.py
  

VIRTUAL MACHINE REQUESTER STUFF
-------------------------------
DIR:poxbetta/ext/VM Requests Generator

- Use to Request Virtual Machines automatically

Arguments:
  1 - IP of controller
  2 - Port
  3 - Request Rate (time interval between requests)
  4 - Average holding time (of vm)
  5 - number of types of user(*)
  6+ - Percentage of bandwidth for each user(*)

(*)currently not working the types of users since mininet doesn't support yet minimum/maximum bandwidth ratio

Examples:
  python ./vmrequesterpoisson.py 127.0.0.1 3000 10 290 1 1

  python ./vmrequesterpoisson.py 127.0.0.1 3000 10 290 2 0.3 0.7

**NOTE:** For now the request requirements are embedded in the code, so one needs to change it to have the desired requests requirements. In the future maybe config file or more arguments will be added to fit the desired requirements.
**NOTE:** Might need root permissions to run some of the components



POX README
==========

POX is a network controller written in Python.

POX officially requires Python 2.7 (though much of it will work fine
fine with Python 2.6), and should run under Linux, Mac OS, and Windows.
You can place a pypy distribution alongside pox.py (in a directory
named "pypy"), and POX will run with pypy (this can be a significant
performance boost!).

POX currently communicates with OpenFlow 1.0 switches and includes
special support for Open vSwitch.

pox.py boots up POX. It takes a list of module names on the command line,
locates the modules, calls their launch() function (if it exists), and
then transitions to the "up" state.

Modules are looked for everywhere that Python normally looks, plus the
"pox" and "ext" directories.  Thus, you can do the following:

  ./pox.py forwarding.l2_learning

You can pass options to the modules by specifying options after the module
name.  These are passed to the module's launch() funcion.  For example,
to set the address or port of the controller, invoke as follows:

  ./pox.py openflow.of_01 --address=10.1.1.1 --port=6634

pox.py also supports a few command line options of its own which should
be given first:
 --verbose      print stack traces for initialization exceptions
 --no-openflow  don't start the openflow module automatically
