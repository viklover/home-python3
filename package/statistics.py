import os
import time
import json
import datetime
import schedule
import threading
import subprocess
import multiprocessing

from queue import Queue

from . import BASE_DIR, MESSAGES, MONTHS, STATS
from .db import Database
from .block import Block
from .dates import Date, Yesterday, getSeconds, get_bounds


class Statistics(Block):

    def __init__(self, program):
        Block.__init__(self, "Statistics")
        self.set_color("magenta")
        self.program = program

        self.stats_db = Database(f'{BASE_DIR}/databases/stats', log_dir=f'{BASE_DIR}/logs', block='stats')

    def start(self):
        # self.check_all_days()

        # schedule.every().day.at("00:00").do(self.check_all_days)
        pass

    def check_all_days(self):

        self.log_msg(41)

        list_of_ids = self.program.object_manager.list_of_ids
        names = self.program.object_manager.names

        new_records = 0

        for day, ids in self.__get_mising_records().items():

            if day == Date() or not len(list(filter(lambda i: i in list_of_ids, ids))):
                continue

            if not new_records:
                self.log_msg(42)

            self.log(f'  -  {day}:', with_name=False)

            for id in filter(lambda i: i in list_of_ids, ids):
                obj = self.program.object_manager.get_object_by_id(id)
                obj.count_hour_data(day, and_save=True)

                self.log(names[id], indent=6, with_name=False)

                new_records += 1

        if new_records:
            message = MESSAGES['412'] % new_records
        else:
            message = MESSAGES['411']

        self.log_msg(414, (message))

    def __get_mising_records(self):

        filename = f"{BASE_DIR}/subprograms/data"
        statbuf = os.stat(filename).st_mtime

        process = subprocess.Popen(
            './check_1',
            cwd=f'{BASE_DIR}/subprograms',
            universal_newlines=True
        )

        while process.poll() is None:
            pass

        process.terminate()
        if statbuf == os.stat(filename).st_mtime:
            self.log_msg(413, MESSAGES['4131'], color='red')
            return {}

        return json.load(open(f'{BASE_DIR}/subprograms/data'))

    def __set_missing_records(self):

        process = subprocess.Popen(
            './execute',
            cwd=f'{BASE_DIR}/subprograms',
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            universal_newlines=True
        )

        while process.poll() is None:
            pass

        process.terminate()

    def get_day_data(self, date, brief_only=False, in_str=False):

        data = dict()

        for obj in self.program.object_manager.get_objects_with_cond({'_statistics': True}):
            object_id = obj.get_id()
            object_data = self.get_object_day_data(date, object_id, in_str=in_str)

            if object_data[0] == 2:
                continue

            if brief_only:
                data[object_id] = object_data[1]
            else:
                data[object_id] = object_data

        return data

    def get_object_day_data(self, date, object_id, in_str=False):

        if type(date).__name__ == "function":
            date = date()

        if isinstance(date, str):
            date = datetime.datetime.strptime(date, '%d-%b-%Y')

        if in_str:
            return self.program.object_manager.get_object_by_id(object_id).get_str_day_data(date)

        return self.program.object_manager.get_object_by_id(object_id).get_day_data(date)

    def get_month_data(self, date, brief_only=False, in_str=False):

        data = dict()

        for obj in self.program.object_manager.get_objects_with_cond({'_statistics': True}):
            object_id = obj.get_id()
            object_data = self.get_object_month_data(date, object_id, in_str=in_str)

            if object_data[0] == 2:
                continue

            if brief_only:
                data[object_id] = object_data[1]
            else:
                data[object_id] = object_data

        return data

    def get_object_month_data(self, date, object_id, in_str=False):

        if type(date).__name__ == "function":
            date = date()

        if isinstance(date, str):
            date = datetime.datetime.strptime(date, '%d-%b-%Y')

        if in_str:
            return self.program.object_manager.get_object_by_id(object_id).get_str_month_data(date)

        return self.program.object_manager.get_object_by_id(object_id).get_month_data(date)

    def get_str_day_data(self, date):

        string = str()

        day = datetime.datetime.strptime(date, '%d-%b-%Y')
        year = f' {day.year}' if not day.year == datetime.datetime.now().year else str()

        if day.timestamp() > datetime.datetime.now().timestamp():
            return STATS['3']

        data = self.get_day_data(date, brief_only=True, in_str=True)

        if not len(data):
            return STATS['1']

        if date == datetime.datetime.now().strftime('%d-%b-%Y'):
            string += STATS['5'] + '\n\n'
        else:
            string += STATS['4'] % (day.day, MONTHS[str(day.month)][1], year) + "\n\n"

        return self.convert_to_format(string, data)

    def get_str_month_data(self, date):

        string = str()

        if isinstance(date, str):
            day = datetime.datetime.strptime(date, '%d-%b-%Y')
        else:
            day = date
            date = day.strftime('%d-%b-%Y')

        day = datetime.datetime(day.year, day.month, 1)
        year = f' {day.year}' if not day.year == datetime.datetime.now().year else str()

        if day.timestamp() > datetime.datetime.now().timestamp():
            return STATS['10']

        data = self.get_month_data(date, brief_only=True, in_str=True)

        if not len(data):
            return STATS['9']

        if day.month == datetime.datetime.now().month and day.year == datetime.datetime.now().year:
            string += STATS['8'] + '\n\n'
        else:
            string += STATS['7'] % (MONTHS[str(day.month)][0], year) + "\n\n"

        return self.convert_to_format(string, data)

    def convert_to_format(self, string, data):

        for class_name, objects in self.program.object_manager.get_list_for_stats():

            objects = list(filter(lambda i: i[1] in data, objects))

            if not len(objects):
                continue

            string += f'— {class_name} —\n'

            for name, id in objects:
                string += data[id]
                string += '\n'

            string += '\n'

        return string

    def get_stats_from_str(self, text):

        count = len(text.split())

        if count == 1 and text == STATS['16'][0]:
            date = datetime.datetime.now().strftime("%d-%b-%Y")
            return self.get_str_day_data(date)

        array = text.split()

        for word in STATS['16']:
            if word in array:
                array.remove(word)

        count = len(array)

        if STATS['15'][0] in text:
            date = (datetime.datetime.now() - datetime.timedelta(days=2)).strftime("%d-%b-%Y")
            return self.get_str_day_data(date)

        if STATS['15'][1] in text:
            date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%d-%b-%Y")
            return self.get_str_day_data(date)

        if '.' in text and len(array[0].split('.')) == 3:

            day, month, year = array[0].split('.')

            if len(year) <= 2:
                year = str(datetime.datetime.now().year)[:2] + year

            start_date = datetime.datetime.fromtimestamp(self.program.time_handler.get_date_borders()[0])

            valid = (
                    day.isdigit() and month.isdigit() and year.isdigit() and
                    str(int(month)) in MONTHS and
                    (int(year) <= datetime.datetime.now().year or int(year) >= start_date.year)
            )

            if not valid:
                return STATS['2']

            try:

                date = datetime.datetime(
                    int(year),
                    int(month),
                    int(day)
                )

            except ZeroDivisionError:
                return STATS['6']

            if date.timestamp() > datetime.datetime.now().timestamp():
                return STATS['3']
            else:
                return self.get_str_day_data(date.strftime("%d-%b-%Y"))

        if STATS['15'][2] in text:
            return self.get_str_month_data(datetime.datetime.now())

        if array[0] in list(map(lambda x: MONTHS[x][0], MONTHS)):

            year = datetime.datetime.now().year

            if count == 2:
                try:
                    if len(array[1]) == 2:
                        year = int(str(datetime.datetime.now().year)[:-2] + array[1])
                    else:
                        year = int(array[1])
                except:
                    return STATS['6']

            date = datetime.datetime(year, int(list(filter(lambda x: MONTHS[x][0] == array[0], MONTHS))[0]), 1)

            return self.get_str_month_data(date)

        # GET DAY STATS

        start_date = datetime.datetime.fromtimestamp(self.program.time_handler.get_date_borders()[0])

        if count == 2:
            day, month = array
            year = datetime.datetime.now().year

        if count == 3:
            day, month, year = array

            if len(year) <= 2:
                year = str(datetime.datetime.now().year)[:2] + year

        valid = (
                (int(year) <= datetime.datetime.now().year or int(year) >= start_date.year) and
                day.isdigit() and
                month in list(map(lambda x: MONTHS[x][1], MONTHS))
        )

        if not valid:
            return STATS['2']

        try:

            date = datetime.datetime(
                int(year),
                int(list(filter(lambda x: month in MONTHS[x], MONTHS))[0]),
                int(day)
            )

        except ValueError:
            return STATS['6']

        if date.timestamp() > datetime.datetime.now().timestamp():
            return STATS['3']

        return self.get_str_day_data(date.strftime("%d-%b-%Y"))
