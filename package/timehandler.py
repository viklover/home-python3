import os
import time
import random
import schedule

from . import BASE_DIR

from .block import Block
from .dates import Time, Date
from threading import Thread


class TimeHandler(Thread, Block):

    def __init__(self, program):
        Thread.__init__(self)
        Block.__init__(self, 'TimeHandler')

        self.files = [
            'bin/first_startup',
            'bin/last_datetime'
        ]

        self.borders = list()

        self.first = False

        self.program = program

        self.__create_files()

    def run(self):
        self.log("запуск обработчика времени schedule", with_name=False)

        self.__set_session_id()
        self.__start_loop()
        self.__close_session()

    def get_date_borders(self):
        return self.borders

    def is_first_startup(self):
        return self.first

    def __start_loop(self):

        while self.program.get_status():
            try:
                schedule.run_pending()

                with open(f'{BASE_DIR}/bin/last_datetime', 'w') as f:
                    f.write(str(time.time()))

            except KeyboardInterrupt:
                break
            finally:
                time.sleep(1)

    def __set_session_id(self):

        with open(f'{BASE_DIR}/bin/session_id', 'w') as f:
            self.id = random.randint(11111, 99999)
            f.write(str(self.id))

    def __close_session(self):

        with open(f'{BASE_DIR}/bin/session_id', 'w') as f:
            f.write('shutdown')

    def __create_files(self):

        for file in self.files:

            index = self.files.index(file)

            if not os.path.isfile(f'{BASE_DIR}/{file}'):

                if not index:
                    self.first = True
                    self.log('этот запуск является первым..')

                with open(f'{BASE_DIR}/{file}', 'w') as f:
                    datetime = time.time()
                    f.write(str(datetime))
                    self.borders.append(datetime)

                return

            with open(f'{BASE_DIR}/{file}', 'r+') as f:
                try:
                    self.borders.append(float(f.readline()))
                except ValueError:
                    self.borders.append(None)
