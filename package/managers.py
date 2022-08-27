import os
import json
import time
import socket
import functools
import websockets
import asyncio

import schedule

from queue import Queue

from .block import Block
from .objects import *
from .installers import *
from .funcs import get_type_list

from . import BASE_DIR


class ObjectManager(Block):

    def __init__(self, program):
        Block.__init__(self, "ObjectManager")

        self.addresses_of_ids = dict()
        self.list_of_ids = list()
        self.vocabulary = dict()

        self.installers = dict()

        self.names = dict()

        self.program = program

        self.set_color('yellow')

        self.__prepare_variables()
        self.__initilize()
        self.__install()

    def start(self):
        self.__run_threads()
        self.__wait_for_readiness()
        self.set_ready(True)

    def __prepare_variables(self):

        config = json.load(open(f"{BASE_DIR}/resources/objects.json"))

        self.type_configs = dict()
        self.list_for_stats = list()
        self.shortnames_classes = dict()

        self.objects = [[], [], [], []]

        for _type in config['types']:
            self.objects[0].append(_type)
            self.objects[1].append(list())
            self.objects[2].append(list())
            self.objects[3].append(list())

        for _class in config['classes']:

            type_index = self.objects[0].index(config["classes"][_class]["type"])
            class_index = len(self.objects[1][type_index])

            self.shortnames_classes[_class] = config["classes"][_class]["short_name"]

            self.objects[1][type_index].append(_class)
            self.objects[2][type_index].append(list())
            self.objects[3][type_index].append(list())

            self.objects[3][type_index][class_index].append('standart')

            if not _class in config['kinds']:
                continue

            for kind in config['kinds'][_class]:
                self.objects[3][type_index][class_index].append(kind)

    def __initilize(self):

        self.log_msg(311)

        resources = json.load(open(f"{BASE_DIR}/resources/objects.json"))

        self.types = list()
        self.classes = list()

        for _type in resources['types']:

            self.types.append(_type)
            self.type_configs = resources['types'][_type]

            type_index = self.objects[0].index(_type)

            format_db = resources['types'][_type]['database']

            for _class in list(filter(lambda x: resources['classes'][x]['type'] == _type, resources['classes'])):

                self.classes.append(_class)
                self.vocabulary[_class] = resources['classes'][_class]['object']
                self.list_for_stats.append([self.vocabulary[_class]['name_plural'], []])

                class_index = self.objects[1][type_index].index(_class)
                class_name = resources["classes"][_class]["class_name"].capitalize()

                config = json.load(open(f'{BASE_DIR}/configs/{_class}/config.json'))

                objects = list()

                for system in config:

                    if len(config[system]):
                        self.log(f'  -  {_class.capitalize()}:', with_name=False, no_capitalize=True)

                    for id in config[system]:

                        param = config[system][id]

                        self.names[id] = param['name']
                        self.list_of_ids.append(id)

                        self.log(
                            f'      {param["name"]}',
                            with_name=False,
                            no_capitalize=True
                        )

                        if id not in os.listdir(path=f'{BASE_DIR}/values'):
                            os.mkdir(f'{BASE_DIR}/values/{id}')

                        kind = 'standart' if 'kind' not in param else param['kind']

                        args = param.copy()
                        args.update({
                            'id': id,
                            'class': _class,
                            'type': _type,
                            'formats': resources['types'][_type]['bots'],
                            'kind': kind,
                            'remote': not system == 'this',
                            'program': self.program
                        })

                        # if system == 'this':
                        object = eval(f'{class_name}{kind.capitalize() if "kind" in param else str()}')(args)
                        objects.append(object)

                        self.objects[2][type_index][class_index].append(object)
                        self.list_for_stats[-1][1].append([object.get_name(), object.get_id()])

                        self.addresses_of_ids[id] = (
                            type_index,
                            class_index,
                            len(self.objects[2][type_index][class_index]) - 1
                        )

                self.list_for_stats[-1][1].sort()

                if 'database' in resources['classes'][_class]:
                    format_db = resources['classes'][_class]['database']

                self.installers[_class] = eval(f'{_class.capitalize()}Installer')(resources["classes"][_class])
                self.installers[_class].set_objects(objects)
                self.installers[_class].set_format_databases(format_db)

    def __install(self):

        self.log_msg(312)

        for _class in self.classes:

            type_index = self.objects[0].index(self.get_type_by_class(_class))
            class_index = self.objects[1][type_index].index(_class)

            for obj in self.objects[2][type_index][class_index]:
                self.installers[_class].install(obj)

        for _class in self.classes:
            self.installers[_class].finish()

    def __run_threads(self):

        self.log_msg(313)

        for _type in range(0, len(self.objects[0])):
            for _class in range(0, len(self.objects[1][_type])):
                [obj.start() for obj in self.objects[2][_type][_class]]

    def __wait_for_readiness(self):

        self.log_msg(314)

        array = self.list_of_ids.copy()

        while not len(array):
            for id in array:
                if self.get_object_by_id(id).is_ready():
                    array.remove(array.index(id))

    def get_types(self):
        return self.objects[0]

    def get_type_by_class(self, name):
        for _type in self.objects[0]:
            type_index = self.objects[0].index(_type)
            for _class in self.objects[1][type_index]:
                if _class == name:
                    return _type

    def get_classes(self):
        classes = self.objects[1]
        return [j for i in classes for j in classes[classes.index(i)]]

    def get_classes_by_type(self, name):
        classes = list()

        type_index = self.objects[0].index(name)

        for _class in self.objects[1][type_index]:
            classes.append(_class)

        return classes

    def get_kinds_by_class(self, name):
        pass

    def get_all_objects(self):
        objects = list()

        for _type in self.objects[0]:
            type_index = self.objects[0].index(_type)
            for _class in self.objects[1][type_index]:
                class_index = self.objects[1][type_index].index(_class)
                for obj in self.objects[2][type_index][class_index]:
                    objects.append(obj)

        return objects

    def get_objects_dict(self):

        objects = dict()

        for _type in self.objects[0]:
            type_index = self.objects[0].index(_type)
            for _class in self.objects[1][type_index]:
                class_index = self.objects[1][type_index].index(_class)
                for obj in self.objects[2][type_index][class_index]:
                    objects[obj.get_id()] = obj

        return objects

    def get_objects_with_cond(self, conds):
        objects = list()

        for _type in self.objects[0]:
            type_index = self.objects[0].index(_type)
            for _class in self.objects[1][type_index]:
                class_index = self.objects[1][type_index].index(_class)
                for obj in self.objects[2][type_index][class_index]:
                    array = list()
                    for i in conds:
                        if isinstance(conds[i], int):
                            array.append(eval(f'obj.{i} != {conds[i]}'))
                        if isinstance(conds[i], str):
                            array.append(eval(f'obj.{i} != "{conds[i]}"'))
                    if not any(array):
                        objects.append(obj)

        return objects

    def get_objects_by_type(self, name):
        type_index = self.objects[0].index(name)
        objects = list()
        for _class in self.objects[1][type_index]:
            class_index = self.objects[1][type_index].index(_class)
            [objects.append(obj) for obj in self.objects[2][type_index][class_index]]
        return objects

    def get_objects_by_class(self, name, conds={}):
        objects = list()

        type_index = self.objects[0].index(self.get_type_by_class(name))
        class_index = self.objects[1][type_index].index(name)

        for obj in self.objects[2][type_index][class_index]:

            array = list()

            for i in conds:
                array.append(eval(f'obj.{i} != {conds[i]}'))

            if not any(array):
                objects.append(obj)
                continue

            if not len(conds):
                objects.append(obj)

        return objects

    def get_object_by_id(self, object_id):
        type_index, class_index, index = self.addresses_of_ids[str(object_id)]
        return self.objects[2][type_index][class_index][index]

    def get_remote_objects(self):
        objects = list()

        for _type in self.objects[0]:
            type_index = self.objects[0].index(_type)
            for _class in self.objects[1][type_index]:
                class_index = self.objects[1][type_index].index(_class)
                for obj in self.objects[2][type_index][class_index]:
                    if obj.is_remote():
                        objects.append(obj)

        return objects

    def get_list_for_stats(self):
        return self.list_for_stats.copy()

    def get_poll_dict(self, string=False):
        dictionary = dict()

        for _type in self.get_types():
            dictionary[_type] = {}
            for _class in self.get_classes_by_type(_type):
                dictionary[_type][_class] = {}
                for obj in self.get_objects_by_class(_class, {'_statistics': True}):
                    if string:
                        dictionary[_type][_class][obj.get_id()] = [obj.get_name(), obj.get_poll(string=True)]
                    else:
                        dictionary[_type][_class][obj.get_id()] = obj.get_poll(string=False)

        return dictionary

    def get_poll_string(self):

        array = self.get_poll_dict(string=True)

        string = str()

        for _type in array:

            for _class in array[_type]:

                objs = list(array[_type][_class].values())
                objs.sort()

                if not len(array[_type][_class]):
                    continue

                string += f'— {self.vocabulary[_class]["name_plural"].capitalize()} —\n'

                for id, value in objs:
                    string += value
                    string += '\n'

                string += '\n'

        return string


class ClientManager(Block, Thread):

    class Client(Block, Thread):

        def __init__(self, config):
            Block.__init__(self, config['name'])
            Thread.__init__(self, daemon=True)

            self.name = config['name']
            self.manager = config['program'].client_manager
            self.program = config['program']

    class SocketClient(Client):

        def __init__(self, config):
            ClientManager.Client.__init__(self, config)

            self.name = f'Socket {config["addr"][0]}:{config["addr"][1]}'

            self.conn = config['conn']
            self.addr = config['addr']

        def run(self):

            while self.program.get_status():
                try:
                    data = self.conn.recv(3024)

                    if not data:
                        continue

                    try:
                        udata = data.decode('utf-8')
                        json_data = json.loads(udata)

                        self.manager.process_request(self, json_data)
                    except ConnectionError:
                        pass
                    except json.decoder.JSONDecodeError:
                        pass

                except ConnectionResetError:
                    break

        def send(self, message):
            self.conn.send(message.encode())

    class SocketServer(Block, Thread):

        def __init__(self, program):
            Block.__init__(self, 'SocketServer')
            Thread.__init__(self, daemon=True)

            self.name = 'SocketServer'
            self.max_clients = 30
            self.port = 4950

            self.clients = list()

            self.program = program
            self.manager = program.client_manager

            self.set_color('azure')

            self.__import_settings()

        def __import_settings(self):

            self.log_msg(10012)

            config = json.load(open(f'{BASE_DIR}/configs/sockets/config.json'))

            if 'port' in config:
                self.port = config['port']

            if 'host' in config:
                self.host = config['host']
            else:
                self.host = socket.gethostname()

            if 'max_clients' in config:
                self.max_clients = config['max_clients']

        def run(self):

            while self.program.get_status():
                try:
                    self.server = socket.socket()
                    self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    self.server.bind((self.host, self.port))
                    self.server.listen(self.max_clients)
                except OSError:
                    self.log_msg(100111, color='red')
                    time.sleep(30)
                else:
                    break

            self.log_msg(100110)

            while self.program.get_status():
                conn, addr = self.server.accept()

                config = {
                    'addr': addr,
                    'conn': conn,
                    'name': f'SocketClient {addr[0]}:{addr[1]}',
                    'program': self.program
                }

                client = ClientManager.SocketClient(config)
                client.start()

                self.manager.add_client(client)

    class WebsocketClient(Client):

        def __init__(self, config):
            ClientManager.Client.__init__(self, config)

            self.name = f'Websocket {config["conn"]}'

            self.conn = config['conn']
            self.path = config['path']

            self.wsserver = config['wsserver']

        async def start(self):

            while self.program.get_status():

                try:

                    data = await self.conn.recv()

                    if not data:
                        continue

                    try:

                        json_data = json.loads(data)

                        self.manager.process_request(self, json_data)

                    except ConnectionError:
                        pass
                    except json.decoder.JSONDecodeError:
                        pass
                    except (
                            websockets.exceptions.ConnectionClosedOK,
                            websockets.exceptions.ConnectionClosedError,
                            ConnectionResetError,
                            Exception
                    ):
                        break

                except RuntimeError:
                    pass

                except ConnectionResetError:
                    break

        async def listen(self):

            while self.program.get_status():

                try:

                    data = await self.conn.recv()

                    if not data:
                        continue

                    try:

                        udata = data.decode('utf-8')
                        json_data = json.loads(udata)

                        self.manager.process_request(self, json_data)

                    except ConnectionError:
                        pass
                    except json.decoder.JSONDecodeError:
                        pass

                except ConnectionResetError:
                    break

        def send(self, message):

            async def sendio(message):
                await self.conn.send(message)

            asyncio.run(sendio(message))

    class WebsocketServer(Block, Thread):

        def __init__(self, program):
            Block.__init__(self, 'WebsocketServer')
            Thread.__init__(self, daemon=True)

            self.name = 'WebsocketServer'
            self.max_clients = 30
            self.port = 4850

            self.clients = list()

            self.program = program
            self.manager = program.client_manager

            self.set_color('azure')

            self.__import_settings()

        def __import_settings(self):

            self.log_msg(10012)

            config = json.load(open(f'{BASE_DIR}/configs/websockets/config.json'))

            if 'port' in config:
                self.port = config['port']

            if 'max_clients' in config:
                self.max_clients = config['max_clients']

            self.host = socket.gethostname()

        async def new_connection(self, websocket, path):

            config = {
                'conn': websocket,
                'path': path,
                'name': f'Websocket {path}',
                'wsserver': self,
                'program': self.program
            }

            client = ClientManager.WebsocketClient(config)

            self.manager.add_client(client)

            try:
                await client.start()
            except Exception:
                pass

            # await client.start()

        def run(self):


            while self.program.get_status():

                try:

                    asyncio.set_event_loop(asyncio.new_event_loop())

                    start_server = websockets.serve(self.new_connection, '192.168.1.3', self.port)

                    asyncio.get_event_loop().run_until_complete(start_server)

                    self.log_msg(100110)

                    asyncio.get_event_loop().run_forever()

                except OSError:
                    self.log_msg(100111, color='orange')
                    
                time.sleep(120)

    def __init__(self, program):
        Block.__init__(self, 'ClientManager')
        Thread.__init__(self, daemon=True)

        self.websocket_server = None
        self.socket_server = None
        self.name = 'ClientManager'
        self.program = program

        self.clients = list()
        self.lock = Lock()

        self.tasks = Queue()

        self.set_color('light gray')

        self.__prepare_variables()

    def __prepare_variables(self):

        def prepare_struct():

            types = []
            classes = []
            objects = []

            self.struct = self.program.object_manager.objects.copy()

            for _type in self.struct[0]:
                type_index = self.struct[0].index(_type)

                types.append(_type)

                classes.append([])
                objects.append([])

                for _class in self.struct[1][type_index]:
                    class_index = self.struct[1][type_index].index(_class)

                    classes[type_index].append(_class)
                    objects[type_index].append([])

                    for obj in self.struct[2][type_index][class_index]:
                        objects[type_index][class_index].append({
                            'id' : obj.get_id(),
                            'name' : obj.get_name(),
                            'short_name' : obj.get_short_name()
                        })

            self.struct[0] = types
            self.struct[1] = classes
            self.struct[2] = objects

        def prepare_short_struct():
            
            self.short_struct = [[], []]

            for classes in self.struct[1]:
                self.short_struct[0].extend(classes)

            for _ in range(len(self.short_struct[0])):    
                self.short_struct[1].append([])

            for index in range(len(self.short_struct[0])):
                
                for obj in self.program.object_manager.get_objects_by_class(
                    self.short_struct[0][index], conds={
                    "_statistics" : True
                }):
                    self.short_struct[1][index].append(int(obj.get_id()))

        prepare_struct()
        prepare_short_struct()


    def run(self):

        self.log_msg(1000)

        self.socket_server = self.SocketServer(self.program)
        self.socket_server.start()

        self.websocket_server = self.WebsocketServer(self.program)
        self.websocket_server.start()

        while self.program.get_status():

            client, message = self.tasks.get()

            try:
                client.send(message)
            except Exception:
                try:
                    self.clients.remove(client)
                except ValueError:
                    pass

            self.tasks.task_done()

        self.tasks.join()

        # BrokenPipeError, 
        # ConnectionResetError, 
        # websockets.exceptions.ConnectionClosedOK, 
        # websockets.exceptions.ConnectionClosedError, 
        # ConnectionResetError, 
        # RuntimeError 

    def add_client(self, client):
        self.lock.acquire()
        self.clients.append(client)
        self.lock.release()

    def send_message(self, client, message):
        self.tasks.put((client, message))

    def send_message_to_all(self, message, event=False):

        if not event:

            for client in self.clients:
                self.tasks.put((client, message))

            return

        for client in filter(lambda x: x.is_ready(), self.clients):
            self.tasks.put((client, message))

    def process_request(self, client, data):

        if not ('request' in data or 'response' in data):
            return

        if not 'api' in data:
            self.send_message(client, "{'response' : 'get_api_v'}")

        args = {}

        if 'args' in data:
            args = data['args']

        if 'request' in data:

            response = {
                'response': data['request'],
                'args': {}
            }

            if data['request'] == 'is_alive':
                self.send_message(client, "{'response' : 'is_alive'}")
                return

            elif data['request'] == 'set_ready':

                if 'status' in args:
                    client.set_ready(args['status'])
                    return

            elif data['request'] == 'get_struct':
                response['struct'] = self.struct
                self.send_message(client, json.dumps(response))
                return

            elif data['request'] == 'get_short_struct':
                response['struct'] = self.short_struct
                self.send_message(client, json.dumps(response))
                return

            # elif data['request'] == 'get_classes':
            #     classes = list()
            #     map(lambda i: classes.extend(i), self.struct[1])
            #     response['classes'] = classes
            #     self.send_message(client, json.dumps(response))
            #     return

            elif data['request'] == 'get_object':

                if 'id' in args:
                    obj = self.program.object_manager.get_object_by_id(args["id"])
                    response['object'] = {}
                    response['object']['name'] = obj.get_name()
                    response['object']['short_name'] = obj.get_short_name()
                    self.send_message(client, json.dumps(response))
                    return
            
            elif data['request'] == 'get_shortname_class':

                if 'class' in args:
                    response['short_name'] = self.program.object_manager.shortnames_classes[args["class"]]
                    self.send_message(client, json.dumps(response))
                    return

            elif data['request'] == 'get_date_bounds':
                response['bounds'] = self.program.time_handler.get_date_borders()
                self.send_message(client, json.dumps(response))
                return

            elif data['request'] == 'get_values':
                response['objects'] = self.program.object_manager.get_poll_dict()
                self.send_message(client, json.dumps(response))
                return

            elif data['request'] == 'poll':
                response['objects'] = self.program.object_managet.get_poll_dict()
                self.send_message(client, json.dumps(response))
                return

            elif data['request'] == 'get_stats':

                if 'day' in args:
                    response['stats'] = self.program.statistics.get_day_data(args['day'])
                    self.send_message(client, json.dumps(response))
                    return

                if 'month' in args:
                    response['stats'] = self.program.statistics.get_month_data(args['month'])
                    self.send_message(client, json.dumps(response))
                    return

                if 'year' in args:
                    response['stats'] = self.program.statistics.get_year_data(args['year'])
                    self.send_message(client, json.dumps(response))
                    return

            elif data['request'] == 'events':
                pass

            self.send_message(client, '{"response":"error"}')


class ActionManager(Block, Thread):

    def __init__(self, program):
        Thread.__init__(self)
        Block.__init__(self, "ActionManager")
        self.set_color('turquoise')

        self.program = program
        self.vars = program.user_vars

        from actions import actions
        self.list_of_actions = actions

        self.tasks = Queue()
        self.daemon = True

    def add_task(self, name, args):
        self.tasks.put((name, args))

    def run(self):

        self.log_msg(80, with_name=False)

        while self.program.get_status():

            name, args = self.tasks.get()

            if not name in self.list_of_actions:
                self.log_msg(83, (name), color='orange')

                self.tasks.task_done()
                continue

            if name is None:
                self.tasks.task_done()
                continue

            self.log_msg(81, (name))

            try:
                self.list_of_actions[name](self.program, self.vars, args)
            except Exception as e:
                self.log_msg(82, (name, e), color='red')

            self.tasks.task_done()

        self.tasks.join()


class TaskManager(Block):

    class Task(Block):

        def __init__(self, config):
            Block.__init__(self, 'TaskManager')
            self.name = config['name']
            self.program = config['program']

            self.set_color('light yellow')

            if 'perform_missed_task' in config:
                self.perform_missed_task = config['perform_missed_tasks']
            else:
                self.perform_missed_task = False

            self.condition = config['condition']
            self.action = config['action']

            self.configurations = config

            self.schedule_task()

        def schedule_task(self):
            eval(f'schedule.{self.condition}.do(self.start)')

        def start(self):
            self.log_msg(92, (self.name))

            self.program.action_manager.add_task(self.action, self.configurations)

    def __init__(self, program):
        Block.__init__(self, 'TaskManager')

        self.name = 'TaskManager'
        self.program = program

        self.set_color('light yellow')

        if not self.__check_config_files():
            return

        self.__prepare_variables()
        self.__create_tasks()

        self.pending_thread = Thread(
            target=self.run_pending,
            name='TaskManager',
            daemon=True
        )

        self.set_ready(True)

    def __check_config_files(self):

        self.log_msg(91, with_name=False)

        def checkExist(path):
            self.log_msg(911, indent=3, no_capitalize=True, with_name=False)
            return os.path.exists(path)

        def checkJSON(path):
            self.log_msg(912, indent=3, no_capitalize=True, with_name=False)
            try:
                with open(path) as f:
                    config = json.load(f)
                return True
            except:
                return False

        def checkFields(path):
            self.log_msg(913, indent=3, no_capitalize=True, with_name=False)

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

            with open(f"{BASE_DIR}/resources/tasks.json") as f:

                fields = json.loads(f.read())['tasks']['fields']

                with open(path) as k:

                    config = json.load(k)

                    for task in config['tasks']:

                        states = list()

                        for field in fields:
                            states.extend(unpackDict(fields, field, task))

                        if False in states:
                            return False

            return True

        def prepareFolders():

            self.log_msg(914, indent=3, no_capitalize=True, with_name=False)

            with open(f"{BASE_DIR}/configs/tasks/config.json") as f:

                config = json.loads(f.read())

                folders = set()

                for task in config['tasks']:
                    if 'folders' in task:
                        folders.update(set([*task['folders']]))

            for folder in folders:

                if '%' in folder:
                    folder = folder % {'name': self.name}

                folder_path = BASE_DIR

                for folder in folder.split('/'):
                    folder_path += '/' + folder
                    if not os.path.isdir(folder_path):
                        os.mkdir(folder_path)

        def prepareFiles():

            self.log_msg(915, indent=3, no_capitalize=True, with_name=False)

            with open(f"{BASE_DIR}/configs/tasks/config.json") as f:

                config = json.loads(f.read())

                files = set()

                for task in config['tasks']:
                    if 'files' in task:
                        files.update(set([*task['files']]))

            for file in files:

                if '%' in file:
                    file = file % {'name': self.name}

                folder_path = f'{BASE_DIR}/{file.split("/")[0]}'

                for folder in file.split('/')[1:]:
                    if not os.path.isdir(folder_path):
                        os.mkdir(folder_path)
                    folder_path += '/' + folder

                if not os.path.isfile(file):
                    os.system(f'touch {BASE_DIR}/{file}')

        file = f'{BASE_DIR}/configs/tasks/config.json'

        if not checkExist(file):
            self.log_msg(917, (MESSAGES['9171']), with_name=False, color='red')
            return False

        if not checkJSON(file):
            self.log_msg(917, (MESSAGES['9172']), with_name=False, color='red')
            return False

        if not checkFields(file):
            self.log_msg(917, (MESSAGES['9173']), with_name=False, color='red')
            return False

        prepareFolders()
        prepareFiles()

        self.log_msg(916, with_name=False)

        return True

    def __prepare_variables(self):
        self.tasks = list()

    def __create_tasks(self):

        for config in json.load(open(f'{BASE_DIR}/configs/tasks/config.json'))['tasks']:
            config = {**config, 'program': self.program}

            self.tasks.append(self.Task(config))

    def start(self):

        if not self.is_ready():
            return

        self.log_msg(90, with_name=False)

        # self.pending_thread.start()

    def run_pending(self):

        while self.program.get_status():
            schedule.run_pending()
            time.sleep(1)
