import ConfigParser
import os

class IniHandler(object):
    '''
    Reads, creates and writes the configuration file
    
    How To:
    -Start class
        ini_handler = IniHandler()
    -Read a ini file (the filepath can be specified, otherwise default is loaded (conf.ini)
        ini_handler.read_ini()
    -read a value from the file
        ini_handler.read_ini_value("topology", "core_link")
    '''

    def __init__(self, filepath=None):
        '''
        Constructor
        '''
        self.config = ConfigParser.ConfigParser()
        self.read_ini(filepath)
        
    
    def clean_conf(self):
        self.config = ConfigParser.ConfigParser()
    
    def add_ini_section(self, section):
        '''
        Add a section to the configuration file
        
        If section already exists, does nothing
        '''
        if not self.config.has_key(section) :
            self.config[section] = {}
    
    def add_ini_key(self, section, key, value):
        '''
        Add a key and a value to a section in the configuration file 
        '''
        if len(self.config[section]) == 0 :
            self.config[section] = {}
        
        self.config[section][key] = value
    
    def add_ini_key_dict(self, section, key_dict):
        '''
        Adds a dictionary of values indexed by key to the section
        '''
        self.config = key_dict
        
    def read_ini_value(self, section, key):
        '''
        Read value from ini file
        Return String with the value
        '''
        #print("Section = %s, Key = %s - Trying to get values", section, key)
        try :
            return self.config.get(section, key)
        except Exception:
            print("INI File doesn't contain expected values")
            os._exit(0)
    
    def write_ini(self):
        '''
        Write configuration file
        '''
        with open('conf.ini', 'w') as configfile:
            self.config.write(configfile)
        pass
    
    def read_ini(self, filepath=None):
        '''
        Read Configuration File
        In case filepath == None, reads default file - conf.ini
        '''
        
        #print ("Filepath = %s - Trying to read INI file", filepath)
        
        self.config = ConfigParser.ConfigParser()
        
        if filepath == None :
            self.config.read('conf.ini')
        else:
            try:
                with open(filepath) as f: pass
            except Exception:
                print("INI File not found")
                os._exit(0)
                
            self.config.read(filepath)
            
        #print ("INI File successfully loaded")
            
def launch():
    import os
    print os.getcwd()
    ini_handler = IniHandler("conf.ini")
    
    #ini_handler.read_ini("conf.ini")
    #ini_handler.read_ini_value("topology", "core_link")
    