from __future__ import annotations
from common import logger
from game import Game

from dataclasses import dataclass
from threading import Thread, Event, Lock
from typing import Optional, List, Union
from enum import Enum, auto
import time, sys, termios, select, tty, os, traceback

TARGET_FPS = 10.0
FRAME_DELTA = 1.0 / TARGET_FPS
SLEEP_MS = 10.0

SCREEN_WIDTH  = 150
SCREEN_HEIGHT = 30

@dataclass
class Rect:
   x1: int
   y1: int
   w: int
   h: int

   @property
   def x2(self) -> int: return self.x1 + self.w
   @property
   def y2(self) -> int: return self.y1 + self.h

INPUT_HEIGHT = 4

EVENT_SPACE = Rect(2, 1, SCREEN_WIDTH - 4, SCREEN_HEIGHT - INPUT_HEIGHT - 3)
INPUT_SPACE = Rect(2, EVENT_SPACE.y2 + 1, SCREEN_WIDTH - 4, INPUT_HEIGHT)
INPUT_PREFIX = "> "


# Context Manager to configure terminal settings, to be set up by the main thread
class Peek_Terminal_Input:
   def __enter__(self):
      self.fd = sys.stdin.fileno()
      self.old_settings = termios.tcgetattr(self.fd)
      tty.setraw(self.fd)
      return self
   def __exit__(self, exc_type, exc_val, exc_tb):
      termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)


def coord(x:int, y:int) -> str:
   return f"\033[{y+1};{x+1}H"


class Special_Keys(Enum):
   LEFT_ARROW = auto()
   RIGHT_ARROW = auto()
   ESCAPE = auto()
   BACKSPACE = auto()
   DELETE = auto()
   CTRL_C = auto()


class Buffer_Handler:
   POOL_INTERVAL_SEC = 0.01

   accepting_input: bool = True
   kill_event: Event
   screen_mutex: Lock

   input_buffer: str
   buffer_pointer: int

   def __init__(self, kill_event:Event, screen_mutex:Lock, buffer_complete_fnx):
      self.buffer_complete_fnx = buffer_complete_fnx
      self.kill_event = kill_event
      self.screen_mutex = screen_mutex
      self.clear_buffer()
      self.fd = sys.stdin.fileno()

   def clear_buffer(self, disable_input:bool=False):
      self.input_buffer = ""
      self.buffer_pointer = 1
      if disable_input:
         self.accepting_input = False

   def __read_seq(self) -> str:
      def has_next():
         return select.select([sys.stdin], [], [], self.POOL_INTERVAL_SEC)[0]
      while not self.kill_event.is_set():
         if has_next():
            text = ""
            while has_next():
               text += sys.stdin.read(1)
            return text
      return ""

   def __read_bytes(self) -> bytes:
      while not self.kill_event.is_set():
         if select.select([sys.stdin], [], [], self.POOL_INTERVAL_SEC)[0]:
            return os.read(self.fd, 16)
      return bytes()

   def __interpret_bytes(self, seq:bytes) -> Union[None,str,Special_Keys]:
      if len(seq) == 1:
         if seq[0] == 3:
            return Special_Keys.CTRL_C
         elif seq[0] == 27:
            return Special_Keys.ESCAPE
         elif seq[0] >= 32 and seq[0] < 126:
            return seq.decode()
      else:
         if seq[0] != 27 and seq[1] == 91:
            logger.error(f"Got unknown seq {list(seq)} with non-27 start")
            return None
         else:
            if len(seq) == 2:
               return Special_Keys.ESCAPE
            if seq[2] == 67:
               return Special_Keys.RIGHT_ARROW
            elif seq[2] == 68:
               return Special_Keys.LEFT_ARROW
      logger.info(f"Got unknown byte sequence {list(seq)}")
      return None

   def get_draw_text(self) -> str:
      return coord(INPUT_SPACE.x1, INPUT_SPACE.y1) + INPUT_PREFIX + self.input_buffer + coord(INPUT_SPACE.x1 + len(INPUT_PREFIX) + self.buffer_pointer, INPUT_SPACE.y1 - 1)

   def draw(self) -> None:
      with self.screen_mutex:
         print(self.get_draw_text())

   def run(self) -> None:
      try:
         while not self.kill_event.is_set():
            if not self.accepting_input:
               time.sleep(self.POOL_INTERVAL_SEC)
               continue

            seq = self.__read_bytes()
            if len(seq) == 0:
               continue
            key = self.__interpret_bytes(seq)
            logger.info(f"Got interpreted key: {key}")
            
            if key is None:
               continue
            elif isinstance(key, str):
               # ASCII character
               if self.buffer_pointer >= len(self.input_buffer):
                  self.input_buffer += key
                  self.buffer_pointer = len(self.input_buffer)
               else:
                  self.input_buffer = self.input_buffer[:self.buffer_pointer] + key + self.input_buffer[self.buffer_pointer:]
                  self.buffer_pointer += 1
               self.draw()
            elif isinstance(key, Special_Keys):
               # Special control character
               if key == Special_Keys.CTRL_C:
                  logger.info("Detected ctrl+c, setting kill event")
                  self.kill_event.set()
               elif key == Special_Keys.LEFT_ARROW:
                  self.buffer_pointer = max(1, self.buffer_pointer - 1)
                  self.draw()
               elif key == Special_Keys.RIGHT_ARROW:
                  self.buffer_pointer = min(self.buffer_pointer + 1, len(self.input_buffer))
                  self.draw()

      except Exception as ex:
         logger.error(f"Screen Hanlder ran into error in run")
         for line in traceback.format_exc().split("\n"):
            logger.error(line)
         self.kill_event.set()


class Screen_Handler:
   kill_event: Event

   __event_lines: List[str]
   __event_page_index: int = 0

   __buffer: Buffer_Handler
   __screen_mutex: Lock

   def __init__(self, game:Game):
      self.kill_event = Event()
      self.__screen_mutex = Lock()
      self.__buffer = Buffer_Handler(self.kill_event, self.__screen_mutex, self.__buffer_complete)
      self.update_game(game)

   def update_game(self, game:Game) -> None:
      self.__event_lines = []
      for event in game.events:
         text = event.player(game)
         if text is not None:
            while len(text) > EVENT_SPACE.w:
               self.__event_lines.append(text[:EVENT_SPACE.w])
               text = text[EVENT_SPACE.w:]
            self.__event_lines.append(text)
            self.__event_lines.append("")
      self.__event_lines.pop(-1) # remove last newline

   def __buffer_complete(self) -> None:
      pass

   def run(self) -> None:
      Thread(target=self.__buffer.run).start()

      e_time = time.time()
      while not self.kill_event.is_set():
         if time.time() < e_time:
            time.sleep(SLEEP_MS / 1000.0)
            continue

         text = "\033[2J" # clear screen
         text += coord(0, 0) + "+" + "-"*(SCREEN_WIDTH-2) + "+"
         for i in range(1, SCREEN_HEIGHT-1):
            text += coord(0, i) + "|" + coord(SCREEN_WIDTH-1, i) + "|"
         text += coord(0, SCREEN_HEIGHT-1) + "+" + "-"*(SCREEN_WIDTH-2) + "+"

         text += coord(0, EVENT_SPACE.y2) + "+" + "-"*(SCREEN_WIDTH-2) + "+"

         end = len(self.__event_lines) - self.__event_page_index * EVENT_SPACE.h
         start = end - EVENT_SPACE.h
         for i in range(start, end):
            if i >= 0:
               text += coord(EVENT_SPACE.x1, EVENT_SPACE.y1+i-start) + self.__event_lines[i]

         text += self.__buffer.get_draw_text()

         with self.__screen_mutex:
            print(text, end="")
         e_time += FRAME_DELTA
