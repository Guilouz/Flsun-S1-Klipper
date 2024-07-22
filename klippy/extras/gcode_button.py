# Support for executing gcode when a hardware button is pressed or released.
#
# Copyright (C) 2019 Alec Plumb <alec@etherwalker.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging

class GCodeButton:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split(' ')[-1]
        self.pressed_time = 0 #flsun add
        self.release_time = 0 #flsun add
        self.triggered_time = 0 #flsun add
        self.pin = config.get('pin')
        self.last_state = 0
        buttons = self.printer.load_object(config, "buttons")
        if config.get('analog_range', None) is None:
            buttons.register_buttons([self.pin], self.button_callback)
        else:
            amin, amax = config.getfloatlist('analog_range', count=2)
            pullup = config.getfloat('analog_pullup_resistor', 4700., above=0.)
            buttons.register_adc_button(self.pin, amin, amax, pullup,
                                        self.button_callback)
        gcode_macro = self.printer.load_object(config, 'gcode_macro')
        self.press_template = gcode_macro.load_template(config, 'press_gcode')
        self.release_template = gcode_macro.load_template(config,
                                                          'release_gcode', '')
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode.register_mux_command("QUERY_BUTTON", "BUTTON", self.name,
                                        self.cmd_QUERY_BUTTON,
                                        desc=self.cmd_QUERY_BUTTON_help)

    cmd_QUERY_BUTTON_help = "Report on the state of a button"
    def cmd_QUERY_BUTTON(self, gcmd):
        gcmd.respond_info(self.name + ": " + self.get_status()['state'])

    def button_callback(self, eventtime, state):
        self.last_state = state
        template = self.press_template
        if not state:
            self.release_time = float(eventtime)
            self.triggered_time = self.release_time - self.pressed_time
            if 'motor_a' in self.name:
                if self.triggered_time < 0.25: # 200ms
                    self.gcode.run_script_from_command("M117 please calibrate motor A!")
                elif self.triggered_time > 0.25 and self.triggered_time < 0.8: #500ms
                    self.printer.invoke_shutdown("motor A occur error")
                    self.gcode.run_script("M117 motor A occor error!") 
            if 'motor_b' in self.name:
                if self.triggered_time < 0.25:
                    self.gcode.run_script_from_command("M117 please calibrate motor B!")
                elif self.triggered_time > 0.25 and self.triggered_time < 0.8:
                    self.printer.invoke_shutdown("motor B occur error")
                    self.gcode.run_script("M117 motor B occor error!")
            if 'motor_c' in self.name:
                if self.triggered_time < 0.25:
                    self.gcode.run_script_from_command("M117 please calibrate motor C!")
                elif self.triggered_time > 0.25 and self.triggered_time < 0.8:
                    self.printer.invoke_shutdown("motor C occur error")
                    self.gcode.run_script("M117 motor C occor error!")
            template = self.release_template
        else:
            self.pressed_time = float(eventtime)
        try:
            self.gcode.run_script(template.render())
        except:
            logging.exception("Script running error")

    def get_status(self, eventtime=None):
        if self.last_state:
            return {'state': "PRESSED"}
        return {'state': "RELEASED"}

def load_config_prefix(config):
    return GCodeButton(config)
