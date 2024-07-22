# Support for a heated bed
#
# Copyright (C) 2018-2019  Kevin O'Connor <kevin@koconnor.net>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

class PrinterHeaterBed:
    def __init__(self, config):
        self.printer = config.get_printer()
        pheaters = self.printer.load_object(config, 'heaters')
        self.heater = pheaters.setup_heater(config, 'B')
        self.get_status = self.heater.get_status
        self.stats = self.heater.stats
        # Register commands
        gcode = self.printer.lookup_object('gcode')
        gcode.register_command("M140", self.cmd_M140)
        gcode.register_command("M190", self.cmd_M190)
    def cmd_M140(self, gcmd, wait=False):
        # Set Bed Temperature
        temp = gcmd.get_float('S', 0.)
        hotbed_0 = gcmd.get_float('A', 1) #flsun add , if 1 ,heat,if 0 ,don't heat
        hotbed_1 = gcmd.get_float('B', 1) #flsun add ,
        pheaters = self.printer.lookup_object('heaters')
        gcode = self.printer.lookup_object('gcode') #flsun add
        if wait:
            if hotbed_0 == 0:
                pheaters.set_temperature(self.heater, temp, False)
            if hotbed_1 == 0:
                gcode.run_script_from_command("SET_HEATER_TEMPERATURE HEATER=HotBed1 TARGET=%f WAIT=0" % temp)
        if hotbed_0==1:
            pheaters.set_temperature(self.heater, temp, wait)
        if hotbed_1==1:
            if wait: #flsun add ,if wait = True ,heat need wait ,so command include 'WAIT=1'
                gcode.run_script_from_command("SET_HEATER_TEMPERATURE HEATER=HotBed1 TARGET=%f WAIT=1" % temp) 
            else: #flsun add ,if wait = False ,heat don't wait ,so command include 'WAIT=0'
                gcode.run_script_from_command("SET_HEATER_TEMPERATURE HEATER=HotBed1 TARGET=%f WAIT=0" % temp)
        if wait:
            if hotbed_0 == 0:
                pheaters.set_temperature(self.heater, 0, False)
            if hotbed_1 == 0:
                gcode.run_script_from_command("SET_HEATER_TEMPERATURE HEATER=HotBed1 TARGET=%f WAIT=0" % 0)
    def cmd_M190(self, gcmd):
        # Set Bed Temperature and Wait
        self.cmd_M140(gcmd, wait=True)

def load_config(config):
    return PrinterHeaterBed(config)

