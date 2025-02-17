from __future__ import annotations
from common import logger
from game import Game

from dataclasses import dataclass
from typing import List, Union, Optional
from enum import Enum, auto
from queue import Queue
from abc import ABC, abstractmethod
import time, sys, termios, select, tty, os, traceback, threading

TARGET_FPS = 1.0
FRAME_DELTA = 1.0 / TARGET_FPS
SLEEP_MS = 10.0

SCREEN_WIDTH  = 200
SCREEN_HEIGHT = 50

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
INPUT_PREFIX = "> "

EVENT_SPACE = Rect(2, 3, SCREEN_WIDTH - 4, SCREEN_HEIGHT - INPUT_HEIGHT - 5)
INPUT_SPACE = Rect(2 + len(INPUT_PREFIX), EVENT_SPACE.y2 + 1, SCREEN_WIDTH - 4 - len(INPUT_PREFIX), INPUT_HEIGHT)


# Context Manager to configure terminal settings, to be set up by the main thread
class Peek_Terminal_Input:
   def __enter__(self):
      self.fd = sys.stdin.fileno()
      self.old_settings = termios.tcgetattr(self.fd)
      tty.setraw(self.fd)
      return self
   def __exit__(self, *_):
      termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)


def coord(x:int, y:int) -> str:
   return f"\033[{y+1};{x+1}H"


class Special_Keys(Enum):
   CTRL_C = auto()
   ENTER = auto()
   ESCAPE = auto()
   BACKSPACE = auto()
   DELETE = auto()
   LEFT_ARROW = auto()
   RIGHT_ARROW = auto()
   HOME = auto()
   END = auto()
   CTRL_LEFT = auto()
   CTRL_RIGHT = auto()


class Input_Target(ABC):
   @abstractmethod
   def process_input(self, inp:Union[str,Special_Keys]) -> None:
      pass


class Screen_Buffer:
   rows: List[str]
   mutex: threading.Lock
   cursor_pos: Pos

   dirty_rows: List[bool]
   dirty_cursor: bool

   def __init__(self, width:int, height:int):
      self.rows = [" "*width for _ in range(height)]
      self.dirty_rows = [False for _ in range(height)]
      self.dirty_cursor = False
      self.mutex = threading.Lock()
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
      self.dirty_cursor = True
      return self

   def draw(self, only_dirty:bool=True) -> 'Screen_Buffer':
      with self.mutex:
         text = "" if only_dirty else "\033[2J"
         for y in range(len(self.rows)):
            if self.dirty_rows[y] or (not only_dirty):
               text += coord(1, y+1) + self.rows[y]
               self.dirty_rows[y] = False
         if self.dirty_cursor or len(text) > 0:
            text += coord(self.cursor_pos.x + 1, self.cursor_pos.y + 1)
            self.dirty_cursor = False
         if len(text) > 0:
            print(text, end='')
            sys.stdout.flush()
      return self


class Bottom_Text_Box(Input_Target):
   rect: Rect = INPUT_SPACE

   accepting_input: bool = True
   kill_event: threading.Event
   screen_buffer: Screen_Buffer

   curr_input: str
   input_ptr: int

   def __init__(self, screen_buffer:Screen_Buffer, kill_event:threading.Event, input_complete_callback):
      self.screen_buffer = screen_buffer
      self.kill_event = kill_event
      self.input_complete_callback = input_complete_callback
      self.clear_input()

   def clear_input(self, disable_input:bool=False):
      self.curr_input = ""
      self.input_ptr = 0
      if disable_input:
         self.accepting_input = False
      self.write_to_buffer()
      self.move_cursor()

   def write_to_buffer(self) -> None:
      text = self.curr_input
      for y in range(self.rect.h):
         line, text = text[:self.rect.w], text[self.rect.w:]
         line += " "*(self.rect.w - len(line))
         self.screen_buffer.put_text_in(self.rect, 0, y, line)

   def move_cursor(self) -> None:
      self.screen_buffer.move_cursor(self.rect.x1 + (self.input_ptr % self.rect.w), self.rect.y1 + (self.input_ptr // self.rect.w))

   def process_input(self, inp:Union[str,Special_Keys]) -> None:
      if isinstance(inp, str):
         # ASCII character
         if self.input_ptr >= len(self.curr_input):
            self.curr_input += inp
            self.input_ptr = len(self.curr_input)
         else:
            self.curr_input = self.curr_input[:self.input_ptr] + inp + self.curr_input[self.input_ptr:]
            self.input_ptr += 1
         self.write_to_buffer()
         self.move_cursor()
      elif isinstance(inp, Special_Keys):
         # Special control character
         if inp == Special_Keys.LEFT_ARROW:
            self.input_ptr = max(0, self.input_ptr - 1)
            self.move_cursor()
            self.screen_buffer.draw()
         elif inp == Special_Keys.RIGHT_ARROW:
            self.input_ptr = min(self.input_ptr + 1, len(self.curr_input))
            self.move_cursor()
            self.screen_buffer.draw()
         elif inp == Special_Keys.BACKSPACE:
            if self.input_ptr > 0:
               self.curr_input = self.curr_input[:self.input_ptr-1] + self.curr_input[self.input_ptr:]
               self.input_ptr -= 1
               self.write_to_buffer()
               self.move_cursor()
         elif inp == Special_Keys.DELETE:
            if self.input_ptr < len(self.curr_input):
               self.curr_input = self.curr_input[:self.input_ptr] + self.curr_input[self.input_ptr+1:]
               self.write_to_buffer()
         elif inp == Special_Keys.HOME:
            self.input_ptr = 0
            self.move_cursor()
         elif inp == Special_Keys.END:
            self.input_ptr = len(self.curr_input)
            self.move_cursor()
         elif inp in (Special_Keys.CTRL_LEFT, Special_Keys.CTRL_RIGHT):
            direction = -1 if inp == Special_Keys.CTRL_LEFT else 1
            walk_ptr = self.input_ptr
            in_white = True
            while True:
               step_ptr = walk_ptr + direction
               if step_ptr <= 0 or step_ptr >= len(self.curr_input):
                  if step_ptr == 0:
                     walk_ptr = 0
                  break # next step is out-of-bounds
               if self.curr_input[step_ptr] == " ":
                  if not in_white:
                     break
               elif in_white:
                  in_white = False
               walk_ptr = step_ptr
            self.input_ptr = walk_ptr
            self.move_cursor()
         elif inp == Special_Keys.ENTER:
            if len(self.curr_input) < 1:
               logger.error("Cannot submit empty input")
            else:
               self.input_complete_callback()

      # Always request a draw (will not nothing if nothing was changed)
      self.screen_buffer.draw()


class Event_Display:
   rect: Rect = EVENT_SPACE
   event_page_index: int = 0
   is_visible: bool = True

   screen_buffer: Screen_Buffer
   event_lines: List[str]
   
   def __init__(self, screen_buffer:Screen_Buffer, game:Game):
      self.screen_buffer = screen_buffer
      self.update_game(game)

   def update_game(self, game:Game) -> None:
      self.event_lines = []
      for event in game.events:
         text = event.player(game)
         if text is not None:
            while len(text) > self.rect.w:
               self.event_lines.append(text[:self.rect.w])
               text = text[self.rect.w:]
            self.event_lines.append(text)
            self.event_lines.append("")
      self.event_lines.pop(-1) # remove last newline

      if self.is_visible:
         self.clear_buffer()
         self.write_to_buffer()

   def clear_buffer(self):
      for y in range(self.rect.h):
         self.screen_buffer.put_text_in(self.rect, 0, y, " "*self.rect.w)

   def write_to_buffer(self):
      for i in range(self.rect.h):
         if i >= len(self.event_lines):
            break
         self.screen_buffer.put_text_in(self.rect, 0, self.rect.h - i - 1, self.event_lines[-(i+1)])


class Screen_Handler:
   POLL_INTERVAL_SEC = 0.01
   rect: Rect = Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)

   kill_event: threading.Event
   user_input_queue: Queue
   screen_buffer: Screen_Buffer
   event_display: Event_Display
   bottom_text_box: Bottom_Text_Box

   input_target: Optional[Input_Target] = None

   def __init__(self, kill_event:threading.Event, game:Game, user_input_queue:Queue[str]):
      self.kill_event = kill_event
      self.user_input_queue = user_input_queue
      self.screen_buffer = Screen_Buffer(SCREEN_WIDTH, SCREEN_HEIGHT)
      self.event_display = Event_Display(self.screen_buffer, game)
      self.bottom_text_box = Bottom_Text_Box(self.screen_buffer, self.kill_event, self.__user_input_complete)
      self.fd = sys.stdin.fileno()
      self.input_target = self.bottom_text_box

   def update_game(self, game:Game) -> None:
      self.event_display.update_game(game)
      self.screen_buffer.draw()

   def accept_input(self) -> None:
      self.bottom_text_box.accepting_input = True

   def __user_input_complete(self) -> None:
      text = self.bottom_text_box.curr_input
      self.bottom_text_box.clear_input()
      self.user_input_queue.put(text)

   def __read_bytes(self) -> bytes:
      while not self.kill_event.is_set():
         if select.select([sys.stdin], [], [], self.POLL_INTERVAL_SEC)[0]:
            return os.read(self.fd, 16)
      return bytes()

   def __interpret_bytes(self, seq:bytes) -> Union[None,str,Special_Keys]:
      if len(seq) == 1:
         if seq[0] == 3:
            return Special_Keys.CTRL_C
         if seq[0] == 13:
            return Special_Keys.ENTER
         if seq[0] == 27:
            return Special_Keys.ESCAPE
         if seq[0] == 127:
            return Special_Keys.BACKSPACE
         if seq[0] >= 32 and seq[0] < 126:
            return seq.decode() # ASCII
      else:
         if seq[0] != 27 and seq[1] != 91:
            logger.error(f"Got unknown seq {list(seq)} with non-(27,91) start")
            return None
         if len(seq) == 2:
            return Special_Keys.ESCAPE
         elif len(seq) == 3:
            if seq[2] == 67:
               return Special_Keys.RIGHT_ARROW
            if seq[2] == 68:
               return Special_Keys.LEFT_ARROW
            if seq[2] == 72:
               return Special_Keys.HOME
            if seq[2] == 70:
               return Special_Keys.END
         elif len(seq) == 4:
            if seq[2] == 51 and seq[3] == 126:
               return Special_Keys.DELETE
         elif len(seq) == 6:
            if seq[2] == 49 and seq[3] == 59 and seq[4] == 53:
               if seq[5] == 68:
                  return Special_Keys.CTRL_LEFT
               if seq[5] == 67:
                  return Special_Keys.CTRL_RIGHT

      logger.info(f"Got unknown byte sequence {list(seq)}")
      return None

   def run(self) -> None:
      try:
         # Borders
         self.screen_buffer.put_text_in(self.rect, 0, 0, "+" + "-"*(SCREEN_WIDTH-2) + "+")
         for y in range(1, SCREEN_HEIGHT-1):
            self.screen_buffer.put_text_in(self.rect, 0, y, "|")
            self.screen_buffer.put_text_in(self.rect, SCREEN_WIDTH-1, y, "|")
         self.screen_buffer.put_text_in(self.rect, 0, SCREEN_HEIGHT-1, "+" + "-"*(SCREEN_WIDTH-2) + "+")
         self.screen_buffer.put_text_in(self.rect, 0, self.bottom_text_box.rect.y1-1, "+" + "-"*(SCREEN_WIDTH-2) + "+")

         # Tabs
         text_row = "| Actions | Speaking | Characters |"
         border_row = "".join(["+" if c == "|" else "-" for c in text_row])
         self.screen_buffer.put_text_in(self.rect, 0, 0, border_row)
         self.screen_buffer.put_text_in(self.rect, 0, 1, text_row)
         self.screen_buffer.put_text_in(self.rect, 0, 2, border_row)

         # User Input
         self.screen_buffer.put_text_in(self.rect, 2, self.bottom_text_box.rect.y1, INPUT_PREFIX)
         self.bottom_text_box.write_to_buffer()
         self.bottom_text_box.move_cursor()

         # Draw the whole screen
         self.screen_buffer.draw(only_dirty=False)

         # Start our main read and process loop
         while not self.kill_event.is_set():
            seq = self.__read_bytes()
            if len(seq) == 0:
               continue # normally means our kill_event got set
            inp = self.__interpret_bytes(seq)
            if inp is None:
               continue # normally means it's a special key we do not handle

            if isinstance(inp, Special_Keys) and inp == Special_Keys.CTRL_C:
               logger.info("Detected ctrl+c, setting kill event")
               self.kill_event.set()

            if self.input_target is not None:
               self.input_target.process_input(inp)

      except Exception:
         logger.error(f"Screen Hanlder ran into error in run")
         for line in traceback.format_exc().split("\n"):
            logger.error(line)
         self.kill_event.set()
