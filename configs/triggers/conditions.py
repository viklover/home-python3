import os
import time
import datetime

def check_1001(program, vars):
    return False

def check_1002(program, vars):

    if vars['triger_test_lt'] is None:
        vars['triger_test_lt'] = time.time()
        return False

    if time.time() - vars['triger_test_lt'] > 10:

        if vars['triger_test_status'] is None:
            vars['triger_test_status'] = True
        
        vars['triger_test_status'] = not vars['triger_test_status']

        vars['triger_test_lt'] = time.time()

    return vars['triger_test_status']

def check_1003(program, vars):

    m1 = program.object_manager.get_object_by_id(60)
    m2 = program.object_manager.get_object_by_id(64)
    m3 = program.object_manager.get_object_by_id(68)
    m4 = program.object_manager.get_object_by_id(76)
    kotel = program.object_manager.get_object_by_id(96)

    if kotel.get_status() and kotel.get_current_duration() >= 600:

        conds = []

        conds.append(not m1.get_status() and m1.get_current_duration() >= 600)
        conds.append(not m2.get_status() and m2.get_current_duration() >= 600)
        conds.append(not m3.get_status() and m3.get_current_duration() >= 600)
        conds.append(not m4.get_status() and m4.get_current_duration() >= 600)

        return all(conds)

    return False

def check_1004(program, vars):
    
    """
    # Это попытка посчитать эффективность нагрева болера. И найти слишком большую паузу, 
    # неизбежно возникающую во время работы котла,
    # когда нагревается болер. Чем меньше пауза тем эффективней нагрев.
    # Соответственно, найти слишком долгий нагрев болера.
    # циркул. насос М4  :   *______________________________________________*
    # Котел             :   *__________* пауза   *________* пауза    *_____*  
    #       
    m4 = program.object_manager.get_object_by_id(76)
    kotel = program.object_manager.get_object_by_id(96)
    
    if kotel.get_status() != True or not m4.get_status():
        return False
    
    if m4.get_current_duration() > kotel.get_current_duration():
        boler_heat_pause_dur = m4.get_current_duration() - (kotel.get_poll()[2] - m4.get_poll()[2])
    else:
        boler_heat_pause_dur = kotel.get_current_duration() - (m4.get_poll()[2] - kotel.get_poll()[2])
    
    ratio = m4.get_current_duration() / boler_heat_pause_dur()
    
    boler_heat_time = m4.get_current_duration()
    
    # ratio - отношение между длительностью паузы при работе котла при нагреве болера,  и общей длительностью M4
    
    # раскомментируй строчку ниже, чтобы выводить значение ratio 
    program.log(f'RATIO = {ratio}')
    program.log(f'BOLER_HEAT_PAUSE = {boler_heat_pause_dur}') 
    program.log(f'BOLER_HEAT_TIME = {boler_heat_time}')
 
    if ratio > 3:
        return True
    
    """
    
    return False
    

def check_1005(program, vars):
    
    predbannyk = program.object_manager.get_object_by_id(3569)
    
    value = predbannyk.get_poll()
    
    if value[0] == False:
        return False
    
    # [status, value, vector]
    
    if value[1] < 10.0:
        return True
    
    return False


def check_1006(program, vars):
    
    m4 = program.object_manager.get_object_by_id(76)
    kotel = program.object_manager.get_object_by_id(96)
    kotel_temp = program.object_manager.get_object_by_id(3563)
    
    # kotel.get_status() == True
    if kotel.get_status() and kotel.get_current_duration() >= 5:
        # success, value, vector, stat, _time = data
        
        """
        data:
           0: success
           1: value (temp)
           2: vector (в виде числа: 0 - вниз, 1 - вверх, 2 - =, 3 - None)
           3: statistics (min, max, avg)
           4: time (время последнего считывания)
        """
        
        data = kotel_temp.get_poll()
        
        if data[0] == True and data[1] >= 89.0:
            
            # Здесь мы должны записать причину срабатывания
            
            if m4.get_status() == True:
                
                #перегрев котла во время нагрева болера
                vars['f4_reason'] = 'болера'
                
            else:
            
                #перегрев котла во время нагрева отопления
                vars['f4_reason'] = 'отопления'
            
            return True
    
    return False


conditions = {
    "1001" : check_1001,
    "1002" : check_1002,
    "1003" : check_1003,
    "1004" : check_1004,
    "1005" : check_1005,
    "1006" : check_1006
}
