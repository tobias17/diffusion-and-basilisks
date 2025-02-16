from __future__ import annotations
from common import logger
from game import Game

from dataclasses import dataclass
from threading import Thread, Event, Lock
from typing import Optional, List, Union
from enum import Enum, auto
import time, sys, termios, select, tty, os, traceback

TARGET_FPS = 1.0
FRAME_DELTA = 1.0 / TARGET_FPS
SLEEP_MS = 10.0

SCREEN_WIDTH  = 150
SCREEN_HEIGHT = 30

@dataclass
class Pos:
   x: int
   y: int

@dataclass
class Rect:
   x1: int
   y1: int
   w: int
   h: int

   # NOTE: these are "off by 1"
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


class Screen_Buffer:
   rows: List[str]
   mutex: Lock
   cursor_pos: Pos

   dirty_rows: List[bool]
   dirty_cursor: bool

   def __init__(self, width:int, height:int):
      self.rows = [" "*width for _ in range(height)]
      self.dirty_rows = [False for _ in range(height)]
      self.dirty_cursor = False
      self.mutex = Lock()
      self.cursor_pos = Pos(0, 0)
   
   def put_text_in(self, rect:Rect, x:int, y:int, text:str) -> 'Screen_Buffer':
      assert rect.x1 >= 0 and rect.x2 <= len(self.rows[0]) and rect.y1 >= 0 and rect.y2 <= len(self.rows)

      assert 0 <= y <= rect.h, f"0 <= {y} < {rect.h}"
      assert 0 <= x <= rect.w, f"0 <= {x} < {rect.w}"
      assert 0 <= x+len(text) <= rect.w, f"0 <= {x+len(text)} < {rect.w}"

      row_y = rect.y1 + y
      start_x = rect.x1 + x
      end_x = start_x + len(text)

      self.rows[row_y] = self.rows[row_y][:start_x] + text + self.rows[row_y][end_x:]
      self.dirty_rows[row_y] = True
      return self

   def move_cursor(self, x:int, y:int) -> 'Screen_Buffer':
      self.cursor_pos.x = x
      self.cursor_pos.y = y
      return self

   def redraw(self, only_dirty:bool=True) -> 'Screen_Buffer':
      logger.info(f"Enter draw request, {only_dirty=}")
      with self.mutex:
         text = "" if only_dirty else "\033[2J"
         for y in range(len(self.rows)):
            if self.dirty_rows[y] or (not only_dirty):
               text += coord(1, y+1) + self.rows[y]
               self.dirty_rows[y] = False
         if len(text) > 0 or self.dirty_cursor:
            text += coord(self.cursor_pos.x + 1, self.cursor_pos.y + 1)
            logger.info(f"Moving cursor to {self.cursor_pos.x + 1}, {self.cursor_pos.y + 1}")
            self.dirty_cursor = False
            logger.info("Redrawing cursor from buffer")
         if len(text) > 0:
            logger.info(f"Printing {len(text.encode())} bytes to screen")
            print(text, end='')
      return self


class Input_Handler:
   POOL_INTERVAL_SEC = 0.01
   rect: Rect = INPUT_SPACE

   accepting_input: bool = True
   kill_event: Event
   screen_buffer: Screen_Buffer

   curr_input: str
   input_ptr: int

   def __init__(self, screen_buffer:Screen_Buffer, kill_event:Event, buffer_complete_fnx):
      self.screen_buffer = screen_buffer
      self.kill_event = kill_event
      self.buffer_complete_fnx = buffer_complete_fnx
      self.clear_input()
      self.fd = sys.stdin.fileno()

   def clear_input(self, disable_input:bool=False):
      self.curr_input = ""
      self.input_ptr = 1
      if disable_input:
         self.accepting_input = False

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

   def rewrite_buffer(self, start_index:int) -> None:
      width = self.rect.w - len(INPUT_PREFIX)

      if start_index == -1:
         self.screen_buffer.put_text_in(self.rect, 0, 0, INPUT_PREFIX)
         start_index = 0

      start_x = start_index %  width
      start_y = start_index // width
      end_x = start_x + (len(self.curr_input) - start_index)

      while end_x > 0:
         start_ptr = start_y * width + start_x
         end_ptr = min(start_y * width + end_x, width)
         self.screen_buffer.put_text_in(self.rect, start_x, start_y, self.curr_input[start_ptr:end_ptr])
         start_y += 1
         start_x = 0
         end_x -= width

   def move_cursor(self) -> None:
      width = self.rect.w - len(INPUT_PREFIX)
      self.screen_buffer.move_cursor(self.rect.x1 + len(INPUT_PREFIX) + (self.input_ptr-1) % width, self.rect.y1 + (self.input_ptr-1) // width)

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
               if self.input_ptr >= len(self.curr_input):
                  self.curr_input += key
                  self.input_ptr = len(self.curr_input)
               else:
                  self.curr_input = self.curr_input[:self.input_ptr] + key + self.curr_input[self.input_ptr:]
                  self.input_ptr += 1
               self.rewrite_buffer(self.input_ptr-1)
               self.move_cursor()
               self.screen_buffer.redraw()
            elif isinstance(key, Special_Keys):
               # Special control character
               if key == Special_Keys.CTRL_C:
                  logger.info("Detected ctrl+c, setting kill event")
                  self.kill_event.set()
               elif key == Special_Keys.LEFT_ARROW:
                  self.input_ptr = max(1, self.input_ptr - 1)
                  self.move_cursor()
                  self.screen_buffer.redraw()
               elif key == Special_Keys.RIGHT_ARROW:
                  self.input_ptr = min(self.input_ptr + 1, len(self.curr_input))
                  self.move_cursor()
                  self.screen_buffer.redraw()

      except Exception:
         logger.error(f"Screen Hanlder ran into error in run")
         for line in traceback.format_exc().split("\n"):
            logger.error(line)
         self.kill_event.set()


class Event_Display:
   rect: Rect = EVENT_SPACE

   __event_lines: List[str]
   __event_page_index: int = 0
   
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


class Screen_Handler:
   kill_event: Event
   rect: Rect = Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)

   screen_buffer: Screen_Buffer
   input_handler: Input_Handler

   def __init__(self, game:Game):
      self.kill_event = Event()
      self.screen_buffer = Screen_Buffer(SCREEN_WIDTH, SCREEN_HEIGHT)
      self.input_handler = Input_Handler(self.screen_buffer, self.kill_event, self.__buffer_complete)
      # self.update_game(game)

   def __buffer_complete(self) -> None:
      pass

   def run(self) -> None:
      try:
         Thread(target=self.input_handler.run).start()

         self.screen_buffer.put_text_in(self.rect, 0, 0, "+" + "-"*(SCREEN_WIDTH-2) + "+")
         for y in range(1, SCREEN_HEIGHT-1):
            self.screen_buffer.put_text_in(self.rect, 0, y, "|")
            self.screen_buffer.put_text_in(self.rect, SCREEN_WIDTH-1, y, "|")
         self.screen_buffer.put_text_in(self.rect, 0, SCREEN_HEIGHT-1, "+" + "-"*(SCREEN_WIDTH-2) + "+")

         self.input_handler.rewrite_buffer(-1)
         self.input_handler.move_cursor()
         self.screen_buffer.redraw(only_dirty=False)

         e_time = time.time()
         while not self.kill_event.is_set():
            if time.time() < e_time:
               time.sleep(SLEEP_MS / 1000.0)
               continue

            # self.screen_buffer.redraw(only_dirty=False)

            e_time += FRAME_DELTA

      except Exception:
         logger.error(f"Screen Hanlder ran into error in run")
         for line in traceback.format_exc().split("\n"):
            logger.error(line)
         self.kill_event.set()
