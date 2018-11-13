# This file conducts a simple IV measurement

import logging
import sys
import numpy as np
sys.path.append('../modules')
from ..VisaConnectWizard import *
from ..utilities import *
l = logging.getLogger(__name__)

help = help_functions()
vcw = VisaConnectWizard.VisaConnectWizard()

@help.timeit # Decorator for timing of a function (not crucial)
class IV_class: # Every measurement muss have a class named after the file AND the suffix '_class'
    
    def __init__(self, main_class):
        # Here all parameters can be definde, which are crucial for the module to work, you can add as much as you want
        self.main = main_class # Import the main parameters and functions
        self.justlength = 24 # paramerter for the writting to file
        time = self.do_IVMain() # Starts the measurement

    def stop_everything(self):
        """Stops the measurement, by sending a signal to the main loop, via a queue object"""
        order = {"ABORT_MEASUREMENT": True}
        self.main.queue_to_main.put(order)

    @help.timeit
    def do_IVMain(self):
        '''This function conducts an IV measurements'''
        voltage_End = None
        voltage_Start = None
        voltage_steps = None
        bias_SMU = self.main.devices["IVSMU"]

        # Defining the min/max/steps for the meausrement
        voltage_End.append(self.main.job_details["IV"].get("EndVolt", 0))
        voltage_Start.append(self.main.job_details["IV"].get("StartVolt", 0))
        voltage_steps.append(self.main.job_details["IV"].get("Steps", 0))

        # Add the fileheader
        if self.main.save_data:
            self.main.write(self.main.measurement_files["IV"], self.main.job_details["IV"]["header"] + "\n") # writes correctly the units into the file

        # Generates a voltagestep list
        voltage_step_list = self.main.ramp_value(voltage_Start, voltage_End, voltage_steps)

        # Config the setup for IV
        complience = str(self.main.job_details["IV"].get("Complience", "50e-6"))
        self.main.config_setup(bias_SMU, [("set_complience_current", complience)])
        self.main.change_value(bias_SMU, "set_output", "1")

        # Loop over all voltages which should be conducted
        for i, voltage in enumerate(voltage_step_list):
            if not self.main.stop_measurement(): # To shut down if necessary
                self.main.change_value(bias_SMU, "set_voltage", str(voltage))
                self.main.settings["Defaults"]["bias_voltage"] = voltage  # changes the bias voltage in the state machine
                if not self.main.steady_state_check(bias_SMU, max_slope = 1e-6, wait = 0, samples = 5, Rsq = 0.5, complience=complience): # Is a dynamic waiting time for the measuremnts
                    self.stop_everything()

                if self.main.check_complience(bias_SMU, float(complience)):
                    self.stop_everything() # stops the measurement if complience is reached

                string_to_write = ""
                I, V = self.do_IV(voltage, bias_SMU, samples = 3)
                if self.main.save_data:
                    string_to_write += str(I).ljust(self.justlength) + str(V).ljust(self.justlength)

                self.main.write(self.main.measurement_files["IVCV"], string_to_write + "\n")  # writes correctly the units into the fileself.main.IVCV_file, string_to_write)

            elif self.main.stop_measurement(): # Stops the measurement if necessary
                break

        if self.main.save_data: # Closes the file after completion of measurement or abortion
            help.close_file(self.main.IVCV_file)

        # After the measurement ramp down and switch of the SMU
        self.main.ramp_voltage(bias_SMU, "set_voltage", str(voltage_step_list[i-1]), 0, 20, 0.01)
        self.main.change_value(bias_SMU, "set_voltage", "0")
        self.main.change_value(bias_SMU, "set_output", "0")

        return None

    #@help.timeit
    def do_IV(self, voltage, device_dict, samples = 5):
        '''This function simply sends a request for reading a current value and process the data'''
        if not self.main.stop_measurement():
            if not self.main.steady_state_check(device_dict, max_slope=1e-6, wait=0, samples=4,Rsq=0.5, complience=self.main.job_details["IVCV"]["IV"]["Complience"]):  # Is a dynamic waiting time for the measuremnt
                self.stop_everything()
                l.warning("Steady state could not be reached, shutdown of measurement")
                return
            values = []
            for i in range(samples):
                command = self.main.build_command(device_dict, "Read") # returns 2 values!!!
                values.append(str(vcw.query(device_dict, command)).split("\t"))

            current = sum([float(x[0]) for x in values])/len(values) # Makes a mean out of it
            voltage = sum([float(x[1]) for x in values]) / len(values)  # Makes a mean out of it

            self.main.settings["Defaults"]["bias_voltage"] = voltage  # changes the bias voltage of the sate machine

            self.main.measurement_data["IV"][0] = np.append(self.main.measurement_data["IV"][0], [float(voltage)])
            self.main.measurement_data["IV"][1] = np.append(self.main.measurement_data["IV"][1],[float(current)])
            self.main.queue_to_main.put({"IV": [float(voltage), float(current)]})

            return (current, voltage)