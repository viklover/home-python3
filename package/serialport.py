import time
import serial

from threading import Lock


class SerialPort:

    def __init__(self, serialport, baudrate=9600, timeout=30):
        self.status = None
        self.path = serialport
        self.baudrate = baudrate
        self.timeout = timeout

        self.was_opened = False

        self.last_request = 0.0
        self.count_requests = 0

        self.lock = Lock()
        self.lock_io = Lock()

        self.__open()

        self.write(".")

    def __open(self):
        try:
            self.serialport = None
            self.serialport = serial.Serial(port=self.path, baudrate=self.baudrate, timeout=self.timeout)
        except:
            self.status = False
        else:
            self.status = True
            self.was_opened = True

    def __close(self):
        try:
            self.serialport.close()
        except:
            pass
        finally:
            self.status = False

    def is_available(self):
        if not self.status:
            self.__open()
            return self.status
        try:
            test = self.serialport.write(bytes("1", "utf-8"))
        except:
            self.status = False
            self.__open()
        return self.status

    def read_byte(self):
        self.lock_io.acquire()
        if self.is_available():
            try:
                data = self.serialport.read(1)
                self.lock_io.release()
                return data
            except:
                self.status = False
                self.lock_io.release()
                raise ConnectionError("Порт не доступен")
        else:
            self.lock_io.release()
            raise ConnectionError("Порт не доступен")

    def read_line(self):
        self.lock_io.acquire()
        if self.is_available():
            try:
                data = self.serialport.readline()
                self.lock_io.release()
                return data
            except:
                self.status = False
                self.lock_io.release()
                raise ConnectionError("Порт не доступен")
        else:
            self.lock_io.release()
            raise ConnectionError("Порт не доступен")

    def read_until(self, until):
        self.lock_io.acquire()
        if self.is_available():
            try:
                buffer = []
                while buffer[-1] != until:
                    if self.serialport.inWaiting() < 1:
                        return buffer
                    buffer += self.serialport.read(1)
                self.lock_io.release()
                return buffer
            except:
                self.status = False
                self.lock_io.release()
                return ConnectionError("Порт не доступен")
        else:
            self.lock_io.release()
            raise ConnectionError("Порт не доступен")

    def write(self, string):
        self.lock_io.acquire()
        self.count_requests += 1
        if self.is_available():
            if time.time() - self.last_request < 30:
                time.sleep(10)
            try:
                self.serialport.write(bytes(string, "utf-8"))
            except:
                self.status = False
                self.lock_io.release()
                raise ConnectionError("Порт не доступен")
            else:
                self.last_request = time.time()
            finally:
                self.lock_io.release()
        else:
            self.lock_io.release()
            raise ConnectionError("Порт не доступен")

    def write_byte(self, byte):
        self.lock_io.acquire()
        if self.is_available():
            self.serialport.write(chr(byte))
            self.lock_io.release()
        else:
            self.lock_io.release()
            raise ConnectionError("Порт не доступен")
