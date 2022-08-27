import re
import os
import time
import datetime

"""
    Здесь можно импортировать любые модули:
        import <module>


    def имя_функции(program):
        <алгоритм>

    actions = {
        "<название_сценария>" : <имя_функции>,
        ...
    }

"""


def clear_logs(program, vars, args):
    start_date = datetime.datetime.now()
    matches = "|".join(
        [(start_date - datetime.timedelta(days=i)).strftime("%d-%b-%Y") for i in range(0, args['save_days'] + 1)])

    with os.scandir('my_directory/') as entries:
        for file in filter(lambda i: '.log' in i, entries):

            print(file.name)

            with open(file.name, "r") as f:
                data = f.readlines()

            with open(file.name, "w") as f:
                lines = list()

                for line in reversed(data):
                    if not any(re.findall(matches, line, re.IGNORECASE)):
                        break
                    lines.append(line)

                f.writelines(reversed(lines))


def play_track(track):
    os.system(f"alsa play {track}")


def send_str_poll(program, vars, args):
    args['chat'].send_message(program.object_manager.get_poll_string())
    # program.vkbot.add_task('send_message', [args['chat_id'], program.object_manager.get_poll_string()],
    #                        {'keyboard': 'main'})


def send_stats(program, vars, args):
    args['chat'].send_message(program.statistics.get_stats_from_str(args['text']))
    # program.vkbot.add_task('send_message', [args['chat_id'], program.statistics.get_stats_from_str(args['text'])],
    #                        {'keyboard': 'main'})


def send_security_choice(program, vars, args):
    args['chat'].send_message('Охрана')
    # program.vkbot.add_task('send_message', [args['chat_id'], 'Охрана'], {'keyboard': 'security'})

def set_chat_for_clients_state(program, vars, args):

    if 'клиентским' in args['text']:
        args['chat'].set_chat_for_clients_state(False)
    
    if 'пользовательским' in args['text']:
        args['char'].set_chat_for_clients_state(True)

    args['chat'].send_message('Категория чата изменена')

def set_security_category(program, vars, args):
    value = False

    if 'включить' in args['text']:
        value = True

    args['chat'].set_category('security', value)
    args['chat'].send_message('Настройки были изменены')


def reboot_program(program, vars, args):
    program.vkbot.add_task('send_message', [args['chat_id'], "Перезагрузка RPi"], {})

    time.sleep(5)

    os.system('sudo reboot')
    program.shutdown('{"reason":"rebooted by ' + str(args["user_id"]) + '"}')


def shutdown_program(program, vars, args):
    program.vkbot.add_task('send_message', [args['chat_id'], "Выключение программы"], {})

    time.sleep(5)

    program.shutdown('{"reason":"closed by ' + str(args["user_id"]) + '"}')


actions = {
    "send_str_poll": send_str_poll,
    "send_stats": send_stats,
    "send_security_choice": send_security_choice,
    "set_security_category": set_security_category,
    "reboot_program": reboot_program,
    "shutdown_program": shutdown_program,
    "clear_logs": clear_logs,
    "chat_for_clients": set_chat_for_clients_state
}
