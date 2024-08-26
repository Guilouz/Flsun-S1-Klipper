# Kinematic input shaper to minimize motion vibrations in XY plane
#
# Copyright (C) 2019-2020  Kevin O'Connor <kevin@koconnor.net>
# Copyright (C) 2020  Dmitry Butyugin <dmbutyugin@google.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import collections
import chelper
import os,math,csv
from . import shaper_defs

FLOAT_EPSILON = 0.01

class InputShaperParams:
    def __init__(self, axis, config):
        self.axis = axis
        self.shapers = {s.name : s.init_func for s in shaper_defs.INPUT_SHAPERS}
        shaper_type = config.get('shaper_type', 'mzv')
        self.shaper_type = config.get('shaper_type_' + axis, shaper_type)
        if self.shaper_type not in self.shapers:
            raise config.error(
                    'Unsupported shaper type: %s' % (self.shaper_type,))
        self.damping_ratio = config.getfloat('damping_ratio_' + axis,
                                             shaper_defs.DEFAULT_DAMPING_RATIO,
                                             minval=0., maxval=1.)
        self.shaper_freq = config.getfloat('shaper_freq_' + axis, 0., minval=0.)
    def update(self, gcmd):
        axis = self.axis.upper()
        self.damping_ratio = gcmd.get_float('DAMPING_RATIO_' + axis,
                                            self.damping_ratio,
                                            minval=0., maxval=1.)
        self.shaper_freq = gcmd.get_float('SHAPER_FREQ_' + axis,
                                          self.shaper_freq, minval=0.)
        shaper_type = gcmd.get('SHAPER_TYPE', None)
        if shaper_type is None:
            shaper_type = gcmd.get('SHAPER_TYPE_' + axis, self.shaper_type)
        if shaper_type.lower() not in self.shapers:
            raise gcmd.error('Unsupported shaper type: %s' % (shaper_type,))
        self.shaper_type = shaper_type.lower()
    def get_shaper(self):
        if not self.shaper_freq:
            A, T = shaper_defs.get_none_shaper()
        elif self.shaper_type == 'zero_zv':
            A, T = self.csv_call(self.shaper_freq, self.damping_ratio, self.axis)
        else:
            A, T = self.shapers[self.shaper_type](
                    self.shaper_freq, self.damping_ratio)
        return len(A), A, T
    def csv_call(self,shaper_freq, damping_ratio, axis,x_file_path='/tmp/shaper_calc_data_x.csv', y_file_path='/tmp/shaper_calc_data_y.csv'):
        if axis == 'x':
            if os.path.exists(x_file_path):
                old_freq_x, old_A_x, old_T_x = self.get_shaper_file_data(x_file_path)
                if math.fabs(old_freq_x - shaper_freq) < FLOAT_EPSILON:
                    A = old_A_x
                    T = old_T_x
                else:
                    A,T = self.generate_csv(shaper_freq, damping_ratio, x_file_path)
            else:
                A,T = self.generate_csv(shaper_freq, damping_ratio, x_file_path)
        if axis == 'y':
            if os.path.exists(y_file_path):
                old_freq_y, old_A_y, old_T_y = self.get_shaper_file_data(y_file_path)
                if math.fabs(old_freq_y - shaper_freq) < FLOAT_EPSILON:
                    A = old_A_y
                    T = old_T_y
                else:
                    A,T = self.generate_csv(shaper_freq, damping_ratio, y_file_path)    
            else:
                A,T = self.generate_csv(shaper_freq, damping_ratio, y_file_path)       
        return (A, T)
    def get_shaper_file_data(self,file_path):
        with open(file_path, newline='') as csvfile: 
            reader = csv.reader(csvfile)
            headers = next(reader)
            column_data = {header_x: [] for header_x in headers}
            for row in reader:
                for header, value in zip(headers, row):
                    column_data[header].append(value)
            first_column_data = column_data.get('freq', [])
            second_column_data = column_data.get('time', [])
            second_column_data = [float(_s) for _s in second_column_data]
            third_column_data = column_data.get('amplitude', [])
            third_column_data = [float(_s) for _s in third_column_data]
            freq = float(first_column_data[0])
        return freq, second_column_data, third_column_data
    def generate_csv(self,shaper_freq, damping_ratio, dump_file_path):
        A,T = shaper_defs.get_zero_zv_shaper(shaper_freq, damping_ratio)
        try:
            with open(dump_file_path, 'w') as csvfile:
                csvfile.write("freq,time,amplitude")
                csvfile.write("\n")
                for i in range(len(A)):
                    _new_A = f'{A[i]:.5f}'
                    _new_T = f'{T[i]:.5f}'
                    _line = ",".join([str(shaper_freq), _new_A, _new_T]) + "\n"
                    csvfile.write(_line)
        except IOError as e:
            raise Exception("Error writing to file '%s': %s" % (dump_file_path, str(e)))
        return (A, T)
    def get_status(self):
        return collections.OrderedDict([
            ('shaper_type', self.shaper_type),
            ('shaper_freq', '%.3f' % (self.shaper_freq,)),
            ('damping_ratio', '%.6f' % (self.damping_ratio,))])

class AxisInputShaper:
    def __init__(self, axis, config):
        self.axis = axis
        self.params = InputShaperParams(axis, config)
        self.n, self.A, self.T = self.params.get_shaper()
        self.saved = None
    def get_name(self):
        return 'shaper_' + self.axis
    def get_shaper(self):
        return self.n, self.A, self.T
    def update(self, gcmd):
        self.params.update(gcmd)
        old_n, old_A, old_T = self.n, self.A, self.T
        self.n, self.A, self.T = self.params.get_shaper()
        return (old_n, old_A, old_T) != (self.n, self.A, self.T)
    def set_shaper_kinematics(self, sk):
        ffi_main, ffi_lib = chelper.get_ffi()
        success = ffi_lib.input_shaper_set_shaper_params(
                sk, self.axis.encode(), self.n, self.A, self.T) == 0
        if not success:
            self.disable_shaping()
            ffi_lib.input_shaper_set_shaper_params(
                    sk, self.axis.encode(), self.n, self.A, self.T)
        return success
    def get_step_generation_window(self):
        ffi_main, ffi_lib = chelper.get_ffi()
        return ffi_lib.input_shaper_get_step_generation_window(self.n,
                                                               self.A, self.T)
    def disable_shaping(self):
        if self.saved is None and self.n:
            self.saved = (self.n, self.A, self.T)
        A, T = shaper_defs.get_none_shaper()
        self.n, self.A, self.T = len(A), A, T
    def enable_shaping(self):
        if self.saved is None:
            # Input shaper was not disabled
            return
        self.n, self.A, self.T = self.saved
        self.saved = None
    def report(self, gcmd):
        info = ' '.join(["%s_%s:%s" % (key, self.axis, value)
                         for (key, value) in self.params.get_status().items()])
        gcmd.respond_info(info)

class InputShaper:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.printer.register_event_handler("klippy:connect", self.connect)
        self.toolhead = None
        self.shapers = [AxisInputShaper('x', config),
                        AxisInputShaper('y', config)]
        self.stepper_kinematics = []
        self.orig_stepper_kinematics = []
        # Register gcode commands
        gcode = self.printer.lookup_object('gcode')
        gcode.register_command("SET_INPUT_SHAPER",
                               self.cmd_SET_INPUT_SHAPER,
                               desc=self.cmd_SET_INPUT_SHAPER_help)
    def get_shapers(self):
        return self.shapers
    def connect(self):
        self.toolhead = self.printer.lookup_object("toolhead")
        kin = self.toolhead.get_kinematics()
        # Lookup stepper kinematics
        ffi_main, ffi_lib = chelper.get_ffi()
        steppers = kin.get_steppers()
        for s in steppers:
            sk = ffi_main.gc(ffi_lib.input_shaper_alloc(), ffi_lib.free)
            orig_sk = s.set_stepper_kinematics(sk)
            res = ffi_lib.input_shaper_set_sk(sk, orig_sk)
            if res < 0:
                s.set_stepper_kinematics(orig_sk)
                continue
            self.stepper_kinematics.append(sk)
            self.orig_stepper_kinematics.append(orig_sk)
        # Configure initial values
        self.old_delay = 0.
        self._update_input_shaping(error=self.printer.config_error)
    def _update_input_shaping(self, error=None):
        self.toolhead.flush_step_generation()
        new_delay = max([s.get_step_generation_window() for s in self.shapers])
        self.toolhead.note_step_generation_scan_time(new_delay,
                                                     old_delay=self.old_delay)
        failed = []
        for sk in self.stepper_kinematics:
            for shaper in self.shapers:
                if shaper in failed:
                    continue
                if not shaper.set_shaper_kinematics(sk):
                    failed.append(shaper)
        if failed:
            error = error or self.printer.command_error
            raise error("Failed to configure shaper(s) %s with given parameters"
                        % (', '.join([s.get_name() for s in failed])))
    def disable_shaping(self):
        for shaper in self.shapers:
            shaper.disable_shaping()
        self._update_input_shaping()
    def enable_shaping(self):
        for shaper in self.shapers:
            shaper.enable_shaping()
        self._update_input_shaping()
    cmd_SET_INPUT_SHAPER_help = "Set cartesian parameters for input shaper"
    def cmd_SET_INPUT_SHAPER(self, gcmd):
        updated = False
        for shaper in self.shapers:
            updated |= shaper.update(gcmd)
        if updated:
            self._update_input_shaping()
        for shaper in self.shapers:
            shaper.report(gcmd)

def load_config(config):
    return InputShaper(config)
