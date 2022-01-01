import time
import datetime


def getSeconds(x):
    return time.mktime(time.strptime(x, '%d-%b-%Y'))


def Time(seconds=False):
    if seconds:
        return time.localtime()
    else:
        return time.strftime("%H:%M:%S", time.localtime())


def Date(seconds=None):
    return time.strftime("%d-%b-%Y", time.localtime(seconds))


def Yesterday():
    return (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%d-%b-%Y")


def get_bounds(day):
    if isinstance(day, str):
        day = datetime.datetime.strptime(day, "%d-%b-%Y")
    elif isinstance(day, datetime.datetime):
        day = datetime.datetime.strptime(day.strftime("%d-%b-%Y"), "%d-%b-%Y")

    bounds = list()

    for i in range(0, 25):
        bounds.append(day)
        day += datetime.timedelta(hours=1)

    return bounds


def get_current_hour():
    return datetime.datetime.now().hour


def get_last_hour():
    return (datetime.datetime.now() - datetime.timedelta(hours=1)).hour
