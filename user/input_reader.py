from common import logger

from enum import Enum, auto
from typing import Union
import sys, os, ctypes


class Special_Keys(Enum):
   CTRL_C = auto()
   ENTER = auto()
   ESCAPE = auto()
   BACKSPACE = auto()
   DELETE = auto()
   LEFT = auto()
   RIGHT = auto()
   UP = auto()
   DOWN = auto()
   HOME = auto()
   END = auto()
   CTRL_LEFT = auto()
   CTRL_RIGHT = auto()
   TAB = auto()
   SHIFT_TAB = auto()
   CTRL_R = auto()
   PAGE_UP = auto()
   PAGE_DOWN = auto()


def interpret_bytes(seq:bytes) -> Union[None,str,Special_Keys]:
   if len(seq) == 1:
      if seq[0] == 3:
         return Special_Keys.CTRL_C
      if seq[0] == 9:
         return Special_Keys.TAB
      if seq[0] == 13:
         return Special_Keys.ENTER
      if seq[0] == 18:
         return Special_Keys.CTRL_R
      if seq[0] == 27:
         return Special_Keys.ESCAPE
      if seq[0] in (127, 8):
         return Special_Keys.BACKSPACE
      if seq[0] >= 32 and seq[0] < 126:
         return seq.decode() # ASCII
   else:
      if seq[0] in (0, 224):
         # Windows-based codes
         if len(seq) == 2:
            if seq[1] == 72:
               return Special_Keys.UP
            if seq[1] == 80:
               return Special_Keys.DOWN
            if seq[1] == 77:
               return Special_Keys.RIGHT
            if seq[1] == 75:
               return Special_Keys.LEFT
            if seq[1] == 71:
               return Special_Keys.HOME
            if seq[1] == 79:
               return Special_Keys.END
            if seq[1] == -1:
               return Special_Keys.SHIFT_TAB # does not work on windows :(
            if seq[1] == 83:
               return Special_Keys.DELETE
            if seq[1] == 73:
               return Special_Keys.PAGE_UP
            if seq[1] == 81:
               return Special_Keys.PAGE_DOWN
            if seq[1] == 115:
               return Special_Keys.CTRL_LEFT
            if seq[1] == 116:
               return Special_Keys.CTRL_RIGHT
      elif seq[0] == 27 and seq[1] == 91:
         # Linux-based codes
         if len(seq) == 2:
            return Special_Keys.ESCAPE
         elif len(seq) == 3:
            if seq[2] == 65:
               return Special_Keys.UP
            if seq[2] == 66:
               return Special_Keys.DOWN
            if seq[2] == 67:
               return Special_Keys.RIGHT
            if seq[2] == 68:
               return Special_Keys.LEFT
            if seq[2] == 72:
               return Special_Keys.HOME
            if seq[2] == 70:
               return Special_Keys.END
            if seq[2] == 90:
               return Special_Keys.SHIFT_TAB
         elif len(seq) == 4:
            if seq[2] == 51 and seq[3] == 126:
               return Special_Keys.DELETE
            if seq[2] == 53 and seq[3] == 126:
               return Special_Keys.PAGE_UP
            if seq[2] == 54 and seq[3] == 126:
               return Special_Keys.PAGE_DOWN
         elif len(seq) == 6:
            if seq[2] == 49 and seq[3] == 59 and seq[4] == 53:
               if seq[5] == 68:
                  return Special_Keys.CTRL_LEFT
               if seq[5] == 67:
                  return Special_Keys.CTRL_RIGHT
      else:
         logger.error(f"Got unknown seq {list(seq)} with non-(27,91)|(0,)|(224,) start")
         return None

   logger.info(f"Got unknown byte sequence {list(seq)}")
   return None


assert os.name in ['posix', 'nt']

# Context Manager to configure terminal settings, to be set up by the main thread
class Peek_Terminal_Input:
   def __enter__(self):
      if os.name == 'nt':
         import msvcrt as _
         self.handle = ctypes.windll.kernel32.GetStdHandle(-11)
         self.orig_mode = ctypes.c_ulong()
         ctypes.windll.kernel32.GetConsoleMode(self.handle, ctypes.byref(self.orig_mode))
         ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
         new_mode = ctypes.c_ulong()
         new_mode.value = self.orig_mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING
         ctypes.windll.kernel32.SetConsoleMode(self.handle, new_mode)
      else:
         import termios, tty
         self.fd = sys.stdin.fileno()
         self.old_settings = termios.tcgetattr(self.fd)
         tty.setraw(self.fd)
      return self

   def __exit__(self, *_):
      if os.name == 'nt':
         ctypes.windll.kernel32.SetConsoleMode(self.handle, self.orig_mode)
      else:
         import termios
         termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)

