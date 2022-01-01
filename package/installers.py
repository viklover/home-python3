import os
import time
import json
import sqlite3
import subprocess

from threading import Thread

import signal
import fcntl

from . import BASE_DIR
from .db import Database
from .objects import *

from .serialport import SerialPort


class Installer:

    def __init__(self, config):
        self.objects = None
        self.format_db = None
        self._class = config['name']

    def install(self, obj):
        self.set_info(obj)
        self.create_table(obj)
        self.create_value_file(obj)

    def set_objects(self, objects):
        self.objects = objects

    def set_format_databases(self, format):
        self.format_db = format

    def create_table(self, obj):

        path = f'{BASE_DIR}/databases'

        events = Database(f'{path}/events', log_dir=f'{BASE_DIR}/logs')
        stats = Database(f'{path}/stats', log_dir=f'{BASE_DIR}/logs')

        if obj.get_id() not in events.get_tables():
            events.create(obj.get_id(), self.format_db['events'])

        if obj.get_id() not in stats.get_tables():
            stats.create(f'{obj.get_id()}_hours',
                         {'year': 'INT', 'month': 'INT', 'day': 'INT', 'hour': 'INT', **self.format_db['stats']})
            stats.create(f'{obj.get_id()}_days',
                         {'year': 'INT', 'month': 'INT', 'day': 'INT', **self.format_db['stats']})
            stats.create(f'{obj.get_id()}_months', {'year': 'INT', 'month': 'INT', **self.format_db['stats']})
            stats.create(f'{obj.get_id()}_years', {'year': "INT", **self.format_db['stats']})

    def set_info(self, obj):

        path = f"{BASE_DIR}/bin/objects"
        data = json.load(open(path))

        id = obj.get_id()

        if id not in list(map(lambda x: x['id'], data['objects'])):
            dictionary = {
                "id": id,
                "class": self._class,
                "was_created": time.time(),
                "was_removed": None
            }

            data['objects'].append(dictionary)

            doc = open(path, 'w')
            doc.write(json.dumps(data))
            doc.close()

            obj.set_info(dictionary)

        for i in data['objects']:
            if i['id'] == id:
                obj.set_info(i)
                break

    def create_value_file(self, obj):

        path = f'{BASE_DIR}/values/{obj.get_id()}/value'

        if not os.path.isfile(path):
            os.system(f'touch {path}')

    def finish(self):
        return


class InputsInstaller(Installer):

    def __init__(self, config):
        Installer.__init__(self, config)


class OutputsInstaller(Installer):

    def __init__(self, config):
        Installer.__init__(self, config)


class TriggersInstaller(Installer, Block):

    def __init__(self, config):
        Installer.__init__(self, config)
        Block.__init__(self, "TriggerController")
        self.thread = Thread(target=self.check_updates, daemon=True)
        self.thread.name = "TriggerController"
        self.object_links = dict()
        self.variables = dict()

    def install(self, obj):
        self.set_info(obj)
        self.create_table(obj)
        self.create_value_file(obj)

        # for i in obj.configurations['objects_in_condition']:
        #     if i not in self.object_links:
        #         self.object_links[i] = list()
        #     self.object_links[i].append(obj)

    def finish(self):
        # self.thread.start()
        pass

    def set_first_values(self):

        files = list()

        for _id in os.listdir(f'{BASE_DIR}/cache'):

            if _id not in self.object_links:
                self.object_links[_id] = list()

            files.append(tuple([_id, f'{BASE_DIR}/cache/{_id}/value']))

        for _id, file in files:
            with open(file) as f:
                value = eval(f.read())
            self.variables[_id] = value

    def check_updates(self):

        self.log('Запуск обработчика событий TriggerController', with_name=False)

        self.set_first_values()

        def get_value(file):
            with open(file) as f:
                return eval(f.read())

        files = list()

        for _id in os.listdir(f'{BASE_DIR}/cache'):
            files.append(tuple([_id, f'{BASE_DIR}/cache/{_id}/value']))

        while True:
            for _id, file in files:
                value = get_value(file)

                if self.variables[_id] != value:
                    self.variables[_id] = value

                    for obj in self.object_links[_id]:
                        # obj.set_variable(_id, value)
                        obj.check_conditions()

            time.sleep(1)


class OnewireInstaller(Installer):

    def __init__(self, config):
        Installer.__init__(self, config)
        self.serial_ports = dict()

    def install(self, obj):
        self.set_info(obj)
        self.create_table(obj)
        self.create_value_file(obj)

        if obj.get_kind() == 'serial':

            config = obj.configurations

            if config['path'] not in self.serial_ports:
                self.serial_ports[config['path']] = SerialPort(config['path'])

            obj.set_serial_port(self.serial_ports[config['path']])
