import os
import sys
import time
import json
import asyncio
import colorama
import schedule

from threading import Thread

import RPi.GPIO as gpio

gpio.setmode(gpio.BOARD)
gpio.setwarnings(False)

BASE_DIR = __file__.split("package")[0][:-1]
BASE_DIR_LIST = BASE_DIR.split("/")[1:]

REGION = json.load(open(f"{BASE_DIR}/configs/config.json"))['localization']
MESSAGES = json.load(open(f"{BASE_DIR}/resources/localization.json"))[REGION]['messages']
MONTHS = json.load(open(f"{BASE_DIR}/resources/localization.json"))[REGION]['months']
STATS = json.load(open(f"{BASE_DIR}/resources/localization.json"))[REGION]['stats']

CONFIG = json.load(open(f"{BASE_DIR}/configs/config.json"))

options = {
    "-l": 0
}

from .bots import VKBot
from .block import colors
from .dates import Time, Date
from .funcs import get_type_list
from .managers import ObjectManager, ActionManager, TaskManager, ClientManager
from .statistics import Statistics
from .timehandler import TimeHandler
from .variables import ProgramVariables, UserVariables


class Home(object):

    def __init__(self, args):
        self.log("-" * 10)

        self.time_handler = TimeHandler(self)

        self.sys_args = args
        self._status = 0

    def __start(self):

        self.__execute_script('startup', path='scripts')

        self.log_msg(1)

        self.__import_modules()

        if self.__check_config_files():
            self._status = 1

            self.log_msg(147, color='green')

            self.time_handler.start()

            # INIT BLOCKS

            self.object_manager = ObjectManager(self)
            self.statistics = Statistics(self)

            self.vars = ProgramVariables(self)
            self.user_vars = UserVariables(self)

            self.action_manager = ActionManager(self)
            self.task_manager = TaskManager(self)
            self.client_manager = ClientManager(self)
            self.vkbot = VKBot(self)

            # START BLOCKS

            self.statistics.start()

            self.action_manager.start()
            self.task_manager.start()
            self.object_manager.start()
            self.client_manager.start()
            self.vkbot.start()

            self.time_handler.join()

        else:
            self.log_msg(148)

    def __close(self, reason):
        self._status = 0
        gpio.cleanup()
        time.sleep(0.2)
        self.__execute_script('shutdown', path='scripts')
        # sys.exit(0)

    def __prepare_variables(self):

        if not os.path.isfile(f'{BASE_DIR}/bin/shutdown'):
            self.shutdown_reason = None

            # return - выход из функции

            return

        with open(f'{BASE_DIR}/bin/shutdown', 'r') as f:
            try:
                self.shutdown_reason = json.load(f)
            except:
                self.shutdown_reason = None

    def startup(self):
        self.__prepare_variables()
        self.__set_options(self.sys_args)
        self.__execute_command(self.sys_args)

    def shutdown(self, reason):

        if not self._status:
            return

        with open(f'{BASE_DIR}/bin/shutdown', "w") as f:
            f.write(reason)

        self._status = 0

        # CLEAN GENERAL PINS INPUT OUTPUT
        gpio.cleanup()

        # DELAY
        time.sleep(0.2)

        # EXECUTE 'SHUTDOWN' SCRIPT
        self.__execute_script('shutdown', path='scripts')

        self.log_msg(101)

    def restart(self):
        self.__close()
        self.log_msg(102)
        self.__execute_script('start')

    def get_status(self):
        return self._status

    def __execute_command(self, args):
        try:
            if args[1] == "start":
                self.log_msg(12, (args[1]))
                self.__print_file("resources", "files", "startup.txt")
                self.__start()
                self.shutdown('completed work')
            elif args[1] == "help":
                self.log_msg(12, (args[1]))
                self.__print_file("resources", "files", "help.txt")
            elif args[1] == "check_configs":
                self.log_msg(12, (args[1]))
                if self.__check_config_files():
                    self.log_msg(147)
            elif args[1] == "check_stats":
                self._status = 2
                self.__import_modules()
                self.object_manager = ObjectManager(self)
                self.stats = Statistics(self)
                self.stats.start()
            else:
                self.log_msg(121, (args[1]))
                self.__print_file("resources", "files", "none.txt")
        except KeyboardInterrupt:
            self.print(str())
            # self.__print_file("resources", "files", "none.txt")
            # finally:
            self.shutdown('keyboard interrupt')

    def __execute_script(self, script, path=None):
        self.log_msg(15, (f'{f"{path}" if path else ""}/{script}.sh'))
        os.system(f'cd {BASE_DIR}{f"/{path}" if path else ""} && ./{script}.sh &')

    def __set_options(self, args):

        args = list(filter(lambda x: "-" in x, args))

        if len(args):
            self.log_msg(11, (', '.join(args)))

        for arg in args:

            if arg in options:
                options[arg] = 1
            else:
                self.log_msg(111, (arg))

    def __print_file(self, *args):
        self.log_msg(16, (os.path.join(*args)))
        with open(os.path.join('/', *BASE_DIR_LIST, *args)) as f:
            self.print(f.read())

    def print(self, text, color='white'):

        if color:
            print(colors[color], end='')

        print(text)

    def log(self, line, no_capitalize=False, color='white', indent=0):

        with open(f"{BASE_DIR}/logs/system.log", 'a') as f:
            f.write(f"\n[{Date()} - {Time()}] {line.capitalize() if not indent else line}")

            if options["-l"]:
                self.print(
                    f"{colors[color]}[{Date()} - {Time()}] {' ' * indent + line.capitalize() if (not no_capitalize and not indent) else (' ' * indent + line)}")

    def log_msg(self, code, args=(), color='white', indent=0):
        self.log(MESSAGES[str(code)] % args, color=color, indent=indent)

    def __check_config_files(self):

        def checkExist(name):
            self.log_msg(141, color='green', indent=6)
            return os.path.exists(f"{BASE_DIR}/{name}")

        def checkJSON(name):
            self.log_msg(142, color='green', indent=6)
            try:
                with open(f"{BASE_DIR}/{name}") as f:
                    config = json.load(f)
                return True
            except:
                return False

        def checkIDs(name):
            self.log_msg(143, color='green', indent=6)

            with open(f'{BASE_DIR}/{name}') as f:
                config = json.load(f)

                for pos in config:

                    for id in config[pos]:

                        if id in ids:
                            return False

                        ids.append(id)

            return True

        def checkFields(name):
            self.log_msg(144, color='green', indent=6)

            def unpackDict(data, field, config):

                states = list()

                if "?" in field:
                    for i in config:
                        states.append(isinstance(config[i], get_type_list(data[field])))

                    if False in states:
                        return [False]

                    return [True]

                n_field = field if "!" not in field else field[1:]

                if "!" in field and n_field not in config:
                    return [True]

                if "!" not in field and n_field not in config:
                    return [False]

                if isinstance(data[field], dict):

                    for i in data[field]:

                        if isinstance(data[field][i], dict):
                            states.extend(unpackDict(data[field], i, config[n_field]))
                        else:

                            if "?" in i:
                                for j in config[n_field]:
                                    states.append(isinstance(config[n_field][j], get_type_list(data[field][i])))

                                if False in states:
                                    return [False]

                                return [True]

                            if "!" in i and i[1:] not in config[n_field]:
                                return [True]

                            if "!" not in i and i not in config[n_field]:
                                return [False]

                            # print(i, config, (isinstance(config[field[1:] if "!" in field else field][(i if "!" not in i else i[1:])], get_type_list(data[field][i]))))

                            states.append(
                                ((i if "!" not in i else i[1:]) in config[n_field]) and
                                (isinstance(config[n_field][(i if "!" not in i else i[1:])],
                                            get_type_list(data[field][i])))
                            )

                            if False in states:
                                return [False]

                else:
                    states.append(n_field in config and isinstance(config[n_field], get_type_list(data[field])))

                return states

            with open(f"{BASE_DIR}/resources/objects.json") as f:

                string = f.read()

                _class = name.split('/')[1]
                _type = json.loads(string)['classes'][_class]['type']

                fields = {
                    **json.loads(string)['types'][_type]['fields'],
                    **json.loads(string)['classes'][_class]['fields']
                }

                with open(f"{BASE_DIR}/{name}") as k:

                    config = json.load(k)

                    for pos in config:

                        for id in config[pos]:

                            current_fields = {**fields}

                            if 'kind' in config[pos][id]:
                                _kind = config[pos][id]['kind']
                                current_fields.update(json.loads(string)['kinds'][_class][_kind]['fields'])

                            states = list()

                            for field in current_fields:
                                states.extend(unpackDict(current_fields, field, config[pos][id]))

                            if False in states:
                                self.id_with_error = id
                                return False

            return True

        def prepareFiles(name):

            self.log_msg(146, color='green', indent=6)

            with open(f"{BASE_DIR}/resources/objects.json") as f:

                string = f.read()
                config = json.loads(string)

                _class = name.split('/')[1]
                _type = config['classes'][_class]['type']

                files = set()

                if 'files' in config['types'][_type]:
                    files.update(set([*config['types'][_type]['files']]))

                if 'files' in config['classes'][_class]:
                    files.update(set([*config['classes'][_class]['files']]))

                if _class in config['kinds']:
                    if 'files' in config['kinds'][_class]:
                        files.update(set([*config['kinds'][_class]['files']]))

            values = {
                'type': _type,
                'class': _class
            }

            for file in files:

                if '%' in file:
                    file = file % values

                folder_path = f'{BASE_DIR}/{file.split("/")[0]}'

                for folder in file.split('/')[1:]:
                    if not os.path.isdir(folder_path):
                        os.mkdir(folder_path)
                    folder_path += '/' + folder

                if not os.path.isfile(file):
                    os.system(f'touch {BASE_DIR}/{file}')

        def prepareFolders(name):
            self.log_msg(145, color='green', indent=6)

            with open(f"{BASE_DIR}/resources/objects.json") as f:

                string = f.read()
                config = json.loads(string)

                _class = name.split('/')[1]
                _type = config['classes'][_class]['type']

                folders = set()

                if 'folders' in config['types'][_type]:
                    folders.update(set([*config['types'][_type]['folders']]))

                if 'folders' in config['classes'][_class]:
                    folders.update(set([*config['classes'][_class]['folders']]))

                if _class in config['kinds']:
                    if 'folders' in config['kinds'][_class]:
                        folders.update(set([*config['kinds'][_class]['folders']]))

            values = {
                'type': _type,
                'class': _class
            }

            for folder in folders:

                if '%' in folder:
                    folder = folder % values

                folder_path = BASE_DIR

                for folder in folder.split('/'):
                    folder_path += '/' + folder
                    if not os.path.isdir(folder_path):
                        os.mkdir(folder_path)

        self.log_msg(14, color='green')

        files = list()
        ids = list()

        with open(f'{BASE_DIR}/resources/objects.json') as f:
            config = json.load(f)

        for _class in config['classes']:

            if _class not in os.listdir(path=f'{BASE_DIR}/configs'):
                path = f'{BASE_DIR}/configs/{_class}/config.json'
                os.mkdir(f'{BASE_DIR}/configs/{_class}')

                with open(path, 'w') as doc:
                    doc.write('{\n    "this": \n    {\n        \n    }\n}')

            files.append(f'configs/{_class}/config.json')

        self.id_with_error = None

        for file in files:

            self.log(f'  - {file}: ', color='green')

            if not checkExist(file):
                self.log_msg(1480, (file, MESSAGES['1481']), color='red')
                return False

            if not checkJSON(file):
                self.log_msg(1480, (file, MESSAGES['1482']), color='red')
                return False

            if not checkIDs(file):
                self.log_msg(1480, (file, MESSAGES['1483']), color='red')
                return False

            if not checkFields(file):
                self.log_msg(1480, (file, MESSAGES['1484'] % self.id_with_error), color='red')
                return False

            prepareFolders(file)
            prepareFiles(file)

        return True

    def __import_modules(self):

        self.log_msg(13, color='blue')

        with open(f'{BASE_DIR}/resources/paths.json') as f:

            for path in json.load(f)['folders']:
                full_path = f'{BASE_DIR}/{path}'

                if not '*' in path:
                    sys.path.append(full_path)
                    self.log('  - ' + path, color='blue')
                    continue

                full_path = full_path[:-2]
                path = path[:-2]

                for folder in os.listdir(full_path):
                    sys.path.append(f'{full_path}/{folder}')
                    self.log(f'  - {path}/{folder}', color='blue')
