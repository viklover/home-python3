import os
import json

from . import BASE_DIR
from .block import Block

from threading import Lock


class Variables(Block):

    def __init__(self, name, program):
        Block.__init__(self, name)
        self.lock = Lock()
        self.vars = dict()


class ProgramVariables(Variables):

    def __init__(self, program):
        Variables.__init__(self, "ProgramVariables", program)

        self.vars['objects'] = program.object_manager.get_objects_dict()
        self.vars['object_manager'] = program.object_manager
        self.vars['statistics'] = program.statistics

    def __getitem__(self, key):
        return self.vars[key]


class UserVariables(Variables):

    def __init__(self, program):
        Variables.__init__(self, "UserVariables", program)
        self.__load_items()

    def __load_items(self):

        if not os.path.isfile(f'{BASE_DIR}/bin/variables'):
            self.vars = {}
            self.__save_items()
            return

        try:
            with open(f'{BASE_DIR}/bin/variables') as f:
                self.vars = json.load(f)
        except json.decoder.JSONDecodeError:
            self.vars = {}

    def __save_items(self):
        with open(f'{BASE_DIR}/bin/variables', 'w') as f:
            f.write(json.dumps(self.vars))

    def __getitem__(self, key):
        self.lock.acquire()
        try:
            value = self.vars[key]
        except KeyError:
            value = None
            self.log_msg(171, (key), color='orange')
        self.lock.release()
        return value

    def __setitem__(self, item, value):

        if not isinstance(item, str):
            self.log_msg(172, color='red')
            return

        self.lock.acquire()
        self.vars[item] = value
        self.lock.release()

        self.__save_items()
