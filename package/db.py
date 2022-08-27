import time
import random
import sqlite3
import functools


class Database:

    def __init__(self, path, logging=True, block=None, log_dir=None):
        self.name = path.split('/')[-1]

        self.last_request = None
        self.last_response = None
        self.logging = logging

        if log_dir is not None:
            self.log_dir = log_dir
        else:
            self.log_dir = '/'.join(path.split('/')[0:-1])

        self.path = path
        self.block = block

        self.log_path = f'{self.log_dir}/{self.name}.log'

    def log(self, line):

        if not self.logging:
            return

        d = time.strftime("%d-%b-%Y", time.localtime())
        t = time.strftime("%H:%M:%S", time.localtime())

        block = str() if not self.block else f'({self.block}) '

        with open(self.log_path, 'a') as f:
            f.write(f'[{d} - {t}] {block}{line}\n')

    def open(self):
        conn = sqlite3.connect(self.path)
        curs = conn.cursor()
        return curs, conn

    def close(self, db):
        curs, conn = db
        curs.close(), conn.close()

    def execute(self, db, request):
        curs, conn = db
        errors = 0

        # print(request)

        self.last_request = request

        while errors < 4:
            try:
                curs.execute(request)
                conn.commit()
            except sqlite3.OperationalError:
                time.sleep(random.uniform(0, 5))
                errors += 1
            else:
                break
        else:
            self.log(f'!{request}')
            return

        self.log(request)

    def executescript(self, requests):
        curs, conn = self.open()
        errors = 0

        request = ';'.join(requests)

        self.last_request = request

        while errors < 4:
            try:
                curs.executescript(request)
                conn.commit()
            except sqlite3.OperationalError:
                time.sleep(random.uniform(0, 5))
                errors += 1
            else:
                break
        else:
            self.log(f'!{request}')
            return

        self.log(request)

    def fetchall(self, db, and_close=True, unpack=False):

        def get_data(cursor):
            error = 0
            while True:
                try:
                    data = cursor.fetchall()
                except sqlite3.ProgrammingError:
                    time.sleep(random.uniform(0.1, 0.5))
                    if error > 5 and error < 7:
                        print('проблемы с fetchall у events.db')
                    error += 1
            return data

        def unpackTuples(array):
            result = list()
            for i in array:
                if not isinstance(i, tuple):
                    result.append(i)
                    continue
                result.extend(unpackTuples(i))
            return result

        curs, conn = db
        data = curs.fetchall()

        if and_close:
            self.close((curs, conn))

        if not len(data):
            self.last_response = list()
            return list()

        if len(data) == 1 and unpack:

            if len(data[0]) == 1:
                self.last_response = data[0][0]
                return data[0][0]

            self.last_response = data[0]
            return data[0]

        if unpack:
            data = unpackTuples(data)

        self.last_response = data

        return data

    def create(self, table, columns):
        curs, conn = self.open()

        columns = self.__create_columns_with_type(columns)

        request = f'CREATE TABLE IF NOT EXISTS "{table}" ({columns})'

        self.execute((curs, conn), request)
        self.close((curs, conn))

    def insert(self, table, columns):
        curs, conn = self.open()

        columns, values = self.__create_columns_and_values(columns)

        request = f'INSERT INTO "{table}" ({columns}) VALUES ({values})'

        self.execute((curs, conn), request)
        self.close((curs, conn))

    def select_req(self, table, columns=["*"], conds=[], last=False, ifnull=False, quotes=True):

        columns = self.__create_columns(columns, quotes=quotes)
        conds = self.__create_conditions(conds)

        sort = "ORDER BY rowid DESC LIMIT 1" if last else ""

        return f'SELECT {columns} FROM "{table}" {conds} {sort}'

    def select(self, table, columns=["*"], conds=[], last=False, ifnull=False, quotes=True, unpack=False):

        curs, conn = self.open()

        request = self.select_req(table, columns, conds, last, ifnull, quotes)

        self.execute((curs, conn), request)

        return self.fetchall((curs, conn), and_close=True, unpack=unpack)

    def update(self, table, columns=[], conds=[]):

        curs, conn = self.open()

        columns = self.__create_update_columns(columns)
        conds = self.__create_conditions(conds)

        request = f'UPDATE "{table}" SET {columns} {conds}'

        self.execute((curs, conn), request)
        self.close((curs, conn))

    def check(self, table, columns=["*"], conds=[], unpack=False, quotes=True):

        curs, conn = self.open()

        # columns = self.__create_columns(columns, quotes=quotes)
        # conds = self.__create_conditions(conds)

        select_req = self.select_req(table, columns=columns, conds=conds, quotes=False)

        request = f'SELECT EXISTS ({select_req})'

        self.execute((curs, conn), request)

        return self.fetchall((curs, conn), and_close=True, unpack=unpack)

    def get_tables(self):
        curs, conn = self.open()

        request = "SELECT name FROM sqlite_master WHERE type='table'"

        self.execute((curs, conn), request)

        return [table for table in self.fetchall((curs, conn), and_close=True)]

    def pragma_table(self, table):
        curs, conn = self.open()

        request = f'PRAGMA table_info("{table}")'

        self.execute((curs, conn), request)

        columns = dict()

        for i in self.fetchall((curs, conn), and_close=False):
            columns[i[1]] = i[2]

        self.close((curs, conn))

        return columns

    def add_column(self, table, column, type):

        curs, conn = self.open()

        request = f'ALTER TABLE "{table}" ADD COLUMN "{column}" {type}'

        self.execute((curs, conn), request)

    def get_str_request(self, command, args, kwargs={}):

        if command == "create":
            table, columns = args
            columns = self.__create_columns_with_type(columns)
            return f'CREATE TABLE IF NOT EXISTS "{table}" ({columns})'

        elif command == "insert":
            table, columns = args
            columns, values = self.__create_columns_and_values(columns)
            return f'INSERT INTO "{table}" ({columns}) VALUES ({values})'

        elif command == "select":
            table = args

            columns, conds = kwargs['columns'], kwargs['conds']
            last = kwargs['last']

            columns = self.__create_columns(columns, **kwargs)
            conds = self.__create_conditions(conds)

            sort = "ORDER BY rowid DESC LIMIT 1" if last else ""

            return f'SELECT {columns} FROM "{table}" {conds} {sort}'

        elif command == "update":
            table = args

            columns, conds = kwargs['columns'], kwargs['conds']

            columns = self.__create_update_columns(columns)
            conds = self.__create_conditions(conds)

            return f'UPDATE "{table}" SET {columns} {conds}'

        elif command == "check":
            table = args

            columns, conds = kwargs['columns'], kwargs['conds']

            columns = self.__create_columns(columns, **kwargs)
            conds = self.__create_conditions(conds)

            return f'SELECT EXISTS (SELECT {columns} FROM "{table}" {conds})'

    def __create_columns(self, columns, quotes=True):

        def format_column(column):
            if column == "*":
                return column

            return f'"{column}"' if quotes else f'{column}'

        return ", ".join(map(format_column, columns))

    def __create_columns_with_type(self, columns):
        return ", ".join(map(lambda i: f'"{i}" {columns[i]}', columns))

    def __create_update_columns(self, columns):

        array = list()

        for key, value in columns:

            if isinstance(value, str):
                value = f'"{value}"'

            array.append(f'"{key}"={value}')

        return ", ".join(array)

    def __create_columns_and_values(self, columns):

        def format_column(column):
            return f'"{column}"'

        def format_value(value):

            if isinstance(value, str):

                if value.lower() == 'null':
                    return "NULL"

                return f'"{value}"'

            if value is None:
                return "NULL"

            return str(value)

        columns, values = zip(*columns)

        columns = map(lambda x: format_column(x), columns)
        values = map(lambda x: format_value(x), values)

        return ', '.join(columns), ', '.join(values)

    def __create_conditions(self, conds, recursion=False):

        if not any(conds):
            return str()

        def set_condition(key, operator, value, quotes=True):

            condition = (f'"{key}"' if quotes else key) + operator

            if value is None:
                return f'"{key}" is NULL'

            if value is '':
                return condition

            if isinstance(value, int) or isinstance(value, float):
                return condition + str(value)

            if isinstance(value, str):

                if any([i in value for i in ('null',)]):
                    return condition + value

                return condition + f'"{value}"'

            print(f'something wrong: why value has {type(value)} type?')

            return None

        first = True
        string = str()

        for i in conds:

            if not first:
                if isinstance(conds, tuple):
                    string += " OR "
                else:
                    string += " AND "

            first = False

            if isinstance(i, tuple) and not isinstance(i[0], tuple):
                quotes = True
                operator = "="

                if len(i) == 3:
                    operator = i[1]
                    value = i[2]
                elif len(i) == 1:
                    operator = str()
                    value = str()
                    quotes = False
                else:
                    operator = '='
                    value = i[1]

                string += set_condition(i[0], operator, value, quotes=quotes)
                continue

            string += self.__create_conditions(i, recursion=True)

        if not recursion:
            return f"WHERE ({string})"

        return f'({string})'
