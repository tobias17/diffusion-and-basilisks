from __future__ import annotations
from common import logger, Event, Save_Data, IMAGE_CHARS_WIDE, IMAGE_CHARS_TALL
from game import Game, Game_Processor
import events as E

import sys, termios, select, tty, os, traceback, threading, json, time
from typing import List, Union, Tuple, Type, Dict, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
import numpy as np

SCREEN_WIDTH  = 240
SCREEN_HEIGHT = IMAGE_CHARS_TALL + 2

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

INPUT_HEIGHT = 6
IMAGE_HEIGHT = SCREEN_HEIGHT - 2

EVENT_SPACE = Rect(2, 1, SCREEN_WIDTH - 4 - IMAGE_CHARS_WIDE, SCREEN_HEIGHT - INPUT_HEIGHT - 3)
INPUT_SPACE = Rect(2, EVENT_SPACE.y2 + 1, SCREEN_WIDTH - 4 - IMAGE_CHARS_WIDE, INPUT_HEIGHT)


# Context Manager to configure terminal settings, to be set up by the main thread
class Peek_Terminal_Input:
   def __enter__(self):
      self.fd = sys.stdin.fileno()
      self.old_settings = termios.tcgetattr(self.fd)
      tty.setraw(self.fd)
      return self
   def __exit__(self, *_):
      termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)


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

   logger.info(f"Got unknown byte sequence {list(seq)}")
   return None


class Screen_Buffer:
   width: int
   height: int
   x_offset: int
   y_offset: int
   mutex: threading.Lock

   data: np.ndarray
   bold: np.ndarray
   dirty_rows: List[bool]
   can_clear: bool

   cursor_pos: Pos
   dirty_cursor: bool

   def __init__(self, width:int, height:int, x_offset:int=0, y_offset:int=0, draw_borders:bool=True, can_clear:bool=True):
      self.height = height
      self.width = width
      self.x_offset = x_offset
      self.y_offset = y_offset
      self.mutex = threading.Lock()

      self.data = np.full((height,width), " ", np.character)
      self.bold = np.zeros((height,width), np.bool_)
      self.dirty_rows = [False for _ in range(height)]
      self.can_clear = can_clear

      self.cursor_pos = Pos(0, 0)
      self.dirty_cursor = False

      if draw_borders:
         init_rect = Rect(0, 0, width, height)
         self.put_text_in(init_rect, 0, 0, "+" + "-"*(width-2) + "+")
         for y in range(1, height-1):
            self.put_text_in(init_rect, 0, y, "|")
            self.put_text_in(init_rect, width-1, y, "|")
         self.put_text_in(init_rect, 0, height-1, "+" + "-"*(width-2) + "+")

   def coord(self, x:int, y:int) -> str:
      return f"\033[{self.y_offset+y+1};{self.x_offset+x+1}H"

   def __assert_shape(self, rect:Rect, x:int, y:int, dx:int, dy:int) -> None:
      assert rect.x1 >= 0 and rect.x2 <= self.width and rect.y1 >= 0 and rect.y2 <= self.height
      assert 0 <= y <= rect.h, f"Expected 0 <= {y} < {rect.h}"
      assert 0 <= x <= rect.w, f"Expected 0 <= {x} < {rect.w}"
      assert 0 <= x+dx <= rect.w, f"Expected 0 <= {x+dx} < {rect.w}"
      assert 0 <= y+dy <= rect.h, f"Expected 0 <= {y+dy} < {rect.h}"

   def put_text_in(self, rect:Rect, x:int, y:int, text:str) -> None:
      self.__assert_shape(rect, x, y, len(text), 0)

      row_y = rect.y1 + y
      start_x = rect.x1 + x

      for i in range(len(text)):
         self.data[row_y, start_x + i] = text[i]
      self.dirty_rows[row_y] = True

   def set_region_bold(self, rect:Rect, x:int, y:int, w:int, h:int, set_bold:bool) -> None:
      assert w > 0 and h > 0
      self.__assert_shape(rect, x, y, w, h)
      self.bold[rect.y1+y:rect.y1+y+h, rect.x1+x:rect.x1+x+w] = set_bold
      for yy in range(rect.y1+y, rect.y1+y+h):
         self.dirty_rows[yy] = True

   def move_cursor(self, x:int, y:int) -> None:
      self.cursor_pos.x = x
      self.cursor_pos.y = y
      self.dirty_cursor = True

   def clear_text(self, rect:Rect) -> None:
      for y in range(rect.h):
         self.put_text_in(rect, 0, y, " "*rect.w)

   def draw(self, only_dirty:bool=True) -> None:
      BOLD_ON_CODE  = "1"
      BOLD_OFF_CODE = "22"

      with self.mutex:
         text = "" if only_dirty or (not self.can_clear) else "\033[2J"
         curr_style = ""
         for y in range(self.height):
            if self.dirty_rows[y] or (not only_dirty):
               text += self.coord(1, y+1)
               for x in range(self.width):
                  code = BOLD_ON_CODE if self.bold[y,x] else BOLD_OFF_CODE
                  target_style = f"\033[{code}m"
                  if curr_style != target_style:
                     text += target_style
                     curr_style = target_style
                  text += self.data[y,x].decode()
               self.dirty_rows[y] = False
         if self.dirty_cursor or len(text) > 0:
            text += self.coord(self.cursor_pos.x + 1, self.cursor_pos.y + 1)
            self.dirty_cursor = False
         if len(text) > 0:
            print(text, end='')
            sys.stdout.flush()


class Image_Screen_Buffer(Screen_Buffer):
   img_x_start: int
   img_x_end: int
   img_cache: Dict[str,List[str]]
   img_rows: List[str]
   void_rows: List[str]
   img_uuid: str = ""

   def __init__(self, width:int, height:int):
      super().__init__(width, height, draw_borders=False)

      self.img_x_start = width - IMAGE_CHARS_WIDE - 1
      self.img_x_end   = width - 1
      self.void_rows = [" "*IMAGE_CHARS_WIDE for _ in range(height-2)]
      not_found = "Image not found"
      self.void_rows[0] = not_found + " "*(IMAGE_CHARS_WIDE-len(not_found))
      self.img_rows = self.void_rows
      self.img_cache = { }

      # Draw initial borders
      init_rect = Rect(0, 0, width, height)
      left_dash  = width - 3 - IMAGE_CHARS_WIDE
      right_dash = width - 3 - left_dash
      self.put_text_in(init_rect, 0, 0, "+" + "-"*left_dash + "+" + "-"*right_dash + "+")
      for y in range(1, height-1):
         self.put_text_in(init_rect, 0, y, "|")
         self.put_text_in(init_rect, width-IMAGE_CHARS_WIDE-2, y, "|")
         self.put_text_in(init_rect, width-1, y, "|")
      self.put_text_in(init_rect, 0, INPUT_SPACE.y1-1, "+" + "-"*left_dash + "+")
      self.put_text_in(init_rect, 0, height-1, "+" + "-"*left_dash + "+" + "-"*right_dash + "+")

   def set_image(self, uuid:str) -> None:
      if self.img_uuid == uuid:
         return
      self.img_rows = self.img_cache.get(uuid, self.void_rows)
      for y in range(1, self.height - 1):
         self.dirty_rows[y] = True

   def draw(self, only_dirty:bool=True) -> None:
      BOLD_ON_CODE  = "1"
      BOLD_OFF_CODE = "22"

      with self.mutex:
         text = "" if only_dirty else "\033[2J"
         curr_style = ""
         for y in range(self.height):
            if self.dirty_rows[y] or (not only_dirty):
               text += self.coord(1, y+1)
               for x in range(self.width):
                  if y >= 1 and y < self.height - 1 and x >= self.img_x_start and x < self.img_x_end:
                     if x == self.img_x_start:
                        text += self.img_rows[y-1]
                  else:
                     code = BOLD_ON_CODE if self.bold[y,x] else BOLD_OFF_CODE
                     target_style = f"\033[{code}m"
                     if curr_style != target_style:
                        text += target_style
                        curr_style = target_style
                     text += self.data[y,x].decode()
               self.dirty_rows[y] = False
         if self.dirty_cursor or len(text) > 0:
            text += self.coord(self.cursor_pos.x + 1, self.cursor_pos.y + 1)
            self.dirty_cursor = False
         if len(text) > 0:
            print(text, end='')
            sys.stdout.flush()


@dataclass
class Input_Data:
   name: str
   event: Type[Event]
   data: Dict
   image_uuid: str
   pointer: int = 0
   text: str = ""


class Text_Box:
   SEPERATOR = " > "
   rect: Rect = INPUT_SPACE
   accepting_input: bool = False

   screen_buffer: Image_Screen_Buffer
   kill_event: threading.Event
   datas: List[Input_Data]
   index: int = 0
   actions_line = ""
   actions_bold: List[Tuple[int,int]]
   waiting_line = "Awaiting model response..."

   def __init__(self, screen_buffer:Image_Screen_Buffer, kill_event:threading.Event, input_complete_callback):
      self.screen_buffer = screen_buffer
      self.kill_event = kill_event
      self.input_complete_callback = input_complete_callback
      self.datas = []
      self.actions_bold = []

   def visualize_game(self, game:Game) -> None:
      curr_loc_id = game.get_curr_loc_id()
      self.datas  = [Input_Data(f"Request Action", E.Player_Request_Action_Event, {}, game.get_loc_image_uuid(curr_loc_id))]

      all_npc_infos = game.get_npc_infos()
      loc_npc_infos = [i for i in all_npc_infos if i.loc_id == curr_loc_id]
      for info in loc_npc_infos:
         self.datas.append(Input_Data(f"Speak to {info.npc_name}", E.Speak_Player_to_Npc_Event, {'npc_id':info.npc_id}, info.image_uuid))
      self.index = 0

      self.actions_line = "Press Tab to Cycle:"
      self.actions_bold = []
      for data in self.datas:
         entry = f" [{data.name}]"
         self.actions_bold.append((len(self.actions_line)+1,len(entry)-1))
         self.actions_line += entry

      self.write_to_buffer()
      self.write_cursor_pos()

   def clear_input(self, accept_input:bool=False):
      self.accepting_input = accept_input
      self.datas = []
      self.index = 0

   def write_to_buffer(self) -> None:
      # Normal buffer writing
      self.screen_buffer.clear_text(self.rect)
      self.screen_buffer.set_region_bold(self.rect, 0, 0, self.rect.w, 1, False)
      if not self.accepting_input:
         self.screen_buffer.put_text_in(self.rect, 0, 0, self.waiting_line)
      else:
         self.screen_buffer.put_text_in(self.rect, 0, 0, self.actions_line)
         bold_start, bold_count = self.actions_bold[self.index]
         self.screen_buffer.set_region_bold(self.rect, bold_start, 0, bold_count, 1, True)
         data = self.datas[self.index]
         text = data.name + self.SEPERATOR + data.text
         for y in range(2, self.rect.h):
            line, text = text[:self.rect.w], text[self.rect.w:]
            line += " "*(self.rect.w - len(line))
            self.screen_buffer.put_text_in(self.rect, 0, y, line)

      # Handle images
      if len(self.datas) > 0:
         image_uuid = self.datas[self.index].image_uuid
         if image_uuid not in self.screen_buffer.img_cache:
            lines_filepath = Save_Data.get_and_make("images", image_uuid, f"{IMAGE_CHARS_WIDE}x{IMAGE_CHARS_TALL}.json", is_file=True)
            if os.path.exists(lines_filepath):
               with open(lines_filepath) as f:
                  lines = json.load(f)
               self.screen_buffer.img_cache[image_uuid] = lines
         self.screen_buffer.set_image(image_uuid)

   def write_cursor_pos(self) -> None:
      if not self.accepting_input:
         self.screen_buffer.move_cursor(self.rect.x1 + len(self.waiting_line), self.rect.y1)
      else:
         data = self.datas[self.index]
         disp_ptr = data.pointer + len(data.name + self.SEPERATOR)
         self.screen_buffer.move_cursor(self.rect.x1 + (disp_ptr % self.rect.w), self.rect.y1 + 2 + (disp_ptr // self.rect.w))
   
   def draw(self) -> None:
      self.write_to_buffer()
      self.write_cursor_pos()
      self.screen_buffer.draw()

   def process_input(self, inp:Union[str,Special_Keys]) -> None:
      if not self.accepting_input or len(self.datas) == 0:
         return

      data = self.datas[self.index]
      if isinstance(inp, str):
         # ASCII character
         if data.pointer >= len(data.text):
            data.text += inp
            data.pointer = len(data.text)
         else:
            data.text = data.text[:data.pointer] + inp + data.text[data.pointer:]
            data.pointer += 1
         self.write_to_buffer()
         self.write_cursor_pos()
      elif isinstance(inp, Special_Keys):
         # Special control character
         if inp == Special_Keys.LEFT:
            data.pointer = max(0, data.pointer - 1)
            self.write_cursor_pos()
            self.screen_buffer.draw()
         elif inp == Special_Keys.RIGHT:
            data.pointer = min(data.pointer + 1, len(data.text))
            self.write_cursor_pos()
            self.screen_buffer.draw()
         elif inp == Special_Keys.BACKSPACE:
            if data.pointer > 0:
               data.text = data.text[:data.pointer-1] + data.text[data.pointer:]
               data.pointer -= 1
               self.write_to_buffer()
               self.write_cursor_pos()
         elif inp == Special_Keys.DELETE:
            if data.pointer < len(data.text):
               data.text = data.text[:data.pointer] + data.text[data.pointer+1:]
               self.write_to_buffer()
         elif inp == Special_Keys.HOME:
            data.pointer = 0
            self.write_cursor_pos()
         elif inp == Special_Keys.END:
            data.pointer = len(data.text)
            self.write_cursor_pos()
         elif inp in (Special_Keys.CTRL_LEFT, Special_Keys.CTRL_RIGHT):
            direction = -1 if inp == Special_Keys.CTRL_LEFT else 1
            walk_ptr = data.pointer
            in_white = True
            while True:
               step_ptr = walk_ptr + direction
               if step_ptr <= 0 or step_ptr >= len(data.text):
                  if step_ptr == 0:
                     walk_ptr = 0
                  break # next step is out-of-bounds
               if data.text[step_ptr] == " ":
                  if not in_white:
                     break
               elif in_white:
                  in_white = False
               walk_ptr = step_ptr
            data.pointer = walk_ptr
            self.write_cursor_pos()
         elif inp in (Special_Keys.TAB, Special_Keys.SHIFT_TAB):
            self.index += (1 if inp == Special_Keys.TAB else -1)
            if self.index >= len(self.datas):
               self.index -= len(self.datas)
            if self.index < 0:
               self.index += len(self.datas)
            self.write_to_buffer()
            self.write_cursor_pos()
         elif inp == Special_Keys.ENTER:
            if len(data.text) < 1:
               logger.error("Cannot submit empty input")
            else:
               self.input_complete_callback(data)

      # Always request a draw (will do nothing if nothing was changed)
      self.screen_buffer.draw()


class Game_Window(ABC):
   NAME: str
   screen_buffer: Screen_Buffer
   accepting_input: bool = False

   def accept_input(self) -> None:
      self.accepting_input = False
   
   def clear_input(self, accept_input:bool=False) -> None:
      self.accepting_input = accept_input

   @abstractmethod
   def visualize_game(self, game:Game) -> None:
      pass

   @abstractmethod
   def write_to_buffer(self) -> None:
      pass

   @abstractmethod
   def process_input(self, inp:Union[str,Special_Keys]) -> None:
      pass


class Empty_Window(Game_Window):
   NAME = "Empty"
   def __init__(self, screen_buffer:Screen_Buffer):
      self.screen_buffer = screen_buffer
   def visualize_game(self, game:Game) -> None:
      pass
   def write_to_buffer(self) -> None:
      pass
   def process_input(self, inp:Union[str,Special_Keys]) -> None:
      pass


class Events_Display(Game_Window):
   NAME = "Events"
   rect: Rect = EVENT_SPACE
   text_box: Text_Box
   screen_buffer: Image_Screen_Buffer
   event_page_index: int = 0
   event_lines: List[str]

   def __init__(self, screen_buffer:Image_Screen_Buffer, kill_event:threading.Event, input_complete_callback):
      self.text_box = Text_Box(screen_buffer, kill_event, input_complete_callback)
      self.screen_buffer = screen_buffer
      self.event_lines = [""]

   def __move_index(self, amount:int) -> None:
      self.event_page_index = max(0, min(len(self.event_lines)-1, self.event_page_index + amount))
      self.write_to_buffer()
      self.screen_buffer.draw()

   def accept_input(self) -> None:
      self.text_box.accepting_input = True
   
   def clear_input(self, accept_input:bool=False) -> None:
      self.text_box.clear_input(accept_input)

   def process_input(self, inp:Union[str,Special_Keys]) -> None:
      if isinstance(inp, str):
         self.text_box.process_input(inp)
      else:
         if inp == Special_Keys.UP:
            self.__move_index(+1)
         elif inp == Special_Keys.DOWN:
            self.__move_index(-1)
         elif inp == Special_Keys.PAGE_UP:
            self.__move_index(+self.rect.h)
         elif inp == Special_Keys.PAGE_DOWN:
            self.__move_index(-self.rect.h)
         else:
            self.text_box.process_input(inp)

   def visualize_game(self, game:Game) -> None:
      self.event_lines = []
      for i, event in enumerate(game.events):
         text = event.player(game)
         if game.new_events > 0 and len(game.events) - i <= game.new_events:
            text = f"* {text}"
         if text is not None:
            while len(text) > self.rect.w:
               self.event_lines.append(text[:self.rect.w])
               text = text[self.rect.w:]
            self.event_lines.append(text)
            self.event_lines.append("")

      self.write_to_buffer()
      self.text_box.visualize_game(game)

   def write_to_buffer(self):
      for i in range(self.rect.h):
         if i + self.event_page_index >= len(self.event_lines):
            line = ""
         else:
            line = self.event_lines[-(i+self.event_page_index+1)]
         self.screen_buffer.put_text_in(self.rect, 0, self.rect.h - i - 1, line + " "*(self.rect.w-len(line)))


class User_Controller(Game_Processor):
   POLL_INTERVAL_SEC = 0.01
   rect: Rect = Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)

   kill_event: threading.Event
   game: Game

   game_windows: List[Game_Window]
   window_index: int = 0

   pause_screen: Screen_Buffer
   pause_rect: Rect
   pause_index: int = 0
   is_paused: bool = False

   done_processing: bool = False

   def __init__(self, kill_event:threading.Event):
      self.kill_event = kill_event
      self.game_windows = [
         Events_Display(Image_Screen_Buffer(SCREEN_WIDTH, SCREEN_HEIGHT), kill_event, self.__user_input_complete),
         Empty_Window(Screen_Buffer(SCREEN_WIDTH, SCREEN_HEIGHT)),
      ]

      pause_width  = 9 + max(len(window.NAME) for window in self.game_windows)
      pause_height = 3 + 2*len(self.game_windows)
      pause_x1 = (self.rect.w - pause_width) // 2
      pause_y1 = (self.rect.h - pause_height) // 2
      self.pause_screen = Screen_Buffer(pause_width, pause_height, pause_x1, pause_y1, can_clear=False)
      self.pause_rect = Rect(0, 0, pause_width, pause_height)

      self.fd = sys.stdin.fileno()
      threading.Thread(target=self.run).start()

   def process_game(self, game:Game, other_proc:Game_Processor) -> Optional[Game]:
      self.done_processing = False

      self.game_windows[self.window_index].accept_input()
      self.peek_game(game)
      self.game = game.reset_event_count()

      while not self.kill_event.is_set():
         if self.done_processing:
            return self.game
         time.sleep(0.01)

      return None

   def peek_game(self, game:Game) -> None:
      self.game_windows[self.window_index].visualize_game(game)
      self.game_windows[self.window_index].screen_buffer.draw()
      self.game = game

   def __user_input_complete(self, data:Input_Data) -> None:
      go_again = data.text.endswith("&")
      if go_again:
         data.text = data.text[:-1]

      if data.event is E.Player_Request_Action_Event:
         self.game.add_event(E.Player_Request_Action_Event(data.text))
      elif data.event is E.Speak_Player_to_Npc_Event:
         self.game.add_event(E.Speak_Player_to_Npc_Event(data.data['npc_id'], data.text))
      else:
         raise RuntimeError(f"{self.__class__.__name__} does not support processing user input from event type {data.event.__name__}")

      self.game_windows[self.window_index].clear_input(accept_input=go_again)
      self.peek_game(self.game)
      if not go_again:
         self.done_processing = True

   def __read_bytes(self) -> bytes:
      while not self.kill_event.is_set():
         if select.select([sys.stdin], [], [], self.POLL_INTERVAL_SEC)[0]:
            return os.read(self.fd, 16)
      return bytes()

   def run(self) -> None:
      try:
         # Prepare the pause screen
         for i, window in enumerate(self.game_windows):
            self.pause_screen.put_text_in(self.pause_rect, 6, 2 + 2*i, window.NAME)
         self.pause_screen.put_text_in(self.pause_rect, 4, 2, ">")
         self.pause_screen.move_cursor(3, 2)

         # Events and Input
         window = self.game_windows[self.window_index]
         window.write_to_buffer()

         # Draw the whole screen
         window.screen_buffer.draw(only_dirty=False)

         # Start our main read and process loop
         while not self.kill_event.is_set():
            seq = self.__read_bytes()
            if len(seq) == 0:
               continue # normally means our kill_event got set
            inp = interpret_bytes(seq)
            if inp is None:
               continue # normally means it's a special key we do not handle

            if isinstance(inp, Special_Keys):
               if inp == Special_Keys.CTRL_C:
                  logger.info("Detected ctrl+c, setting kill event")
                  self.kill_event.set()
               elif inp == Special_Keys.CTRL_R:
                  logger.info("Redrawing entire screen buffer")
                  self.game_windows[self.window_index].screen_buffer.draw(only_dirty=False)
                  continue
               elif inp == Special_Keys.ESCAPE:
                  self.is_paused = not self.is_paused
                  self.game_windows[self.window_index].screen_buffer.draw(only_dirty=False)
                  if self.is_paused:
                     self.pause_screen.draw(only_dirty=False)
                  continue
               elif self.is_paused:
                  if inp in (Special_Keys.DOWN, Special_Keys.UP):
                     self.pause_screen.put_text_in(self.pause_rect, 4, 2 + 2*self.pause_index, " ")
                     amnt = -1 if inp == Special_Keys.DOWN else 1
                     self.pause_index += amnt
                     if self.pause_index < 0:
                        self.pause_index += len(self.game_windows)
                     elif self.pause_index >= len(self.game_windows):
                        self.pause_index -= len(self.game_windows)
                     self.pause_screen.put_text_in(self.pause_rect, 4, 2 + 2*self.pause_index, ">")
                     self.pause_screen.move_cursor(3, 2 + 2*self.pause_index)
                     self.pause_screen.draw(only_dirty=True)
                  elif inp == Special_Keys.ENTER:
                     self.window_index = self.pause_index
                     self.is_paused = False
                     self.game_windows[self.window_index].visualize_game(self.game)
                     self.game_windows[self.window_index].screen_buffer.draw(only_dirty=False)
                  continue

            if not self.is_paused:
               self.game_windows[self.window_index].process_input(inp)

      except Exception as ex:
         logger.error(f"Screen Hanlder ran into error in run")
         for line in traceback.format_exc().split("\n"):
            logger.error(line)
         self.kill_event.set()
         raise ex from ex
