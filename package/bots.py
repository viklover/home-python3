import os
import time
import json
import datetime
import traceback

import vk_api
import telebot

from . import BASE_DIR, CONFIG, MESSAGES
from .db import Database
from .funcs import get_type_list
from .block import Block

from random import randint

from threading import Thread, Lock

from vk_api import VkApi, VkUpload
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType


class Bot(Block, Thread):

    def __init__(self, program, name):
        Block.__init__(self, name.capitalize())
        Thread.__init__(self)

        self.name = name
        self.program = program
        self.daemon = True

        self.tasks = []
        self.lock = Lock()

        self.tasks_thread = Thread(target=self.tasks_loop, daemon=True)
        self.was_started = False

        self.database = Database(f'{BASE_DIR}/databases/{name}', log_dir=f'{BASE_DIR}/logs')
        self.configurations = json.load(open(f'{BASE_DIR}/configs/{name}/config.json'))

        self.set_color('light blue')

        self.__initilize()

    def __initilize(self):

        self.status_checking = self.__check_config_files()

        if not self.status_checking:
            print('ошибка проверки конфиг файлов')
            return

        self.__prepare_variables()
        self.__prepare_table()

    def __check_config_files(self):

        def checkExist(path):
            self.log_msg(141, indent=3, no_capitalize=True, with_name=False)
            return os.path.exists(path)

        def checkJSON(path):
            self.log_msg(142, indent=3, no_capitalize=True, with_name=False)
            try:
                with open(path) as f:
                    config = json.load(f)
                return True
            except:
                return False

        def checkFields(path):
            self.log_msg(144, indent=3, no_capitalize=True, with_name=False)

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

            with open(f"{BASE_DIR}/resources/bots.json") as f:

                string = f.read()

                fields = {
                    **json.loads(string)['bot']['fields'],
                    **json.loads(string)[self.name]['fields']
                }

                with open(path) as k:

                    config = json.load(k)

                    states = list()

                    for field in fields:
                        states.extend(unpackDict(fields, field, config))

                    if False in states:
                        return False

            return True

        def prepareFiles():

            self.log_msg(146, indent=3, no_capitalize=True, with_name=False)

            with open(f"{BASE_DIR}/resources/bots.json") as f:

                config = json.loads(f.read())

                files = set()

                if 'files' in config['bot']:
                    files.update(set([*config['bot']['files']]))

                if 'files' in config[self.name]:
                    files.update(set([*config[self.name]['files']]))

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

        def prepareFolders():

            self.log_msg(145, indent=3, no_capitalize=True, with_name=False)

            with open(f"{BASE_DIR}/resources/bots.json") as f:

                config = json.loads(f.read())

                folders = set()

                if 'folders' in config['bot']:
                    folders.update(set([*config['bot']['folders']]))

                if 'folders' in config[self.name]:
                    folders.update(set([*config[self.name]['folders']]))

            for folder in folders:

                if '%' in folder:
                    folder = folder % {'name': self.name}

                folder_path = BASE_DIR

                for folder in folder.split('/'):
                    folder_path += '/' + folder
                    if not os.path.isdir(folder_path):
                        os.mkdir(folder_path)

        self.log_msg(60, with_name=False)

        with open(f'{BASE_DIR}/resources/bots.json') as f:
            config = json.load(f)

        if not self.name in config:
            return None

        file = f'{BASE_DIR}/configs/{self.name}/config.json'

        if not checkExist(file):
            self.log_msg(603, (MESSAGES['1481']), color='red', with_name=False)
            return False

        if not checkJSON(file):
            self.log_msg(603, (MESSAGES['1482']), color='red', with_name=False)
            return False

        if not checkFields(file):
            self.log_msg(603, (MESSAGES['604']), color='red', with_name=False)
            return False

        prepareFolders()
        prepareFiles()

        return True

    def __prepare_variables(self):

        self.keyboards = {None: None}

        self.logged_users = list()
        self.category_users = dict()

        self.user_categories = ['all']
        self.user_categories.extend(list(map(list, zip(*self.configurations['user_categories'])))[0])

        self.categories_start_values = dict()

        for category, value in self.configurations['user_categories']:
            self.categories_start_values[category] = value
            self.category_users[category] = list()

        with open(f'{BASE_DIR}/resources/bots.json') as f:
            self.format_db = json.load(f)[self.name]['database']

    def __prepare_table(self):
        database = self.format_db

        for category in self.user_categories:
            if category != 'all':
                database['chats'][category] = "BOOL"

        columns = dict()

        for table in database:
            self.database.create(table, database[table])
            columns[table] = self.database.pragma_table(table)

        # ADD MISSING COLUMNS

        for table in database:
            for column in database[table]:
                if column not in columns[table]:
                    self.database.add_column(table, column, database[table][column])

    def __import_settings(self):
        config = self.configurations

        self.actions = list()

        for action in config['actions']:
            if action[0] == '~':
                self.actions.append([1, action[1:], config['actions'][action]])
                continue
            self.actions.append([0, action, config['actions'][action]])

        with open(f'{BASE_DIR}/configs/{self.name}/token') as f:
            self.token = f.read()

    def __import_chats(self):
        pass

    def add_task(self, action, args, kwargs={}):
        self.lock.acquire()
        self.tasks.append((action, args, kwargs))
        self.lock.release()

    def tasks_loop(self):

        while self.program.get_status():

            self.lock.acquire()

            for index, task in enumerate(self.tasks):

                action, args, kwargs = task

                if action == 'send_message':
                    chat_id, text = args

                    print(self.keyboards)

                    if 'keyboard' in kwargs and not kwargs['keyboard'] in self.keyboards:
                        self.log_msg(633, (kwargs['keyboard']))
                        keyboard = None
                    elif 'keyboard' not in kwargs:
                        keyboard = None
                    else:
                        keyboard = kwargs['keyboard']

                    if isinstance(chat_id, str):
                        if chat_id.isdigit():
                            chat_id = int(chat_id)

                    try:
                        self.send_message(chat_id, text, self.keyboards[keyboard])
                    except Exception:
                        continue

                    del self.tasks[index]

            self.lock.release()

            time.sleep(0.6)

    def is_available(self):
        pass

    def run_action(self, name, event={}):

        if name is None:
            return

        args = {**self.configurations, **event}

        self.program.action_manager.add_task(name, args)

    def run(self):
        pass


class VKBot(Bot):

    class Chat:

        def __init__(self, vkbot, chat_id):
            self.reg_code = None
            self.id = chat_id
            self.vkbot = vkbot
            self.name = None
            self.for_clients = False
            self.logged = None

            self.database = Database(f'{BASE_DIR}/databases/{vkbot.name}', log_dir=f'{BASE_DIR}/logs')

            self.__prepare_variables()

        def __prepare_variables(self):

            self.logged = self.database.check('chats', conds=[('id', self.id), ('logged', True)], unpack=True)
            self.for_clients = self.database.check('chats', conds=[('id', self.id), ('for_clients', True)])

            if not self.logged:
                if not self.database.select('chats', ['code'], [('id', self.id)], unpack=True):
                    self.reg_code = randint(100000, 999999)
                    self.database.insert('chats', [('id', self.id), ('code', self.reg_code), ('for_clients', False),
                                                   ('logged', False)])
                    return
                self.reg_code = self.database.last_response

        def is_logged(self):
            return bool(self.logged)

        def log_in(self, code):

            if not isinstance(code, int):
                return False

            if not code == self.reg_code:
                self.reg_code = randint(100000, 999999)
                self.database.update('chats', [('code', self.reg_code)], [('id', self.id)])
                return False

            self.logged = True
            self.database.update('chats', [('logged', True)], [('id', self.id)])

            if not self in self.vkbot.logged_users:
                self.vkbot.logged_users.append(self)

            if 'main' in self.vkbot.keyboards:
                self.database.update('chats', [('keyboard', 'main')], [('id', self.id)])

            # SET START VALUES OF CATEGORIES
            columns = []

            for category, value in self.vkbot.categories_start_values.items():
                columns.append((category, value))

            self.database.update('chats', columns, [('id', self.id)])

            return True

        def get_reg_code(self):
            return self.reg_code

        def get_id(self):
            return self.id

        def send_message(self, text):
            self.vkbot.add_task('send_message', [self.id, text])

        def set_category(self, category, value):

            if category in self.vkbot.user_categories and category != 'all':
                self.database.update('chats', [(category, value)], [('id', self.id)])

                if value:
                    self.vkbot.log_msg(651, (self.id, category))
                    if self not in self.vkbot.category_users[category]:
                        self.vkbot.category_users[category].append(self)
                else:
                    self.vkbot.log_msg(652, (self.id, category))
                    if self in self.vkbot.category_users[category]:
                        self.vkbot.category_users[category].remove(self)

                return

            self.vkbot.log_msg(6501, (category))

        def set_chat_for_clients_state(self, value):
            self.for_clients = value
            self.database.update('chats', ('for_clients', value), [('id', self.id)])

    def __init__(self, program):
        Bot.__init__(self, program, 'vkbot')
        
        # TASK MANAGER
        self.vk = None
        self.longpoll = None
        self.upload = None
        self.session = None

        self.set_name('VKBot')

        if self.__check_keyboard_config():
            self.__init_keyboards()

        self.__import_settings()
        self.__import_chats()

        self.__prepare_tasks()        

    def __import_settings(self):

        self._Bot__import_settings()

        with open(f'{BASE_DIR}/configs/{self.name}/group_id') as f:
            try:
                self.group_id = int(f.read())
            except ValueError:
                self.group_id = None
                self.log_msg(605, ('configs/vkbot/group_id'), color='red')

    def __import_chats(self):

        self.log_msg(640, with_name=False)

        self.chats = dict()
        self.chats_for_clients = list()

        columns = ['id', 'for_clients', *self.user_categories.copy()[1:]]

        for i in self.database.select('chats', columns):
            id, for_clients, categories = i[0], i[1], dict(zip(columns[2:], i[2:]))

            self.chats[id] = self.Chat(self, id)

            if self.chats[id].is_logged():
                self.logged_users.append(self.chats[id])

            if for_clients:
                self.chats_for_clients.append(self.chats[id])
                return

            for category, value in categories.items():
                if value == True and category in self.user_categories:
                    self.category_users[category].append(self.chats[id])

    def __check_keyboard_config(self):

        self.log_msg(630, with_name=False)

        with open(f'{BASE_DIR}/resources/bots.json') as f:
            config = json.load(f)['vkbot']['keyboard']

        keyboards = json.load(open(f'{BASE_DIR}/configs/{self.name}/config.json'))['keyboards']

        for keyboard in keyboards:

            name = keyboard
            keyboard = keyboards[name]

            for field in config['fields']:

                if field not in keyboard or not isinstance(keyboard[field], get_type_list(config['fields'][field])):
                    self.log_msg(631, (name, MESSAGES['6305'] % field), color='red', with_name=False,
                                 no_capitalize=True)
                    return False

            inline = keyboard['inline']
            kind = 'inline' if inline else 'standart'
            size = config['sizes']['inline' if inline else 'standart']
            max_count = config['count']['inline' if inline else 'standart']

            count = 0

            if (not len(keyboard['lines']) <= size[1]) or any(map(lambda x: len(x) > size[0], keyboard['lines'])):
                self.log_msg(631, (name, MESSAGES['6301'] % (kind, 'x'.join(map(str, size)))), color='red',
                             with_name=False, no_capitalize=True)
                return False

            for i, line in enumerate(keyboard['lines'], start=1):

                for button in line:

                    count += 1

                    if 'type' not in button or button['type'] not in config['types']:
                        self.log_msg(631, (name, MESSAGES['6302'] % i), color='red', with_name=False,
                                     no_capitalize=True)
                        return False

                    for field in config['types'][button['type']]:

                        is_not_required = "!" in field

                        if is_not_required:
                            n_field = field[1:]

                            if field not in button:
                                continue

                            if not isinstance(button[n_field], get_type_list(config['types'][button['type']][field])):
                                self.log_msg(631, (name, MESSAGES['6303'] % i), color='red', with_name=False,
                                             no_capitalize=True)
                                return False

                            continue

                        if (field not in button) or (
                                not isinstance(button[field], get_type_list(config['types'][button['type']][field]))):
                            self.log_msg(631, (name, MESSAGES['6303'] % i), color='red', with_name=False,
                                         no_capitalize=True)
                            return False

                    if 'color' in button and not button['color'] in config['colors']:
                        self.log_msg(6306, (button['color']))
                        return False

            if count > max_count:
                self.log_msg(631, (name, MESSAGES['6304'] % (kind, max_count)), color='red', with_name=False,
                             no_capitalize=True)
                return False

        self.log_msg(632, with_name=False)
        return True

    def __init_keyboards(self):

        self.log_msg(641, with_name=False)

        add_buttons = json.load(open(f'{BASE_DIR}/resources/bots.json'))[self.name]['keyboard']['add_funcs']
        keyboards = json.load(open(f'{BASE_DIR}/configs/{self.name}/config.json'))['keyboards']

        for keyboard in keyboards:

            inline = keyboards[keyboard]['inline']
            one_time = keyboards[keyboard]['one_time']

            body = VkKeyboard(inline=inline, one_time=one_time)

            for i, line in enumerate(keyboards[keyboard]['lines']):

                if i:
                    body.add_line()

                for button in line:

                    properties = button.copy()

                    func, args = add_buttons[button['type']]

                    args_string = str()

                    for j, arg in enumerate(args):
                        if j: args_string += ', '
                        args_string += f'properties["{arg}"]'
                        if arg in button: del button[arg]

                    kwargs_string = str()

                    del button['type']

                    for j, kwarg in enumerate(button):
                        if (len(args_string) and not j) or j:
                            kwargs_string += ', '
                        if kwarg != 'color':
                            kwargs_string += f'{kwarg}=properties["{kwarg}"]'
                        else:
                            kwargs_string += f'{kwarg}=VkKeyboardColor.{properties[kwarg]}'

                    eval(f'body.{func}({args_string}{kwargs_string})')

            self.keyboards[keyboard] = body.get_keyboard()

        self.keyboards['empty'] = VkKeyboard().get_empty_keyboard()

    def __prepare_tasks(self):

        if self.program.shutdown_reason is None:
            return

        reason = self.program.shutdown_reason['reason']

        if 'closed by' in reason:
            user_id = int(reason.split('closed by ')[1])
            date = datetime.datetime.now().strftime('%d-%b-%Y %H:%M:%S')

            self.add_task('send_message', [user_id, f'Программа запущена'], {})

        if 'rebooted by' in reason:
            user_id = int(reason.split('rebooted by ')[1])
            date = datetime.datetime.now().strftime('%d-%b-%Y %H:%M:%S')

            self.add_task('send_message', [user_id, f'Система перезагружена'], {})

    def send_message_to_all(self, message):
        for user in self.logged_users:
            self.add_task('send_message', [user.get_id(), message])

    def send_message_to_category(self, category, message):
        for user in self.category_users[category]:
            self.add_task('send_message', [user.get_id(), message])

    def send_message(self, chat_id, text, keyboard):

<<<<<<< HEAD
        self.session.messages.send(
            peer_id=chat_id,
            message=text,
            random_id=randint(1, 121314),
            keyboard=keyboard
        )
=======
                if action == 'send_message':
                    chat_id, text = args

                    if 'keyboard' in kwargs and not kwargs['keyboard'] in self.keyboards:
                        self.log_msg(633, (kwargs['keyboard']))
                        keyboard = None
                    elif 'keyboard' not in kwargs:
                        keyboard = None
                    else:
                        keyboard = kwargs['keyboard']

                    if isinstance(chat_id, str):
                        if chat_id.isdigit():
                            chat_id = int(chat_id)

                    try:
                        send_message(chat_id, text, self.keyboards[keyboard])
                    except Exception:
                        traceback.print_exc()

                    del self.tasks[index]

            self.lock.release()

            time.sleep(0.6)
>>>>>>> experiment

    def run(self):

        time.sleep(1)

        if not CONFIG['bots'] or self.group_id is None or self.status_checking:
            return

        was_errors = False

        while self.program.get_status():

            if not was_errors:
                self.log_msg(6100)

            try:
                self.vk = VkApi(token=self.token)
                self.longpoll = VkBotLongPoll(self.vk, self.group_id)
                self.upload = VkUpload(self.vk)
                self.session = self.vk.get_api()
            except Exception:
                if not was_errors:
                    self.log_msg(6101, (MESSAGES['6104']), color='orange')
                    was_errors = True
                time.sleep(15)

            else:

                if was_errors:
                    self.log_msg(6102)
                    was_errors = False
                else:
                    self.log_msg(6103)

                if not self.was_started:
                    self.tasks_thread.start()
                    self.was_started = True

                try:
                    self.listen_longpoll()
                except Exception:
                    traceback.print_exc()
                    continue

    def listen_longpoll(self):

        def new_message(event):
            text = event.object.text.lower()
            chat_id = event.object.peer_id
            user_id = event.object.from_id

            chat = self.Chat(self, chat_id)

            args = {
                'text': text,
                'chat_id': chat_id,
                'user_id': user_id,
                'chat' : chat
            }

            if not chat.is_logged():

                if not len(text) == 6 and not text.isdigit():
                    user = self.session.users.get(user_ids=user_id)[0]
                    self.log_msg(6201, (user['first_name'], chat.get_reg_code()), no_capitalize=True)
                    self.add_task('send_message', [chat_id, 'Введите код: '])
                    return

                if not chat.log_in(int(text)):
                    user = self.session.users.get(user_ids=user_id)[0]
                    self.log_msg(6201, (user['first_name'], chat.get_reg_code()), no_capitalize=True)
                    self.add_task('send_message', [chat_id, 'Введите код: '])
                    return

                self.add_task('send_message', [chat_id, MESSAGES['6202']])

            if chat_id in self.chats_for_clients:
                
                try:
                    json_data = json.loads(text)
                    self.program.client_manager.process_request(chat, json_data)
                except:
                    pass

            return

            for mode, message, action in self.actions:

                if not mode and text in message:
                    self.run_action(action, args)
                    break

                if message in text:
                    self.run_action(action, args)
                    break

        for event in self.longpoll.listen():

            if event.type == VkBotEventType.MESSAGE_NEW:
                new_message(event)


class TeleBot(Bot):

    class Chat:

        def __init__(self, telebot, chat_id):
            self.reg_code = None
            self.id = chat_id
            self.telebot = telebot
            self.name = None
            self.for_clients = False
            self.logged = None

            self.database = Database(f'{BASE_DIR}/databases/{telebot.name}', log_dir=f'{BASE_DIR}/logs')

            self.__prepare_variables()

        def __prepare_variables(self):

            self.logged = self.database.check('chats', conds=[('id', self.id), ('logged', True)], unpack=True)
            self.for_clients = self.database.check('chats', conds=[('id', self.id), ('for_clients', True)])

            if not self.logged:
                if not self.database.select('chats', ['code'], [('id', self.id)], unpack=True):
                    self.reg_code = randint(100000, 999999)
                    self.database.insert('chats', [('id', self.id), ('code', self.reg_code), ('for_clients', False),
                                                   ('logged', False)])
                    return
                self.reg_code = self.database.last_response

        def is_logged(self):
            return bool(self.logged)

        def log_in(self, code):

            if not isinstance(code, int):
                return False

            if not code == self.reg_code:
                self.reg_code = randint(100000, 999999)
                self.database.update('chats', [('code', self.reg_code)], [('id', self.id)])
                return False

            self.logged = True
            self.database.update('chats', [('logged', True)], [('id', self.id)])

            if not self in self.telebot.logged_users:
                self.telebot.logged_users.append(self)

            if 'main' in self.telebot.keyboards:
                self.database.update('chats', [('keyboard', 'main')], [('id', self.id)])

            # SET START VALUES OF CATEGORIES
            columns = []

            for category, value in self.telebot.categories_start_values.items():
                columns.append((category, value))

            self.database.update('chats', columns, [('id', self.id)])

            return True

        def get_reg_code(self):
            return self.reg_code

        def get_id(self):
            return self.id

        def send_message(self, text):
            self.telebot.add_task('send_message', [self.id, text])

        def set_category(self, category, value):

            if category in self.telebot.user_categories and category != 'all':
                self.database.update('chats', [(category, value)], [('id', self.id)])

                if value:
                    self.telebot.log_msg(651, (self.id, category))
                    if self not in self.telebot.category_users[category]:
                        self.telebot.category_users[category].append(self)
                else:
                    self.telebot.log_msg(652, (self.id, category))
                    if self in self.telebot.category_users[category]:
                        self.telebot.category_users[category].remove(self)

                return

            self.telebot.log_msg(6501, (category))

    def __init__(self, program):
        Bot.__init__(self, program, 'telebot')

        self._Bot__import_settings()

        self.set_name('TeleBot')

    def run(self):

        time.sleep(1)

        if not CONFIG['bots'] or not self.status_checking:
            return

        self.bot = telebot.TeleBot(self.token)

        self.init_handlers()

        self.tasks_thread.start()

        while self.program.get_status():
            try:
                self.listen_longpoll()
            except (ConnectionError, AttributeError):
                self.log_msg(6101, (MESSAGES['6104']), color='orange')
                time.sleep(5)

    def init_handlers(self):

        @self.bot.message_handler(commands=['start', 'help'])
        def send_welcome(message):
            self.bot.reply_to(message, "Howdy, how are you doing?")

        @self.bot.message_handler(func=lambda message: True)
        def new_message(message):
            
            text = message.text.lower()
            chat_id = message.chat.id
            user_id = message.from_user.id

            chat = self.Chat(self, chat_id)

            args = {
                'text': text,
                'chat_id': chat_id,
                'user_id': user_id,
                'chat' : chat
            }

            if not chat.is_logged():

                if not len(text) == 6 and not text.isdigit():
                    first_name = message.from_user.first_name
                    self.log_msg(6201, (first_name, chat.get_reg_code()), no_capitalize=True)
                    self.add_task('send_message', [chat_id, 'Введите код: '])
                    return

                if not chat.log_in(int(text)):
                    first_name = message.from_user.first_name
                    self.log_msg(6201, (first_name, chat.get_reg_code()), no_capitalize=True)
                    self.add_task('send_message', [chat_id, 'Введите код: '])
                    return

                self.add_task('send_message', [chat_id, MESSAGES['6202']], {'keyboard': 'main'})

            for mode, message, action in self.actions:

                if not mode and text in message:
                    self.run_action(action, args)
                    break

                if message in text:
                    self.run_action(action, args)
                    break

    def send_message(self, chat_id, text, keyboard=None):
        self.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)

    def listen_longpoll(self):
        self.bot.infinity_polling()


    #    # TASK MANAGER
    #     self.vk = None
    #     self.longpoll = None
    #     self.upload = None
    #     self.session = None
    #     self.tasks = list()
    #     self.tasks_thread = Thread(target=self.tasks_loop, daemon=True)

    #     self.was_started = False

    #     self.lock = Lock()

    #     self.set_name('VKBot')

    #     if self.__check_keyboard_config():
    #         self.__init_keyboards()

    #     self.__import_settings()
    #     self.__import_chats()

    #     self.__prepare_tasks()      


