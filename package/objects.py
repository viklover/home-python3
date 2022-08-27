import os
import sys
import time
import json
import socket
import random
import sqlite3
import datetime
import schedule
import calendar
import multiprocessing

import RPi.GPIO as GPIO

from . import BASE_DIR, MESSAGES
from .db import Database
from .block import Block
from .dates import *
from .funcs import count_in_process

from threading import Thread, Timer, Lock


class Object(Block, Thread):

    def __init__(self, config):
        Thread.__init__(self, name=f'Object <{config["name"]}>')

        self._id = config["id"]
        self._name = config["name"]
        self._type = config["type"]
        self._class = config["class"]
        self._kind = config["kind"]
        self._remote = config["remote"]
        self._statistics = config["statistics"]

        self._masters = list()

        self.events_db = Database(f'{BASE_DIR}/databases/events', log_dir=f'{BASE_DIR}/logs', block=self._id)
        self.stats_db = Database(f'{BASE_DIR}/databases/stats', log_dir=f'{BASE_DIR}/logs', block=self._id)

        self.path_to_value = f'{BASE_DIR}/values/{self._id}/value'

        self._program = config["program"]

        self.configurations = config

        self.was_created = None

        Block.__init__(self, f'Object <{self._name}>')

    def get_id(self):
        return self._id

    def get_name(self):
        return self.configurations['name']

    def get_short_name(self):
        if 'short_name' in self.configurations:
            return self.configurations['short_name'][:5]
        return self.configurations['name'][:5]

    def get_type(self):
        return self._type

    def get_class(self):
        return self._class

    def get_kind(self):
        return self._kind

    def has_values_day(self, day):
        return bool(self.stats_db.check(
            self.get_id(),
            ['date'],
            [('date', day.strftime("%d-%b-%Y"))],
            True
        ))

    def is_remote(self):
        return self._remote

    def set_info(self, info):
        self.was_created = info['was_created']

    def save_value(self, value):
        os.system(f'echo "{value}" > {self.path_to_value}')

    def run_action(self, name, event={}):
        if name is None:
            return

        args = {**self.configurations, **event}

        self._program.action_manager.add_task(name, args)

    def __send_to_clients(self, event):
        data = {
            'event': 'update_values',
            'content': {
                **event,
                'id': self._id
            }
        }

        self._program.client_manager.send_message_to_all(json.dumps(data), True)


class TObject(Object):

    def __init__(self, config):
        Object.__init__(self, config)

        self.first = True
        self.resume = config['resume']
        self.resumed = False
        self.last_update = None
        self.last_event = None

        # self.status = self.configurations['opposite']

        self.states = {
            1: 'on', 0: 'off'
        }

        self.status_words = {
            1: MESSAGES['711'], 0: MESSAGES['710']
        }

        self.actions = {False: None, True: None}

        if 'actions' in config:

            if 'on' in config['actions']:
                self.actions[True] = config['actions']['on']

            if 'off' in config['actions']:
                self.actions[False] = config['actions']['off']

        self.time_on = None

        self.__load_last_values()

    def __set_event(self, event):

        def set_on(event, markers):

            columns = [
                *markers,
                ('on', event['time']),
                ('hour_on', datetime.datetime.fromtimestamp(event['time']).hour),
            ]

            self.time_on = event['time']
            self.events_db.insert(self.get_id(), columns=columns)

        def set_off(event, markers):

            if Date(seconds=self.time_on) != event['date']:
                self.log_msg(7113)

                conds = [
                    ('date', Date(seconds=self.time_on)),
                    ('score', event["score"]),
                ]

                columns = [
                    ('duration', getSeconds(event['date']) - self.time_on),
                    ('off', '-0'),
                    ('hour_off', '24'),
                ]

                self.events_db.update(self.get_id(), columns=columns, conds=conds)

                columns = [
                    ('date', event['date']),
                    ('on', '-0'),
                    ('off', event['time']),
                    ('duration', event['time'] - getSeconds(event['date'])),
                    ('score', 1),
                    ('hour_on', '-1'),
                    ('hour_off', datetime.datetime.fromtimestamp(event['time']).hour)
                ]

                self.events_db.insert(self.get_id(), columns=columns)

                self.duration = event['time'] - getSeconds(event['date'])

                return

            columns = [
                ('hour_off', datetime.datetime.fromtimestamp(event['time']).hour),
                ('duration', event['time'] - self.time_on),
                ('off', event['time']),
            ]

            self.events_db.update(self.get_id(), columns=columns, conds=markers)

            self.duration += (event['time'] - self.time_on)

        markers = [
            ('date', event['date']),
            ('score', event['score']),
        ]

        functions = {
            0: set_off,
            1: set_on
        }

        if not self.first or (self.first and event['status'] and not self.resumed):
            self.log_msg(7111, (self.states[int(event['status'])], event['score']))
            functions[event['status']](event, markers)

    def __load_last_values(self):

        self.date = Date()

        self.duration = float()
        self.score = int()

        self.last_update = None

        if self.events_db.select(self._id, columns=["date", "score", "on", "off"], last=True, unpack=True):

            _date, _score, _on, _off = self.events_db.last_response

            self.resumed = (time.time() - _on) <= self.resume and not _off

            if self.resumed:
                self.time_on = _on
                self.score = _score
                self.status = True

            if self.events_db.select(self._id, ['sum(duration)'], [('date', Date())], unpack=True, quotes=False):
                self.duration = self.events_db.last_response

            if not _off:
                self.last_update = _on
            else:
                self.last_update = _off

            if _date == Date():
                self.score = _score

    def set_info(self, info):
        self.was_created = info['was_created']
        if self.last_update is None:
            self.last_update = self.was_created

    def get_status(self):
        return self.status

    def get_score(self):
        return self.score

    def get_current_duration(self):
        if self.last_event is None:
            return time.time() - self.last_update
        return time.time() - self.last_event['time']

    def get_poll(self, string=False):

        if not self.last_event is None:
            keys = self.last_event
        else:
            keys = {'status': self.status, 'score': self.score, 'duration': self.duration, 'time': None}

        if not string:
            return self.status, (self.score, self.duration), self.last_update

        params = {'name': self.get_name(), **keys}

        params['status'] = self.states[int(params['status'])].capitalize()

        return self.configurations['formats']['poll'] % params

    def get_frames(self, date):
        # return self.events_db.select(self.get_id(), columns=["date", "on", "off", "score"], conds=[('date', date.strftime('%d-%b-%Y'))])
        return []

    def get_events(self, day):
        return self.events_db.select(
            self.get_id(),
            columns=['date', 'on', 'off', 'hour_on', 'hour_off', 'duration'],
            conds=[('date', day.strftime('%d-%b-%Y'))]
        )

    def get_str_day_data(self, day):
        return self.convert_to_format(*self.get_day_data(day)[:-1], day)

    def get_str_month_data(self, day):
        return self.convert_to_format(*self.get_month_data(day), day)

    def convert_to_format(self, success, data, day):

        fields = {
            "name": self.get_name(),
            **dict(zip(self.configurations['formats']['brief_keys'], data))
        }

        if day.strftime("%d-%b-%Y") == Date() and self.status:
            fields['dur'] += time.time() - self.last_event['time']

        fields['dur'] = time.strftime('%H:%M:%S', time.gmtime(fields['dur']))

        return success, self.configurations['formats']['stats'] % fields

    def get_days_data(self, days):

        data = {'score': 0, 'dur': 0}

        for day in days:
            success, brief_data, _ = self.get_day_data(get_bounds(day))

            current_data = dict(zip(self.configurations['formats']['brief_keys'], brief_data))

            data['score'] = sum(item['score'] for item in current_data)
            data['dur'] = sum(item['dur'] for item in current_data)

        return data

    def get_hour_data(self, date):

        def has_values(date):
            return bool(self.stats_db.check(
                f'{self.get_id()}_hours',
                columns=['day'],
                conds=[
                    ('day', date.day),
                    ('month', date.month),
                    ('year', date.year)
                ],
                unpack=True
            ))

        if isinstance(date, str):
            date = datetime.datetime.strptime(date, '%d-%b-%Y')

        if has_values(date):
            data = self.stats_db.select(
                f'{self.get_id()}_hours',
                columns=['score', 'duration'],
                conds=[
                    ('day', date.day),
                    ('month', date.month),
                    ('year', date.year)
                ]
            )

            success = 1

            return success, data

        return self.count_hour_data(date, and_save=True)

    def count_hour_data(self, date, and_save=False, and_return=False):

        def count(queue, args):

            bounds, events = args

            data = [[int(), float()] for _ in range(0, 24)]

            success = True

            total_duration = float()

            for date, on, off, hour_on, hour_off, dur in events:

                if off is None:
                    continue

                total_duration += dur

                if hour_on == -1:
                    hour_on = 0
                    on = datetime.datetime.strptime(date, '%d-%b-%Y')
                else:
                    on = datetime.datetime.fromtimestamp(on)

                if hour_off == 24:
                    hour_off = 24
                    off = bounds[0] + datetime.timedelta(days=1)
                else:
                    off = datetime.datetime.fromtimestamp(off)

                if off.timestamp() - on.timestamp() < 0:
                    success = False
                    break

                if hour_on == hour_off:
                    data[hour_on][1] += off.timestamp() - on.timestamp()
                    data[hour_on][0] += 1
                    continue

                data[hour_on][1] += (bounds[hour_on + 1] - on).total_seconds()
                data[hour_on][0] += 1

                hours_later = 0

                for i in range(hour_on + 1, hour_off):
                    data[i][1] += 3600
                    hours_later += 1

                if off.timestamp() == bounds[hour_off].timestamp() or hour_off == 24:
                    continue

                data[hour_off][1] += (off.timestamp() - on.timestamp()) - 3600 * hours_later - (
                        bounds[hour_on + 1] - on).total_seconds()

            checksum = sum(map(lambda x: x[1], data))

            success = int(success and round(total_duration, 2) == round(checksum, 2))

            # if not success:
            #    print(round(total_duration, 2), round(checksum, 2))

            queue.put((success, data, (total_duration, checksum)))

        if isinstance(date, str):
            date = datetime.datetime.strptime(date, '%d-%b-%Y') + datetime.timedelta(hours=23, minutes=59, seconds=59)
        else:
            date = date + datetime.timedelta(hours=23, minutes=59, seconds=59)

        existed = date.timestamp() >= self.was_created
        events = self.get_events(date)

        if not events or not existed:

            data = [(int(), float()) for _ in range(0, 24)]

            success = 1 + int(not existed)

            if and_save and existed and date.strftime("%d-%b-%Y") != Date():
                self.set_values_hour(date, data)

            return success, data

        success, data, dur = count_in_process(count, (get_bounds(date), events))

        if and_save and success and date.strftime("%d-%b-%Y") != Date():
            self.set_values_hour(date, data)

        if and_save and date.strftime("%d-%m-%Y") == Date():
            self.log_msg(7121, color='orange')

        if not success:
            self.log_msg(7122, (date.strftime("%d-%m-%Y"), MESSAGES['71221'] % str(dur)), color='red')

        data = list(map(tuple, data))

        return success, data

    def set_values_hour(self, date, data):

        def has_values(date):
            return bool(self.stats_db.check(
                f'{self.get_id()}_hours',
                columns=['day', 'month', 'year'],
                conds=[
                    ('day', date.day),
                    ('month', date.month),
                    ('year', date.year)
                ],
                unpack=True
            ))

        if not has_values(date):

            requests = []

            for hour in range(0, 24):
                columns = [
                    ('day', date.day),
                    ('month', date.month),
                    ('year', date.year),
                    ('hour', hour),
                    ('duration', data[hour][1]),
                    ('score', data[hour][0])
                ]

                requests.append(self.stats_db.get_str_request('insert', (f'{self.get_id()}_hours', columns)))

            self.stats_db.executescript(requests)

    def get_day_data(self, date):

        def has_values(date):
            return bool(self.stats_db.check(
                f'{self.get_id()}_days',
                columns=['day', 'month', 'year'],
                conds=[
                    ('day', date.day),
                    ('month', date.month),
                    ('year', date.year)
                ],
                unpack=True
            ))

        if isinstance(date, str):
            date = datetime.datetime.strptime(date, '%d-%b-%Y')

        if has_values(date):
            brief_data = self.stats_db.select(
                f'{self.get_id()}_days',
                columns=['score', 'duration'],
                conds=[
                    ('day', date.day),
                    ('month', date.month),
                    ('year', date.year)
                ],
                unpack=True
            )

            data = self.get_frames(date)
            success = 1

            return success, tuple(brief_data), data

        return self.count_day_data(date, and_save=True)

    def count_day_data(self, date, and_save=False, and_return=False):

        success, data = self.get_hour_data(date)

        if not success or success == 2:

            brief_data = (0, 0)
            data = []

            date = date + datetime.timedelta(hours=23, minutes=59, seconds=59)

            existed = date.timestamp() >= self.was_created

            if and_save and success == 1 and existed and date.strftime('%d-%b-%Y') != Date():
                self.set_values_day(date, brief_data)

            return success, brief_data, data

        brief_data = tuple(map(lambda x: sum(x), zip(*data)))
        data = self.get_frames(date)

        if and_save and success and date.strftime("%d-%b-%Y") != Date():
            self.set_values_day(date, brief_data)

        if and_save and date.strftime("%d-%m-%Y") == Date():
            # self.log_msg(7121, color='orange')
            # нельзя сохранять статистику за сегодняшний день
            pass

        if not success:
            # self.log_msg(7122, (bounds[0].strftime("%d-%m-%Y"), MESSAGES['71221']), color='red')
            # ошибка при подсчёте статистики за день (%s)
            pass

        return success, brief_data, data

    def set_values_day(self, date, data):

        def has_values(date):
            return bool(self.stats_db.check(
                f'{self.get_id()}_days',
                columns=['day', 'month', 'year'],
                conds=[
                    ('day', date.day),
                    ('month', date.month),
                    ('year', date.year)
                ],
                unpack=True
            ))

        if not has_values(date):
            columns = [
                ('day', date.day),
                ('month', date.month),
                ('year', date.year),
                ('duration', data[1]),
                ('score', data[0])
            ]

            self.stats_db.insert(f'{self.get_id()}_days', columns)

    def get_month_data(self, date):

        def has_values(date):
            return bool(self.stats_db.check(
                f'{self.get_id()}_months',
                columns=['month'],
                conds=[
                    ('month', date.month),
                    ('year', date.year)
                ],
                unpack=True
            ))

        if isinstance(date, str):
            date = datetime.datetime.strptime(date, '%d-%b-%Y')

        if has_values(date):
            brief_data = self.stats_db.select(
                f'{self.get_id()}_months',
                columns=['score', 'duration'],
                conds=[
                    ('month', date.month),
                    ('year', date.year)
                ],
                unpack=True
            )

            # data = self.get_month_data_frames(date)
            success = 1

            return success, tuple(brief_data)

        return self.count_month_data(date, and_save=True)

    def get_month_data_frames(self, date):

        start_date = datetime.datetime(date.year, date.month, 1)

        days = []

        for i in range(calendar.monthrange(date.year, date.month)[1]):
            days.append(start_date + datetime.timedelta(days=i))

        data = []

        for day in days:
            data.append((*self.get_day_data(day)[:-1], day.strftime('%d-%b-%Y')))

        return data

    def count_month_data(self, date, and_save=True):

        if isinstance(date, str):
            date = datetime.datetime.strptime(date, '%d-%b-%Y')

        start_date = datetime.datetime(date.year, date.month, 1)

        days = []
        existed = False
        current_month = False

        for i in range(calendar.monthrange(date.year, date.month)[1]):

            day = start_date + datetime.timedelta(days=i)

            # 86399 = 23:59:59

            if not existed and ((day.timestamp() + 86399) >= self.was_created):
                existed = True

            if day.strftime('%d-%b-%Y') == Date():
                current_month = True
                break

            days.append(day)

        if not existed:
            success = 2
            brief_data = [int(), float()]
            # data = []

            return (success, brief_data)

        brief_data = []
        # data = []

        for day in days:
            success, current_brief_data = self.get_day_data(day)[:-1]

            if not success:
                continue

            brief_data.append(list(current_brief_data))
        #    data.append((success, current_brief_data, day.strftime('%d-%b-%Y')))

        brief_data = tuple(map(lambda x: sum(x), zip(*brief_data)))

        if and_save and not current_month:
            self.set_values_month(date, brief_data)

        success = 1

        return success, brief_data

    def set_values_month(self, date, data):

        def has_values(date):
            return bool(self.stats_db.check(
                f'{self.get_id()}_months',
                columns=['month', 'year'],
                conds=[
                    ('month', date.month),
                    ('year', date.year)
                ],
                unpack=True
            ))

        if not has_values(date):
            columns = [
                ('month', date.month),
                ('year', date.year),
                ('duration', data[1]),
                ('score', data[0])
            ]

            self.stats_db.insert(f'{self.get_id()}_months', columns)

    def get_year_data(self, year):
        pass

    """def get_behavior_assessment(self):

        def count_last_hour_data(queue, args):

            bounds, events, hour = args

            data = [[int(), float()] for _ in range(0, 24)]

            for date, on, off, hour_on, hour_off, dur in events:

                if off is None:
                    continue

                if hour_on == -1:
                    hour_on = 0
                    on = datetime.datetime.strptime(date, '%d-%b-%Y')
                else:
                    on = datetime.datetime.fromtimestamp(on)

                if hour_off == 24:
                    hour_off = 24
                    off = day - datetime.timedelta(hours=1)
                else:
                    off = datetime.datetime.fromtimestamp(off)

                if hour_on == hour_off:
                    data[hour_on][1] += off.timestamp() - on.timestamp()
                    data[hour_on][0] += 1
                    continue

                data[hour_on][1] += (bounds[hour_on + 1] - on).total_seconds()
                data[hour_on][0] += 1

                hours_later = 0

                for i in range(hour_on + 1, hour_off):
                    data[i][1] += 3600
                    hours_later += 1

                if off.timestamp() == bounds[hour_off].timestamp() or hour_off == 24:
                    continue

                data[hour_off][1] += (off.timestamp() - on.timestamp()) - 3600 * hours_later - (
                            bounds[hour_on + 1] - on).total_seconds()

            queue.put(tuple(data[hour]))

        date_of_last_hour = (datetime.datetime.now() - datetime.timedelta(hours=1)).strftime("%d-%b-%Y")
        bounds = get_bounds(date_of_last_hour)
        events = self.get_events(bounds[0])

        data = list([
            count_in_process(count_last_hour_data, (bounds, events, hour)),
            *self.stats_db.select(
                self.get_id(),
                columns=['duration', 'score'],
                conds=[('hour', hour)]
            )
        ])
"""


class VObject(Object):

    def __init__(self, config):
        Object.__init__(self, config)
        self.values = list()

        self.actual_value_duration = 3600

        if 'actual_value_duration' in config:
            self.actual_value_duration = config['actual_value_duration']

        self.fail = False
        self.first = True

        self.max = None
        self.min = None
        self.avg = None

        self.last_success_event = None
        self.last_update = None

        self.set_color('cyan')

    def __set_event(self, event):

        if event['success'] and not event['fail']:
            columns = [
                ('date', event['date']),
                ('value', event['value']),
                ('time', event['time'])
            ]

            self.events_db.insert(self.get_id(), columns=columns)

    def __load_last_values(self):

        columns = ['max("value")', 'min("value")']

        if self.events_db.select(self.get_id(), columns=columns, conds=[("date", Date())], quotes=False, unpack=True):
            self.max, self.min = self.events_db.last_response

        if self.events_db.select(self.get_id(), columns=['value'], conds=[("date", Date())], unpack=True):

            if not isinstance(self.events_db.last_response, list):
                self.values = [self.events_db.last_response]
                self.avg = round(self.events_db.last_response, 1)
                return

            self.values = list(self.events_db.last_response)
            self.avg = round(sum(self.values) / len(self.values), 1)

        if self.events_db.select(self.get_id(), ['time', 'value'], [('date', Date())]):
            time_on, value = self.events_db.last_response[-1:][0]

            if time.time() - time_on <= self.actual_value_duration:
                self.last_success_event = {
                    'success': True,
                    'value': value,
                    'date': Date(),
                    'time': time_on,
                    'fail': self.fail,
                    'max': self.max,
                    'min': self.min,
                    'avg': self.avg,
                    'first': False,
                    'prev_value': self.events_db.last_response[-2:][0]
                }

                self.last_update = time_on

    def get_frames(self, date):
        # return self.events_db.select(self.get_id(), columns=['time', 'value'], conds=[('date', date)])
        return []

    def get_events(self, day):
        return self.events_db.select(
            self.get_id(),
            columns=['time', 'value', 'hour'],
            conds=[('date', day.strftime('%d-%b-%Y'))]
        )

    def get_str_day_data(self, day):
        return self.convert_to_format(*self.get_day_data(day)[:-1])

    def get_str_month_data(self, day):
        return self.convert_to_format(*self.get_month_data(day))

    def convert_to_format(self, success, data):

        fields = {
            "name": self.get_name(),
            **dict(zip(self.configurations['formats']['brief_keys'], data))
        }

        for i in fields:
            if fields[i] is None:
                fields[i] = '__'

        return success, self.configurations['formats']['stats'] % fields

    def __get_brief_data(self, data):

        def unpack(item):
            unpacked_array = []
            if isinstance(item, tuple) or isinstance(item, list):
                for i in item:
                    if isinstance(i, tuple) or isinstance(i, list):
                        unpacked_array.extend(unpack(i))
                        continue
                    if isinstance(i, float):
                        unpacked_array.append(i)
            else:
                if isinstance(item, float):
                    unpacked_array.append(item)
            return unpacked_array

        def is_float(x):
            return isinstance(x, float)

        data = unpack(data)

        if not len(data):
            return None, None, None

        brief_data = (min(data), max(data), round(sum(data) / len(data), 2))

        return brief_data

    def get_hour_data(self, date):

        def has_values(date):
            return bool(self.stats_db.check(
                f'{self.get_id()}_hours',
                columns=['day', 'month', 'year'],
                conds=[
                    ('day', date.day),
                    ('month', date.month),
                    ('year', date.year)
                ],
                unpack=True
            ))

        if isinstance(date, str):
            date = datetime.datetime.strptime(date, '%d-%b-%Y')

        if has_values(date):
            data = self.stats_db.select(
                f'{self.get_id()}_hours',
                columns=['min', 'max', 'avg'],
                conds=[
                    ('day', date.day),
                    ('month', date.month),
                    ('year', date.year)
                ]
            )

            success = 1

            return (success, data)

        return self.count_hour_data(date, and_save=True)

    def count_hour_data(self, date, and_save=True):

        if isinstance(date, str):
            date = datetime.datetime.strptime(date, '%d-%b-%Y') + datetime.timedelta(hours=23, minutes=59, seconds=59)

        bounds = get_bounds(date)

        existed = date.timestamp() >= self.was_created
        events = self.get_events(date)

        if not events or not existed:

            data = [(None, None, None) for _ in range(0, 24)]

            success = 1 + int(not existed)

            if and_save and existed and date.strftime("%d-%b-%Y") != Date():
                self.set_values_hour(date, data)

            return (success, data)

        def count(queue, args):

            bounds, events = args

            data = [[None, None, None] for _ in range(0, 24)]

            for hour in range(0, 24):

                def is_current_hour(j):
                    return hour == datetime.datetime.fromtimestamp(j[0]).hour

                values = list(filter(is_current_hour, events))

                if not len(values):
                    continue

                _, values, _ = zip(*values)

                data[hour][0] = min(values)
                data[hour][1] = max(values)
                data[hour][2] = round(sum(values) / len(values), 2)

            queue.put(data)

        data = count_in_process(count, (bounds, events))

        if and_save and date.strftime("%d-%b-%Y") != Date():
            self.set_values_hour(date, data)

        data = list(map(tuple, data))
        success = 1

        return success, data

    def set_values_hour(self, day, data):

        def has_values(date):
            return bool(self.stats_db.check(
                f'{self.get_id()}_hours',
                columns=['day', 'month', 'year'],
                conds=[
                    ('day', date.day),
                    ('month', date.month),
                    ('year', date.year)
                ],
                unpack=True
            ))

        if not has_values(day):

            requests = []

            for hour in range(0, 24):
                columns = [
                    ('day', day.day),
                    ('month', day.month),
                    ('year', day.year),
                    ('hour', hour),
                    ('min', data[hour][0]),
                    ('max', data[hour][1]),
                    ('avg', data[hour][2])
                ]

                requests.append(self.stats_db.get_str_request('insert', (f'{self.get_id()}_hours', columns)))

            self.stats_db.executescript(requests)

    def get_day_data(self, date):

        def has_values(date):
            return bool(self.stats_db.check(
                f'{self.get_id()}_days',
                columns=['day', 'month', 'year'],
                conds=[
                    ('day', date.day),
                    ('month', date.month),
                    ('year', date.year)
                ],
                unpack=True
            ))

        if isinstance(date, str):
            date = datetime.datetime.strptime(date, '%d-%b-%Y')

        if has_values(date):
            data = self.stats_db.select(
                f'{self.get_id()}_days',
                columns=['min', 'max', 'avg'],
                conds=[
                    ('day', date.day),
                    ('month', date.month),
                    ('year', date.year)
                ],
                unpack=True
            )

            brief_data = tuple(data)
            data = self.get_frames(date)
            success = 1

            return success, brief_data, data

        return self.count_day_data(date, and_save=True)

    def count_day_data(self, date, and_save=True):

        success, data = self.get_hour_data(date)

        if not success or success == 2:
            brief_data = (None, None, None)
            data = []

            return success, brief_data, data

        brief_data = self.__get_brief_data(data)

        if and_save and success and date.strftime("%d-%b-%Y") != Date():
            self.set_values_day(date, brief_data)

        data = self.get_frames(date)
        success = 1

        return success, brief_data, data

    def set_values_day(self, day, data):

        def has_values(date):
            return bool(self.stats_db.check(
                f'{self.get_id()}_days',
                columns=['day'],
                conds=[
                    ('day', date.day),
                    ('month', date.month),
                    ('year', date.year)
                ],
                unpack=True
            ))

        if not has_values(day):
            columns = [
                ('day', day.day),
                ('month', day.month),
                ('year', day.year),
                ('min', data[0]),
                ('max', data[1]),
                ('avg', data[2])
            ]

            self.stats_db.insert(f'{self.get_id()}_days', columns)

    def get_month_data(self, date):

        def has_values(date):
            return bool(self.stats_db.check(
                f'{self.get_id()}_months',
                columns=['month'],
                conds=[
                    ('month', date.month),
                    ('year', date.year)
                ],
                unpack=True
            ))

        if isinstance(date, str):
            date = datetime.datetime.strptime(date, '%d-%b-%Y')

        if has_values(date):
            brief_data = self.stats_db.select(
                f'{self.get_id()}_months',
                columns=['min', 'max', 'avg'],
                conds=[
                    ('month', date.month),
                    ('year', date.year)
                ],
                unpack=True
            )

            # data = self.get_month_data_frames(date)
            success = 1

            return success, tuple(brief_data)

        return self.count_month_data(date, and_save=True)

    def get_month_data_frames(self, date):

        start_date = datetime.datetime(date.year, date.month, 1)

        days = []

        for i in range(calendar.monthrange(date.year, date.month)[1]):
            days.append(start_date + datetime.timedelta(days=i))

        data = []

        for day in days:

            if day.strftime('%d-%b-%Y') == Date():
                break

            data.append((*self.get_day_data(day)[:-1], day.strftime('%d-%b-%Y')))

        return data

    def count_month_data(self, date, and_save=True):

        if isinstance(date, str):
            date = datetime.datetime.strptime(date, '%d-%b-%Y')

        start_date = datetime.datetime(date.year, date.month, 1)

        days = []
        existed = False
        current_month = False

        for i in range(calendar.monthrange(date.year, date.month)[1]):

            day = start_date + datetime.timedelta(days=i)

            if not existed and (day.timestamp() >= self.was_created):
                existed = True

            if day.strftime('%d-%b-%Y') == Date():
                current_month = True
                break

            days.append(day)

        if not existed:
            success = 2
            brief_data = [None, None, None]
            # data = []

            return success, brief_data

        brief_data = []
        # data = []

        for day in days:
            success, current_brief_data = self.get_day_data(day)[:-1]

            if not success:
                continue

            brief_data.append(list(current_brief_data))
            # data.append((success, current_brief_data, day.strftime('%d-%b-%Y')))

        brief_data = self.__get_brief_data(brief_data)

        if and_save and not current_month:
            self.set_values_month(date, brief_data)

        success = 1

        return success, brief_data

    def set_values_month(self, date, data):

        def has_values(date):
            return bool(self.stats_db.check(
                f'{self.get_id()}_months',
                columns=['month', 'year'],
                conds=[
                    ('month', date.month),
                    ('year', date.year)
                ],
                unpack=True
            ))

        if not has_values(date):
            columns = [
                ('month', date.month),
                ('year', date.year),
                ('min', data[0]),
                ('max', data[1]),
                ('avg', data[2])
            ]

            self.stats_db.insert(f'{self.get_id()}_months', columns)


class Sensor(VObject):

    def __init__(self, config):
        Thread.__init__(self)
        VObject.__init__(self, config)

        self.daemon = True

        self._sleep = config['sleep']
        self._serial_number = config['serial_number']

        self.filter = None
        self.vector = None
        self.actual_value_duration = 3600
        self.attempts = 0

        if 'filter' in config:
            self.filter = config['filter']

        if 'vector' in config:
            self.vector = config['vector']

            if 'interval' not in config['vector']:
                self.vector['interval'] = 3

            if 'attempts' not in config['vector']:
                self.vector['attempts'] = 1

            if 'iteration' not in config['vector']:
                self.vector['iteration'] = 1

        if 'actual_value_duration' in config:
            self.actual_value_duration = config['actual_value_duration']

        self.path = f'/sys/bus/w1/devices/{self._serial_number}/w1_slave'
        self.dir = f'/sys/bus/w1/devices/{self._serial_number}'

        self.first = True
        self.fail = False
        self.was_keyerror = False

        self.max = None
        self.min = None
        self.avg = None

        self.was_success = False

        self.last_values = list()

        self.__set_event = self._VObject__set_event
        self.__send_to_clients = self._Object__send_to_clients
        self.__load_last_values = self._VObject__load_last_values

    def __event(self):
        success, value = self.read_value()

        seconds = time.time()
        date = Date()

        self.prev_value = value

        event = {
            'time': seconds,
            'date': date,
            'success': success,
            'fail': self.fail,
            'value': value,
            'min': self.min,
            'max': self.max,
            'avg': self.avg,
            'first': self.first,
            'prev_value': self.prev_value
        }

        self.__set_event(event)

        self.last_event = event
        self.last_update = seconds

        if not success and not self.first:
            self.fail = True
            self.attempts += 1

        if success and self.fail:
            self.fail = False
            self.was_keyerror = False

            if self.attempts > self.vector['attempts']:
                self.last_values = list()

        if success and not self.fail and not self.first:

            if len(self.last_values) == self.vector['interval']:
                self.last_values.pop(0)

            self.values.append(value)
            self.last_values.append(value)

            if self.max is None or value > self.max:
                self.max = value

            if self.min is None or value < self.min:
                self.min = value

            if self.avg is None:
                self.avg = round(sum(self.values) / len(self.values), 1)

            event['max'], event['min'], event['avg'] = self.max, self.min, self.avg

            self.was_success = True

            self.log_msg(7211, (value))
            self.last_success_event = event
            self.save_value(value)
            return

        event['vector'] = self.get_vector()

        self.__send_to_clients(event)

        if (self.last_success_event is None) or (
                time.time() - self.last_success_event['time'] > self.actual_value_duration):
            self.save_value("None")
            
        self.first = False

    def read_value(self):

        def get_lines():
            try:
                if os.path.isdir(self.dir):
                    f = open(self.path, 'r')
                    lines = f.readlines()
                    f.close()
                    return lines

            except Exception:
                pass
            return None

        def check(value):

            if self.first or self.prev_value == None:
                return False

            array = list()

            if self.filter:

                if 'max' in self.filter:
                    array.append(not (value <= self.filter['max']))

                if 'min' in self.filter:
                    array.append(not (value >= self.filter['min']))

                if 'variance' in self.filter:
                    array.append(not (abs(self.prev_value - value) <= self.filter['variance']))

            # print(not any(array))

            return not any(array)

        lines = get_lines()

        if not lines:
            return False, None

        if lines[0].strip()[-3:] == 'YES':

            if lines[0][lines[0].find('crc=') + 4:].split()[0] == '00' or lines[1].find('t=') == -1:
                return False, None

            value = round(float(lines[1][lines[1].find('t=') + 2:]) / 1000.0, 1)

        return check(value), value

    def run(self):
        self.__load_last_values()

        if self.last_success_event is not None:
            self.last_values = self.values[-self.vector['interval']:]

        for _ in range(0, 2):
            self.__event()

        schedule.every(self._sleep).seconds.do(self.__event)

        self.set_ready(True)

    def get_vector(self):

        if len(self.last_values) < self.vector['interval']:
            return 3

        up = int()
        down = int()
        none = int()

        for i in range(1, len(self.last_values)):

            variance = self.last_values[i] - self.last_values[i - 1]

            if abs(variance) < self.vector['variance']:
                none += 1
                continue

            if variance > 0:
                up += 1

            if variance < 0:
                down += 1

        # print(self.last_values)

        # print(f'up: {up}, down: {down}, none: {none}')

        # if up == down or (none > up and none > down):
        #    return 2

        if up == down or none == self.vector['interval']:
            return 2

        # percent = (abs(up - down) / self.vector['interval'])*100 >= 30.0

        return up > down

    def get_poll(self, string=False):

        vector = {
            0: '↓', 1: '↑', 2: '', 3: ''
        }

        vector_value = self.get_vector()

        actual = not ((self.last_success_event is None) or (
                (time.time() - self.last_success_event['time']) > self.actual_value_duration))

        if not string:

            if not actual:
                return False, None, 3, (self.min, self.max, self.avg), self.last_update

            return (
                self.last_success_event['success'],
                self.last_success_event['value'],
                int(vector_value),
                (self.min, self.max, self.avg),
                self.last_success_event['time']
            )

        else:

            config = {'name': self.get_name()}

            format = self.configurations['formats']['poll']

            if not self.was_success:
                value = '___'
            else:
                value = '...'

            if not actual:
                return format % {**config, 'value': value, 'vector': ''}

            return format % {**config, **self.last_success_event, 'vector': vector[vector_value]}


class SensorSerial(Sensor):

    def __init__(self, config):
        Sensor.__init__(self, config)

        self.serial_port = None

        self.__event = self._Sensor__event
        self.__send_to_clients = self._Sensor__send_to_clients
        self.__load_last_values = self._Sensor__load_last_values

    def set_serial_port(self, serial_port):
        self.serial_port = serial_port

    def read_value(self):

        def get_value():
            self.serial_port.lock.acquire()
            try:
                request = f"get_value *{self._serial_number}"
                # print(request)

                self.serial_port.write(request)

                data = self.serial_port.read_line()
                # print(data)

                data = json.loads(data)[self._serial_number]

            except (ConnectionError, json.decoder.JSONDecodeError, OSError, RuntimeError):
                data = None
                if not self.first:
                    self.log_msg(7222, color='red')
            except KeyError:
                data = None
                self.log_msg(7221, color='red')
                self.was_keyerror = True
            finally:
                self.serial_port.lock.release()
            return data

        def check(value):

            if self.first or self.prev_value is None:
                return False

            array = list()

            if self.filter:

                if 'max' in self.filter:
                    array.append(not (value <= self.filter['max']))

                if 'min' in self.filter:
                    array.append(not (value >= self.filter['min']))

                if 'variance' in self.filter:
                    array.append(not (abs(self.prev_value - value) <= self.filter['variance']))

            # print(not any(array))

            return not any(array)

        value = get_value()

        if value == -127.0 or value is None or type(value) != float:
            if self.fail and not self.was_keyerror:
                self.log_msg(7223, color='red')
            return False, value

        return check(value), value


class Input(TObject):

    def __init__(self, config):
        TObject.__init__(self, config)

        self.pin = config['pin']
        self.pull_ud = GPIO.PUD_DOWN

        if config['pull_ud']:
            self.pull_ud = GPIO.PUD_UP

        self.__set_event = self._TObject__set_event
        self.__send_to_clients = self._Object__send_to_clients

        self.last_event = None
        self.first = True

        GPIO.setup(self.pin, GPIO.IN, pull_up_down=self.pull_ud)

        if not self.configurations['opposite']:
            self.status = bool(GPIO.input(self.pin))
        else:
            self.status = not bool(GPIO.input(self.pin))

        # print(self.get_id(), self.status)

    def run(self):

        if self.first and self.resumed:
            self.log_msg(7112)

        self.__event(None)

        GPIO.add_event_detect(self.pin, GPIO.BOTH, callback=self.__event)
        # bouncetime=300)

        self.set_ready(True)

    def __event(self, pin):

        def get_status():

            if GPIO.input(self.pin) == GPIO.LOW and self.status == self.configurations['opposite']:
                return not self.configurations['opposite']

            elif GPIO.input(self.pin) == GPIO.HIGH and self.status == (not self.configurations['opposite']):
                return self.configurations['opposite']

            return None

        status = get_status()

        if status is None:
            return

        self.status = status

        seconds = time.time()
        date = Date()

        if self.date != date and status:
            self.score = 0

        self.score += int(self.status and not (self.first and self.resumed))

        event = {
            "date": date,
            "time": seconds,
            "score": self.score,
            "status": self.status
        }

        self.__set_event(event)

        if self.date != date and not status:
            self.score = 1

        # SET LAST TIME UPDATE
        if not self.first:
            self.last_update = seconds

        # UPDATE DURATION
        event['duration'] = self.duration

        # SEND EVENT TO CLIENTS
        self.__send_to_clients(event)

        # UPDATE VALUE FILE
        self.save_value(event['status'])

        self.last_event = event
        self.date = date

        if not self.first:
            self.run_action(self.actions[self.status], event)

        if self.first:
            self.first = False

        # print(self.get_id(), self.status)


class Trigger(TObject):

    def __init__(self, config):
        TObject.__init__(self, config)

        # Thread Settings
        # self.name = f'Object <{config["id"]}>'
        self.program_vars = None
        self.user_vars = None
        self.daemon = True

        self.objects = dict()
        self.status = False

        self.lock = Lock()

        from conditions import conditions
        self.condition = conditions[self._id]

        self.__send_to_clients = self._Object__send_to_clients
        self.__set_event = self._TObject__set_event

        self.last_event = None
        self.first = True

        self.__import_config()

    def __import_config(self):

        if 'sleep' in self.configurations:
            self.sleep = self.configurations['sleep']
        else:
            self.sleep = 0.2

    def set_variable(self, id, value):
        # self.objects[id] = value
        self.check_conditions()

    def run(self):
        self.program_vars = self._program.vars
        self.user_vars = self._program.user_vars

        self.status = not self.condition(self._program, self.user_vars)

        self.set_ready(True)

        while self._program.get_status():
            self.check_conditions()
            time.sleep(self.sleep)

    def check_conditions(self):

        if self.condition(self._program, self.user_vars) != self.status:

            seconds = time.time()
            date = Date()

            self.status = not self.status
            self.score += int(self.status and not (self.first and self.resumed))

            event = {
                "date": date,
                "time": seconds,
                "score": self.score,
                "status": self.status,
            }

            self.__set_event(event)

            self.last_update = seconds

            event['duration'] = self.duration

            self.__send_to_clients(event)
            self.save_value(event['status'])

            if not (self.first and not self.status):
                self.run_action(self.actions[self.status], event)

            self.last_event = event
            self.first = False
            self.date = date


class Output(TObject):

    def __init__(self, config):
        TObject.__init__(self, config)

        self.pin = config['pin']
        self.initial = config['initial']

        GPIO.setup(self.pin, GPIO.OUT, initial=self.initial)

        self.status = bool(GPIO.output(self.pin))

        self.__send_to_clients = self._Object__send_to_clients

    def set_active(self, status):
        if self.status == status:
            return

        # SAVE TIME AND DATE
        seconds = time.time()
        date = Date()

        # SET ACTIVE OUTPUT
        levels = {
            True: GPIO.HIGH,
            False: GPIO.LOW,
        }
        GPIO.output(self.pin, levels[status])

        # CREATE EVENT
        self.score += int(status and not (self.first and self.resumed))
        self.status = not self.status

        event = {
            'date': date,
            'time': seconds,
            'score': self.score,
            'status': self.status
        }

        self.__set_event(event)
        self.last_update = seconds

        event['duration'] = self.duration

        # SEND EVENT TO CLIENTS
        self.__send_to_clients(event)

        # UPDATE 'values/{id}/value' FILE
        self.save_value(event['status'])

        # RUN ACTIONS
        self.run_action(self.actions[self.status], event)

        # UPDATE VARIABLES
        self.first = False
        self.last_event = event
