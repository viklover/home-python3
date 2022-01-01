import os

from . import BASE_DIR, MESSAGES, options
from .dates import Time, Date

from colorama import Fore, Back, Style

colors = {
    "white": Fore.WHITE + Style.BRIGHT,
    "yellow": Fore.YELLOW + Style.BRIGHT,
    "orange": "\033[38;5;208m",
    "turquoise": "\033[38;5;49m",
    "sand": "\033[38;5;187m",
    "light blue": "\033[38;5;153m",
    "light yellow": "\033[38;5;155m",
    "light gray": "\033[38;5;150m",
    "azure": "\033[38;5;123m",
    "red": Fore.RED + Style.BRIGHT,
    "green": Fore.GREEN + Style.BRIGHT,
    "blue": Fore.BLUE + Style.BRIGHT,
    "cyan": Fore.CYAN + Style.BRIGHT,
    "magenta": Fore.MAGENTA + Style.BRIGHT
}


class Block:

    def __init__(self, name, path=f"{BASE_DIR}/logs/system.log"):
        self.name_of_block = name
        self.path_log = path
        self.color = 'white'
        self.ready = False

    def is_ready(self):
        return self.ready

    def set_ready(self, status):
        self.ready = status

    def set_name(self, name):
        self.name_of_block = name

    def if_ready(self, func):
        def decorated():
            if self.is_ready():
                func()
            return None

        return decorated

    def printFile(self, name):
        self.log(f'вывод текста из файла "{name}" в консоль')
        with open(f"{BASE_DIR}/{name}") as f:
            self.print(f.read())

    def log(self, line, with_name=True, no_capitalize=False, printing=True, color=None, indent=0):

        string = f"\n[{Date()} - {Time()}]"

        if with_name:
            string += f' {self.name_of_block}:'

        string += f' {" " * indent + line.capitalize() if not no_capitalize else (" " * indent + line)}'

        with open(self.path_log, 'a') as f:

            f.write(string)

            if options["-l"] and printing:
                color = colors[color] if color else colors[self.color]
                print(color + string[1:])

    def log_msg(self, code, args=(), color=None, no_capitalize=False, with_name=True, indent=0):
        self.log(MESSAGES[str(code)] % args, color=color, indent=indent, no_capitalize=no_capitalize,
                 with_name=with_name)

    def set_color(self, color):
        self.color = color
