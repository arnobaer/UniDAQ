# This file manages the dynamic waiting time measurements and it is intended to be used as a plugin for the QTC software

import logging
import sys
sys.path.append('../modules')
from ..utilities import *
l = logging.getLogger(__name__)

help = help_functions()
vcw = VisaConnectWizard.VisaConnectWizard()
trans = transformation()


class dynamicwaiting_class:

    def __init__(self, main_class):
        self.main = main_class
        self.switching = self.main.switching
        self.biasSMU = self.main.devices["IVSMU"]
        self.compliance = self.main.job_details["dynamicwaiting"]["Compliance"]
        self.justlength = 24
        self.interval = 0.01
        self.buffer = 100
        self.current_voltage = None
        self.voltage_step_list = []
        self.get_data_query = "printbuffer(1, {samples!s}, measbuffer)"

        self.SMU_clean = "measbuffer = nil"

        # Starts the actual measurement
        time = self.do_dynamic_waiting()

    def stop_everything(self):
        """Stops the measurement"""
        order = {"ABORT_MEASUREMENT": True}  # just for now
        self.main.queue_to_main.put(order)

    @hf.timeit
    def do_dynamic_waiting(self):
        """
        This function does everything concerning the dynamic waiting time measurement
        :return:
        """

        # Config the SMU
        self.do_preparations()

        # Conduct the measurement
        for i, voltage in enumerate(self.voltage_step_list):
            if not self.main.stop_measurement():  # To shut down if necessary

                # Here the magic happens it changes all values and so on
                values = self.do_dynamic_measurement("dynamicwaiting", self.biasSMU, voltage, 100, 0.01, True)

                if self.main.check_complience(self.biasSMU, float(self.compliance)):
                    self.stop_everything()  # stops the measurement if compliance is reached

                if not self.main.steady_state_check(self.biasSMU, max_slope=1e-6, wait=0, samples=5, Rsq=0.5, complience=self.compliance):  # Is a dynamic waiting time for the measuremnts
                    self.stop_everything()

        # Ramp down and switch all off
        self.current_voltage = self.main.main.default_dict["Defaults"]["bias_voltage"]
        self.main.ramp_voltage(self.biasSMU, "set_voltage", self.current_voltage, 0, 20, 0.01)
        self.main.change_value(self.biasSMU, "set_voltage", "0")
        self.main.change_value(self.biasSMU, "set_output", "0")



    def do_preparations(self):
        """This function prepares the setup, like ramping the voltage and steady state check
        """

        # Get ramping list
        voltage_Start = self.main.job_details["dynamicwaiting"].get("StartVolt", 0)
        voltage_End = self.main.job_details["dynamicwaiting"].get("EndVolt", 0)
        voltage_steps = self.main.job_details["dynamicwaiting"].get("VoltSteps", 10)
        self.voltage_step_list = self.main.ramp_value(voltage_Start, voltage_End, voltage_steps)

        # Switch to IV for correct biasing for ramp
        if not self.switching.switch_to_measurement("IV"):
            self.stop_everything()

        # Configure the setup, compliance and switch on the smu
        self.main.send_to_device(self.biasSMU, self.SMU_clean)
        self.main.change_value(self.biasSMU, "set_voltage", "0")
        self.main.config_setup(self.biasSMU, [("set_complience_current", str(self.compliance))])
        self.main.change_value(self.biasSMU, "set_voltage", "0")
        self.main.change_value(self.biasSMU, "set_output", "1")

        if self.main.steady_state_check(self.biasSMU, max_slope=1e-6, wait=0, samples=3, Rsq=0.5, complience=self.compliance):  # Is a dynamic waiting time for the measuremnts
            self.current_voltage = self.main.main.default_dict["Defaults"]["bias_voltage"]
        else:
            self.stop_everything()

    def do_dynamic_measurement(self, str_name, device, voltage = 0, samples = 100, interval = 0.01, write_to_main = True):
        '''
         Does a simple dynamic waiting time measurement

        :param str_name: What measurement is conducted, only important when write_to_main is true
        :param device: Which device should be used
        :param xvalue: XValue used
        :param samples: How many samples should be taken
        :param interval: measurement interval
        :param write_to_main: Writes the value back to the main loop (default: True)
        :return: Returns the mean of all acquired values
        '''

        self.main.send_to_device(self.biasSMU, self.SMU_clean)

        # Todo: Actually it is not necessary to generate this text every time
        self.SMU_config = "smua.measure.count = {samples!s} \n" \
                          "smua.measure.interval = {interval!s}\n" \
                          "measbuffer = smua.makebuffer(smua.measure.count)\n" \
                          "smua.source.levelv = {level!s} " \
                          "smua.measure.overlappedi(measbuffer)\n" \
                          "waitcomplete()\n".format(samples=samples, interval=interval, level=voltage)
        # Send the command to the device and wait till complete
        self.main.send_to_device(device, self.SMU_config)

        # Waits the time it takes at least for the device to finish operation plus 100 ms
        sleep(samples*(interval/1000.)+100)

        # Get the data from the device
        ans = self.main.query_device(device, self.get_data_query.format(samples=samples))

        xvalues, yvalues = self.pic_device_answer(ans, interval)

        if write_to_main: # Writes data to the main, or not
            self.main.queue_to_main.put({str(str_name): [xvalues, yvalues]})

        # Clear buffer
        self.main.send_to_device(device, self.SMU_clean)

        return (xvalues, yvalues)


    def pic_device_answer(self, answer_string, interval=0.1):
        """
        Dissects the answer string and returns 2 array containing the x an y values
        :param answer_string: String to dissect
        :param interval: interval defined
        :return: xvalues, yvalues
        """
        yvalues = answer_string.strip["["].strip["]"].split[","]
        xvalues = [interval*x for x in range(len(yvalues))]

        return xvalues, yvalues
