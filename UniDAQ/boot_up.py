#This modules are for boot up purposes.
# -It checks the validity of the installation and installs missing packages on its own
# -Loads the config files for the instrumentds etc.
# -Connects to all system relevant instruments
# -Initialize statistics and state control

import importlib, os, threading, yaml
import logging
import numpy as np
import glob
import sys

class loading_init_files:
    '''This class is for loading all config files, pad files and default parameters.
    This class is crucial for the program to work. All works within the init function of this class.
    It generates three new dicts which can be accessed from the class as class attributes

    self.devices_dict
    self.pad_files_dict
    self.default_values_dict

    '''


    def __init__(self, hf):

        self.log = logging.getLogger(__name__)

        # Get project path
        package_dir = os.path.dirname(os.path.realpath(__file__))
        init_dir = os.path.join(package_dir, "config")

        # Get data dirs
        devices_dir = os.path.join(init_dir, "device_lib")
        default_dir = os.path.join(init_dir, "config")
        pad_files_dir = os.path.join(init_dir, "Pad_files")

        # Get all files in the directories
        self.list_device_init = map(os.path.basename, glob.glob(os.path.join(devices_dir, "*.yml")))
        self.list_default_values = map(os.path.basename, glob.glob(os.path.join(default_dir, "*.yml")))
        self.list_pad_files_folders = os.listdir(pad_files_dir)


        #print(self.list_default_values)

        # Dictionaries for the types of input files
        self.devices_dict = {}
        self.pad_files_dict = {}
        self.default_values_dict = {}


        # Read in files and create the dictionary for the devices---------------------------------------------------------------------------------
        #-----------------------------------------------------------------------------------------------------------------------------------------
        for filename in self.list_device_init: # Loop over all files found

            self.log.info("Try reading device file: " + str(filename))

            #line_strings = hf.read_from_file(filename, devices_dir) # Reads every line in the file, returns a list
            #new_dict_name = self.check_for_device_name(line_strings, "Display_name")
            new_device_dict = self.create_dictionary(filename, devices_dir)

            self.devices_dict.update({new_device_dict.get("Display_name", "MissingNo"): new_device_dict}) # Adds the new device in the dictionary
        # -----------------------------------------------------------------------------------------------------------------------------------------
        # -----------------------------------------------------------------------------------------------------------------------------------------

        # Read in files and create the dictionary for the default values---------------------------------------------------------------------------
        # -----------------------------------------------------------------------------------------------------------------------------------------
        for filename in self.list_default_values: # Loop over all files found

            self.log.info("Try reading settings file: " + str(filename))
            #line_strings = hf.read_from_file(filename, default_dir) # Reads every line in the file, returns a list
            #new_dict_name = self.check_for_device_name(line_strings, "Settings_name")
            new_device_dict = self.create_dictionary(filename, default_dir)

            self.default_values_dict.update({new_device_dict["Settings_name"]: new_device_dict}) # Adds the new device in the dictionary
        # -----------------------------------------------------------------------------------------------------------------------------------------
        # -----------------------------------------------------------------------------------------------------------------------------------------

        # Read in files and create the dictionary for the pad files--------------------------------------------------------------------------------
        # -----------------------------------------------------------------------------------------------------------------------------------------
        #First check if the foldes matches with the projects listed and asign to each other
        pad_data_dict = {}
        for folder in self.list_pad_files_folders:
            pad_data_dict.update({folder: self.read_pad_files(os.path.join(pad_files_dir, folder))})

        self.pad_files_dict = pad_data_dict.copy()

        # Update the projects and sensors which are included and can be measured
        self.default_values_dict["Defaults"]["Sensor_types"] = {}
        for project in self.pad_files_dict:
            self.default_values_dict["Defaults"]["Sensor_types"].update({str(project): [sensor for sensor in self.pad_files_dict[project]]})
        self.default_values_dict["Defaults"]["Projects"] = [project for project in self.pad_files_dict]
        # -----------------------------------------------------------------------------------------------------------------------------------------
        # -----------------------------------------------------------------------------------------------------------------------------------------

        self.config_device_notation() # Changes the names of the dicts key for the devives, so that they are independet inside the program

    def read_pad_files(self, path):
        '''This function reads the pad files and returns a dictionary with the data'''

        # First get list of all pad files in the folder
        all_pad_files = {}
        list_of_files = os.listdir(path)
        header = []
        data = []
        for filename in list_of_files:
            with open(os.path.join(path, filename), "r") as f:
                read_data = f.readlines()
                #print(read_data)

            # first find the header
            for i, lines in enumerate(read_data):
                if "strip" in lines: # Can be done better
                    header = read_data[:i+1]
                    data = read_data[i+1:]
                    break

            # Find the reference pads in the header and strip length
            reference_pad_list = []
            new_param = {}
            for i, lines in enumerate(header):
                if "reference pad" in lines:
                    reference_pad_list.append(int(lines.split(":")[1]))

                # Find additional parameters
                elif ":" in lines:
                    new_param.update({lines.split(":")[0].strip(): lines.split(":")[1].strip()})
            #reference_pad_list = reference_pad_list.sort()


            # Now make the data look shiny
            data_list = []
            for lines in data:
                data_list.append([self.confloattry(x) for x in lines.split()])

            final_dict = {"reference_pads" : reference_pad_list, "header": header, "data": data_list}
            final_dict.update({"additional_params": new_param})
            all_pad_files.update({str(filename.split(".")[0]): final_dict})

        return all_pad_files

    def confloattry(self, value):
        """This function trys to convert a string to a float, else string is returned"""

        try:
            return float(value)
        except:
            return value

    def config_device_notation(self):
        '''This function renames the device dict, so that the measurement class has a common name declaration. It wont change the display name. Just for internal consistency purposes'''

        assigned_dicts = []
        for device in self.default_values_dict["Defaults"]: #  Gets me the internal names of all stated devices in the default file (or the keys) (only for the defaults file)
            # Searches for devices in the device list, returns false if not found (real device is the value dict of the device
            try:
                if (self.default_values_dict["Defaults"][device] in self.devices_dict) and self.default_values_dict["Defaults"][device] not in assigned_dicts:
                    # syntax for changing keys in dictionaries dictionary[new_key] = dictionary.pop(old_key)
                    self.devices_dict[device]=self.devices_dict.pop(self.default_values_dict["Defaults"][device])
                    assigned_dicts.append(self.default_values_dict["Defaults"][device])

                elif self.default_values_dict["Defaults"][device] in assigned_dicts: #looks if dict already assigned
                    # If so make a pointer to the already assigned dict (alias name)
                    # find the other dict
                    for key, value in self.default_values_dict["Defaults"].items(): # loop over all values
                        if value == self.default_values_dict["Defaults"][device]: # see if one entry has the same value as the searched one
                            if key in self.devices_dict: # now look if the key exists in the device dict
                                self.devices_dict.update({device: self.devices_dict[key]}) # now update with a reference to the other
                                break
            except:
                pass # This is just for saftey reasons if a list occurs during searching (eg operator names)


    def create_dictionary(self, filename, filepath):
        '''Creates a dictionary with all values written in the file using yaml'''

        resource = os.path.join(filepath, filename)
        #self.log.info("Loading file:" + str(filename))
        with open(resource, "r") as fp:
            return yaml.safe_load(fp)


#Debricated methods

    def check_for_device_name_debricated(self, line_strings, key_name):
        '''Searches for a device name in the config files'''

        dict_name = ""
        for line in line_strings:  # Loop over each lines to find the display name
            if line.find(key_name,0,150) != -1: # Searches for the key words, function will return a vaule greater -1 when match is found
                dict_name = line.split('"')[1]  # Gets me the the actual string which is written between the "..."
                break
        else: # If no break occured this will be displayed
            self.log.warning("No name for the device found!")

        return dict_name


    def create_dictionary_debricated(self, line_strings):
        '''Creates a dictionary with all values written in the file'''

        if line_strings[0][0] == "#": # Gets rid of a header line
            line_strings.remove(line_strings[0]) # Removes the header from the init list, which is useless

        dict = {} # Temporary dictionary
        for line in line_strings:
            if not line.isspace(): # Prevents that empty lines are written into the dictionary
                key = line.split("=")[0].strip() # Extracts the key name of the string and removes useless whitespaces
                value = line.split('"')[1]

                if value.find(",") >= 0 and key != "Device_IDN": # Just searches if commas are in the line but dont do if it is the device IDN
                    value = map(lambda string: string.strip(), value.split(",")) # Creates a list separated by commas and strips it for withspaces
                    #print(value)
                    try:
                        for i, val in enumerate(value):
                            value[i] = float(val)
                    except:
                        pass

                try:
                    value = float(value)
                except:
                    pass

                dict.update({key: value}) # Adds the new dict

        return dict

class connect_to_devices:
    '''This class simply handles the connections, generates a dictionary with all devices.
    This can be accessed via self.get_new_device_dict()'''

    def __init__(self, vcw, device_dict):
        """Actually does everythin on its own"""

        self.log = logging.getLogger(__name__)
        self.vcw = vcw
        self.device_dict = device_dict


        self.vcw.show_instruments() # Lists all devices which are connected to the PC

        for device in device_dict.keys():  # device_dict is a dictionary containing dictionaries

            try:
                device_IDN = device_dict[device]["Device_IDN"]  # gets me the IDN for each device loaded
                connection_type = device_dict[device].get("Connection_type", -1) # Gets me the type of the connection
                if "device_IDN_query" in device_dict[device]:
                    IDN_query = device_dict[device]["device_IDN_query"]
                else:
                    IDN_query = "*IDN?"

                if "GPIB" in str(connection_type).upper():
                    # This manages the connections for GBIP devices

                    if ("GPIB0::"+str(connection_type.split(":")[-1]) + "::INSTR") in self.vcw.resource_names: # Searches for a match in the resource list
                        success = self.vcw.connect_to(self.vcw.resource_names.index("GPIB0::"+str(connection_type.split(":")[-1]) + "::INSTR"), device_IDN, device_IDN=IDN_query) # Connects to the device Its always ASRL*::INSTR
                        if success:
                            self.log.info("Connection established to device: " + str(device) + " at ")
                        else:
                            self.log.error("Connection could not be established to device: " + str(device))
                    else:
                        self.log.error("Serial instrument at port " + str(connection_type.split(":")[-1]) + " is not connected.")


                elif "RS232" in str(connection_type).upper():
                    # This maneges the connections for Serial devices

                    if ("ASRL"+str(connection_type.split(":")[-1]) + "::INSTR") in self.vcw.resource_names: # Searches for a match in the resource list
                        #print(self.device_dict[device].get("Baud_rate", 57600))
                        success = self.vcw.connect_to(self.vcw.resource_names.index("ASRL"+str(connection_type.split(":")[-1]) + "::INSTR"), device_IDN, baudrate=self.device_dict[device].get("Baud_rate", 57600), device_IDN=IDN_query) # Connects to the device Its always ASRL*::INSTR
                        if success:
                            self.log.info("Connection established to device: " + str(device) + " at ")
                        else:
                            self.log.error("Connection could not be established to device: " + str(device))
                    else:
                        self.log.error("Serial instrument at port " + str(connection_type.split(":")[-1]) + " is not connected.")


                elif "IP" in str(connection_type).upper():
                    # This maneges the connections for IP devices
                    pass

                # Add other connection types

                else:
                    self.log.info("No valid connection type found for device " + str(device) + ". Therefore no connection established. You may proceed but measurements will fail.")

            except KeyError:
                self.log.error("Device " + device_dict[device]["Display_name"] + " has no IDN.")



        # List all devices
        #vcw.connect_to_instruments() # Tries to connect to all available instruments
        #vcw.verify_ID()              # Tries to query the IDN from each instrument

        self.new_device_dict = self.append_resource_to_device_dict() # Appends the resources to the decice dict

    def get_new_device_dict(self):
        """Returns all connected devices."""
        return self.new_device_dict

    def append_resource_to_device_dict(self): #better way
        '''Appends all valid resources to the dictionaries for the devices'''

        valid_resources =  self.vcw.myInstruments_dict # gets me the dict with the resources which are currently connected

        for device in self.device_dict.keys(): # device_dict is a dictionary containing dictionaries

                device_IDN = "No IDN"

                try:
                    device_IDN = self.device_dict[device]["Device_IDN"] # gets me the IDN for each device loaded
                except KeyError:
                    self.log.error("Device " + self.device_dict[device]["Display_name"] + " has no IDN.")

                resource = valid_resources.get(str(device_IDN).strip(), "Not listed")
                # Some kind of hack, it searches for the device IDN if not found "not listed" is returned

                if resource != "Not listed":
                    self.device_dict[device].update({"Visa_Resource": resource})  # If resource was found with same IDN the resource gets appended to the dict
                    self.log.info("Device " + self.device_dict[device]["Display_name"] + " is assigned to " + str(resource) + " with IDN: " + str(device_IDN).strip())
                elif resource == "Not listed":
                    self.log.error("Device " + self.device_dict[device]["Display_name"] + " could not be found in active resources.")

        return self.device_dict
        # Check if every device dict has its resource added
        #for device in device_dict.keys():
        #    if "Visa_Resource" not in device_dict[device]:
        #        print("No Visa resources listed for device " + device_dict[device]["Display_name"] + ".")

class update_defaults_dict:
    '''A class with two members. self.update takes an dict which updates the default values dict with the given fict.
    The other one self.to_update returns a dict. This can be extended, if the default values dict needs additional
    parameters.'''

    def update(self,dict):
        """
        Updates the defaults values dict
        :param dict: the dictionary which will be updated to the default values dict
        """
        for keys in self.to_update().keys():
            dict["Defaults"][keys] = self.to_update()[keys]
        return dict.copy()


    def to_update(self):
        """
        It only returns a dict of parametes, which are additional parameters for the state machine. Can be extendent
        with importan items for the framework to work.
        :return: dict
        """
        return {"End_time": "NaN",
                "Start_time": "NaN",
                "Bad_strips": 0,
                "Measurement_running": False,
                "Alignment": False,
                "trans_matrix": np.array([[ 0.95085078,  0.00807139,  0.        ],
                                            [-0.00098357,  0.98345749,  0.        ]]),
                "Environment_status": False,
                "external_lights": False,
                "internal_lights": False,
                "chuck_temperature": 0,
                "humidity_control": False,
                "current_tempmin": 20,
                "current_tempmax": 25,
                "current_hummin": 20,
                "current_hummax": 25,
                "Table_state": True,
                 "current_selected_browser_value": None,
                 "current_selected_main_object": None,
                 "Current_sensor": None,
                 "Current_operator": None,
                 "Current_filename": None,
                 "Current_project": None,
                "update_counter": 0,
                "last_plot_update": 0,
                "current_led_state": None,
                 "new_data": True,
                "IV_measure": [True, -10.0,-60.0, 12],  #do_it, min voltage, complience, steps
                "CV_measure": [True, -10.0, -50.0, 10],  # do_it,min voltage, complience, steps
                "Stripscan_measure": [True, -10.0, -50.0, 10],  #do_it,min voltage, complience, steps
                "Idiel_measure": [True, 1, 1, 200],  # do_it, every, start, stop
                "Rpoly_measure": [True, 1, 1, 200],  # do_it, every, start, stop
                "Cac_measure": [True, 1, 1, 200],  # do_it, every, start, stop
                "Idark_measure": [True, 1, 1, 200],  # do_it, every, start, stop
                "Rint_measure": [True, 1, 1, 200],  # do_it, every, start, stop
                "Cint_measure": [True, 1, 1, 200],  # do_it, every, start, stop
                "Cback_measure": [False, 1, 1, 200],  # do_it, every, start, stop
                "Istrip_measure": [True, 1, 1, 200],  # do_it, every, start, stop
                "IV_longterm_measure": [False, -10, -60.0, 5],  # do_it, min voltage, complience, steps
                "CintAC_measure": [False, 1, 1, 200],
                "Table_stay_down": False,
                "height_movement": 300, # height movement of the table when moving the table
                "table_ready": False,
                "bias_voltage": 0,
                "current_switching": {},
                "joystick": False,
                "zlock":    True,
                "table_is_moving": False,
                "V0": np.array( [ 68516.76686,   7866.83842,   6611.13939]),
                "current_strip": -1,
                "strip_scan_time": 10,
                "IVCV_time": 300,
                "Rint_MinMax": [-1.,1.,0.1]
                }
