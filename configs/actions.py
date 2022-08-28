
import os
import time

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

def play_track(track):
    os.system(f"aplay {track}")

def septic_on(program, vars, args):

    if vars["septic"] is None or (time.time() - vars["septic"]) >= 86400:

        vars["septic"] = time.time()

        program.vkbot.send_message_to_all('Септик наполнен')

def septic_status_alert(program, vars, args):

    if vars['septic'] is None:
        return

    obj = program.object_manager.get_object_by_id('70')

    if obj.get_status():
        program.vkbot.send_message_to_all('Септик всё ещё наполнен')

def septic_off(program, vars, args):
    pass

def f1_on(program, vars, args):
    program.vkbot.send_message_to_all('АВАРИЯ! Ошибка F1 у Котла')

def f1_off(program, vars, args):
    program.vkbot.send_message_to_all('Авария устранена')


def send_str_poll(program, vars, args):
    program.vkbot.add_task('send_message', [args['chat_id'], program.object_manager.get_poll_string()], {'keyboard' : 'main'})
    #poll = program.object_manager.get_poll_string()
    #program.vkbot.send_all_message(poll)

def send_stats(program, vars, args):
    program.vkbot.add_task('send_message', [args['chat_id'], program.statistics.get_stats_from_str(args['text'])], {'keyboard' : 'main'})

def f4_on(program, vars, args):
    program.vkbot.send_message_to_all('Перегрев во время нагрева: ' + vars['f4_reason'])

def f4_off(program, vars, args):
    program.vkbot.send_message_to_all('Авария устранена')


def send_security_choice(program, vars, args):
    program.vkbot.add_task('send_message', [args['chat_id'], 'Охрана'], {'keyboard': 'security'})

def set_chat_for_clients_state(program, vars, args):

    if 'клиентским' in args['text']:
        args['chat'].set_chat_for_clients_state(True)
    
    if 'пользовательским' in args['text']:
        args['chat'].set_chat_for_clients_state(False)

    args['chat'].send_message('Принял ваши настройки')

def set_security_category(program, vars, args):

    value = False

    if 'включить' in args['text']:
        value = True

    program.vkbot.chats[args['chat_id']].set_category('security', value)
    program.vkbot.chats[args['chat_id']].send_message('Настройки были изменены')

def set_stats_category(program, vars, args):
    
    value = False

    if 'включить' in args['text']:
        value = True

    program.vkbot.chats[args['chat_id']].set_category('stats', value)
    program.vkbot.chats[args['chat_id']].send_message('Настройки были изменены')



def send_msg_m4_on(program, vars, args):
    #program.vkbot.send_message_to_all('Болер долго нагревается')
    pass

def send_msg_m4_off(program, vars, args):
    #program.vkbot.send_message_to_all('Нагрев болера в норме')
    pass




def send_msg_1005_on(program, vars, args):
    program.vkbot.send_message_to_all('Низкая темература в бане')
    
def send_msg_1005_off(program, vars, args):
    # class, podklass, vars method (deistvie)
    program.vkbot.send_message_to_all('Темература в бане - норма')
    
    
def m4_count_off(program, vars, args):
    
    m4 = program.object_manager.get_object_by_id(76)
    kotel = program.object_manager.get_object_by_id(96)
    
    # data = m4.get_str_day_data('22-Feb-2019')
    
    if kotel.get_status() != True or not m4.get_status():
        return False
    
    if m4.get_current_duration() > kotel.get_current_duration():
        boler_heat_pause_dur = m4.get_current_duration() - (kotel.get_poll()[2] - m4.get_poll()[2])
    else:
        boler_heat_pause_dur = kotel.get_current_duration() - (m4.get_poll()[2] - kotel.get_poll()[2])
    
    ratio = m4.get_current_duration() / boler_heat_pause_dur
    
    boler_heat_time = m4.get_current_duration()
    
    # ratio - отношение между длительностью паузы при работе котла при нагреве болера, и общей длительностью M4
    
    # раскомментируй строчку ниже, чтобы выводить значение ratio 
    program.log(f'RATIO = {ratio}')
    program.log(f'BOLER_HEAT_PAUSE = {boler_heat_pause_dur}') 
    program.log(f'BOLER_HEAT_TIME = {boler_heat_time}')
    
def send_yesterday_stats(program, vars, args):
    program.vkbot.send_message_to_category('stats', program.statistics.get_stats_from_str('cтатистика за вчера'))
    
def send_stats_choice(program, vars, args):
    program.vkbot.add_task('send_message', [args['chat_id'], 'Eжедневные уведомления'], {'keyboard' : 'stats'})
    
    
def reboot_program(program, vars, args):

    program.vkbot.add_task('send_message', [args['chat_id'], "Перезагрузка RPi"], {})

    time.sleep(5)

    os.system('sudo reboot')
    program.shutdown('{"reason":"rebooted by '+str(args["user_id"])+'"}')
    
def shutdown_program(program, vars, args):
    
    program.vkbot.add_task('send_message', [args['chat_id'], "Выключение программы"], {})
    
    time.sleep(5)
    
    # shutdown the PROGRAM
    program.shutdown('{"reason":"closed by '+str(args["user_id"])+'"}')




actions = {
    "send_str_poll": send_str_poll,
    "send_stats": send_stats,
    "send_security_choice": send_security_choice,
    "set_security_category": set_security_category,
    "reboot_program": reboot_program,
    "shutdown_program": shutdown_program,
    "chat_for_clients": set_chat_for_clients_state,
    "fldoor_off" : lambda x, y, z: play_track('/home/pi/home-python3/audio/FlDoor/close.wav'),
    "fldoor_on" : lambda x, y, z: play_track('/home/pi/home-python3/audio/FlDoor/open.wav'),
    "door_off" : lambda x, y, z: play_track('/home/pi/home-python3/audio/Door/close.wav'),
    "door_on" : lambda x, y, z: play_track('/home/pi/home-python3/audio/Door/open.wav'),
    "send_stats_choice": send_stats_choice,
    "septic_status_alert" : septic_status_alert,
    "send_yesterday_stats": send_yesterday_stats,
    "set_stats_category": set_stats_category,
    "f1_on" : f1_on,
    "f1_off" : f1_off,
    "septic_on" : septic_on,
    "septic_off" : septic_off,
    "send_msg_m4_on" : send_msg_m4_on,
    "send_msg_m4_off" : send_msg_m4_off,
    "send_msg_1005_on" : send_msg_1005_on,
    "send_msg_1005_off" : send_msg_1005_off,
    "m4_count_off" : m4_count_off,
    "f4_on" : f4_on,
    "f4_off" : f4_off
}
