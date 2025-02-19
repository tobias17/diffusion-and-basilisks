from __future__ import annotations
from common import logger, Event
from game import Game
import events as E

from dataclasses import dataclass
from typing import List, Union, Optional
from enum import Enum, auto
from queue import Queue
from abc import ABC, abstractmethod
import numpy as np
import sys, termios, select, tty, os, traceback, threading

SCREEN_WIDTH  = 200
SCREEN_HEIGHT = 45

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

EVENT_SPACE = Rect(2, 5, SCREEN_WIDTH - 4, SCREEN_HEIGHT - INPUT_HEIGHT - 7)
INPUT_SPACE = Rect(2, EVENT_SPACE.y2 + 1, SCREEN_WIDTH - 4, INPUT_HEIGHT)


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
   height: int
   width: int
   mutex: threading.Lock

   data: np.ndarray
   bold: np.ndarray
   dirty_rows: List[bool]

   cursor_pos: Pos
   dirty_cursor: bool

   def __init__(self, width:int, height:int):
      self.height = height
      self.width = width
      self.mutex = threading.Lock()

      self.data = np.full((height,width), " ", np.character)
      self.bold = np.zeros((height,width), np.bool_)
      self.dirty_rows = [False for _ in range(height)]

      self.cursor_pos = Pos(0, 0)
      self.dirty_cursor = False
   
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

   def draw(self, only_dirty:bool=True) -> None:
      BOLD_ON_CODE  = "1"
      BOLD_OFF_CODE = "22"

      with self.mutex:
         text = "" if only_dirty else "\033[2J"
         curr_style = ""
         for y in range(self.height):
            if self.dirty_rows[y] or (not only_dirty):
               text += coord(1, y+1)
               for x in range(self.width):
                  codes = [
                     BOLD_ON_CODE if self.bold[y,x] else BOLD_OFF_CODE,
                  ]
                  target_style = f"\033[" + ";".join(codes) + "m"
                  if curr_style != target_style:
                     text += target_style
                     curr_style = target_style
                  text += self.data[y,x].decode()
               self.dirty_rows[y] = False
         if self.dirty_cursor or len(text) > 0:
            text += coord(self.cursor_pos.x + 1, self.cursor_pos.y + 1)
            self.dirty_cursor = False
         if len(text) > 0:
            print(text, end='')
            sys.stdout.flush()


class Text_Box():
   rect: Rect = INPUT_SPACE
   screen_buffer: Screen_Buffer
   accepting_input: bool = True
   enabled: bool = True
   curr_input: str = ""

   def __init__(self, screen_buffer:Screen_Buffer):
      self.screen_buffer = screen_buffer

   def process_input(self, inp:Union[str,Special_Keys]) -> None:
      pass

   def clear_input(self) -> None:
      pass

   def write_to_buffer(self) -> None:
      self.screen_buffer.put_text_in(self.rect, 0, 0, " "*self.rect.w)

   def write_cursor_pos(self) -> None:
      self.screen_buffer.move_cursor(self.rect.x1, self.rect.y1)

   def draw(self) -> None:
      self.write_to_buffer()
      self.write_cursor_pos()
      self.screen_buffer.draw()


class Real_Text_Box(Text_Box):
   kill_event: threading.Event
   input_prefix: str
   input_ptr: int

   def __init__(self, input_prefix:str, screen_buffer:Screen_Buffer, kill_event:threading.Event, input_complete_callback):
      self.input_prefix = input_prefix
      self.screen_buffer = screen_buffer
      self.kill_event = kill_event
      self.input_complete_callback = input_complete_callback
      self.clear_input()

   def clear_input(self):
      self.input_ptr = 0
      self.curr_input = ""

   def write_to_buffer(self) -> None:
      text = self.input_prefix + self.curr_input
      for y in range(self.rect.h):
         line, text = text[:self.rect.w], text[self.rect.w:]
         line += " "*(self.rect.w - len(line))
         self.screen_buffer.put_text_in(self.rect, 0, y, line)

   def write_cursor_pos(self) -> None:
      disp_ptr = self.input_ptr + len(self.input_prefix)
      self.screen_buffer.move_cursor(self.rect.x1 + (disp_ptr % self.rect.w), self.rect.y1 + (disp_ptr // self.rect.w))

   def process_input(self, inp:Union[str,Special_Keys]) -> None:
      if not self.accepting_input or not self.enabled:
         return

      if isinstance(inp, str):
         # ASCII character
         if self.input_ptr >= len(self.curr_input):
            self.curr_input += inp
            self.input_ptr = len(self.curr_input)
         else:
            self.curr_input = self.curr_input[:self.input_ptr] + inp + self.curr_input[self.input_ptr:]
            self.input_ptr += 1
         self.write_to_buffer()
         self.write_cursor_pos()
      elif isinstance(inp, Special_Keys):
         # Special control character
         if inp == Special_Keys.LEFT:
            self.input_ptr = max(0, self.input_ptr - 1)
            self.write_cursor_pos()
            self.screen_buffer.draw()
         elif inp == Special_Keys.RIGHT:
            self.input_ptr = min(self.input_ptr + 1, len(self.curr_input))
            self.write_cursor_pos()
            self.screen_buffer.draw()
         elif inp == Special_Keys.BACKSPACE:
            if self.input_ptr > 0:
               self.curr_input = self.curr_input[:self.input_ptr-1] + self.curr_input[self.input_ptr:]
               self.input_ptr -= 1
               self.write_to_buffer()
               self.write_cursor_pos()
         elif inp == Special_Keys.DELETE:
            if self.input_ptr < len(self.curr_input):
               self.curr_input = self.curr_input[:self.input_ptr] + self.curr_input[self.input_ptr+1:]
               self.write_to_buffer()
         elif inp == Special_Keys.HOME:
            self.input_ptr = 0
            self.write_cursor_pos()
         elif inp == Special_Keys.END:
            self.input_ptr = len(self.curr_input)
            self.write_cursor_pos()
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
            self.write_cursor_pos()
         elif inp == Special_Keys.ENTER:
            if len(self.curr_input) < 1:
               logger.error("Cannot submit empty input")
            else:
               self.input_complete_callback()

      # Always request a draw (will do nothing if nothing was changed)
      self.screen_buffer.draw()


class Tab_Page(ABC):
   rect: Rect = EVENT_SPACE
   title: str
   text_box: Text_Box
   screen_buffer: Screen_Buffer
   is_visible: bool = False

   @abstractmethod
   def update_game(self, game:Game) -> None:
      pass

   def clear_buffer(self):
      for y in range(self.rect.h):
         self.screen_buffer.put_text_in(self.rect, 0, y, " "*self.rect.w)

   @abstractmethod
   def write_to_buffer(self):
      pass

   @abstractmethod
   def process_input(self, inp:Union[str,Special_Keys]) -> None:
      pass


class Action_Display(Tab_Page):
   event_page_index: int = 0
   event_lines: List[str]
   
   def __init__(self, screen_buffer:Screen_Buffer, game:Game, kill_event:threading.Event, input_complete_callback):
      self.title = "Actions"
      self.text_box = Real_Text_Box("Act > ", screen_buffer, kill_event, input_complete_callback)
      self.screen_buffer = screen_buffer
      self.update_game(game)
   
   def __move_index(self, amount:int) -> None:
      logger.info(f"Before: {self.event_page_index}")
      self.event_page_index = max(0, min(len(self.event_lines)-1, self.event_page_index + amount))
      logger.info(f"After:  {self.event_page_index}")
      self.write_to_buffer()
      self.screen_buffer.draw()

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

   def update_game(self, game:Game) -> None:
      self.event_lines = []
      for event in game.events:
         text = event.player_event(game)
         if text is not None:
            while len(text) > self.rect.w:
               self.event_lines.append(text[:self.rect.w])
               text = text[self.rect.w:]
            self.event_lines.append(text)
            self.event_lines.append("")

      if self.is_visible:
         self.clear_buffer()
         self.write_to_buffer()

   def write_to_buffer(self):
      for i in range(self.rect.h):
         if i + self.event_page_index >= len(self.event_lines):
            line = ""
         else:
            line = self.event_lines[-(i+self.event_page_index+1)]
         self.screen_buffer.put_text_in(self.rect, 0, self.rect.h - i - 1, line + " "*(self.rect.w-len(line)))


class Speech_Display(Tab_Page):
   screen_buffer: Screen_Buffer
   game: Game
   speak_target: Optional[str] = None
   speech_page_index: int = 0
   speech_lines: List[str]
   
   def __init__(self, screen_buffer:Screen_Buffer, game:Game, kill_event:threading.Event, input_complete_callback):
      self.title = "Speaking"
      self.text_box = Real_Text_Box("Say > ", screen_buffer, kill_event, input_complete_callback)
      self.screen_buffer = screen_buffer
      self.update_game(game)
   
   def __move_index(self, amount:int) -> None:
      self.speech_page_index = max(0, min(len(self.speech_lines), self.speech_page_index + amount))
      self.write_to_buffer()
      self.screen_buffer.draw()

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

   def set_speak_target(self, npc_id:str) -> None:
      self.speak_target = npc_id
      self.speech_lines = [f"Start of conversation with {self.game.get_npc_name(npc_id)}", ""]
      for event in self.game.events:
         if isinstance(event, E.Speak_Event) and event.npc_id == npc_id:
            line = event.player_speak(self.game)
            assert line is not None
            while len(line) > self.rect.w:
               self.speech_lines.append(line[:self.rect.w])
               line = line[self.rect.w:]
            self.speech_lines.append(line)
            self.speech_lines.append("")
      if self.is_visible:
         self.clear_buffer()
         self.write_to_buffer()

   def update_game(self, game:Game) -> None:
      self.game = game
      npc_infos = game.get_npc_infos()
      curr_loc_id = game.get_curr_loc_id()
      curr_loc_npc_infos = [i for i in npc_infos if i.loc_id == curr_loc_id]

      if len(curr_loc_npc_infos) > 0:
         curr_loc_npc_infos = sorted(curr_loc_npc_infos, key=lambda i: i.last_interaction)
         self.set_speak_target(curr_loc_npc_infos[-1].npc_id)
         self.text_box.enabled = True
      else:
         self.speak_target = None
         self.text_box.enabled = False

   def write_to_buffer(self):
      self.clear_buffer()
      if self.speak_target is not None:
         for i in range(self.rect.h):
            if i >= len(self.speech_lines):
               break
            self.screen_buffer.put_text_in(self.rect, 0, self.rect.h - i - 1, self.speech_lines[-(i+1)])


class Tab_Selection:
   SPACE_PADDING = 3
   screen_buffer: Screen_Buffer
   pages: List[Tab_Page]
   names: List[str]
   rect: Rect

   def __init__(self, screen_buffer:Screen_Buffer, pages:List[Tab_Page]):
      self.screen_buffer = screen_buffer
      self.pages = pages
      self.names = [tab.title for tab in pages]
      width = 1
      for name in self.names:
         width += self.SPACE_PADDING*2 + len(name) + 1
      self.rect = Rect(0, 0, width, 5)

   def write_to_buffer(self) -> None:
      text_row = "|" + "|".join(" "*self.SPACE_PADDING + n + " "*self.SPACE_PADDING for n in self.names) + "|"
      gap_row = "|" + "|".join(" "*self.SPACE_PADDING + " "*len(n) + " "*self.SPACE_PADDING for n in self.names) + "|"
      border_row = "+" + "+".join("-"*(self.SPACE_PADDING*2 + len(n)) for n in self.names) + "+"
      self.screen_buffer.put_text_in(self.rect, 0, 0, border_row)
      self.screen_buffer.put_text_in(self.rect, 0, 1, gap_row)
      self.screen_buffer.put_text_in(self.rect, 0, 2, text_row)
      self.screen_buffer.put_text_in(self.rect, 0, 3, gap_row)
      self.screen_buffer.put_text_in(self.rect, 0, 4, border_row)

   def select(self, index:int) -> None:
      text = ""
      for i, n in enumerate(self.names):
         self.screen_buffer.set_region_bold(self.rect, len(text)+2, 2, len(n) + 2*self.SPACE_PADDING - 4, 1, i == index)
         text += "|" if (i == index and i == 0) else "+"
         text += (" " if i == index else "-") * (len(n) + 2*self.SPACE_PADDING)
      text += "+"
      self.screen_buffer.put_text_in(self.rect, 0, 4, text)
      for i, page in enumerate(self.pages):
         page.is_visible = (i == index)
         if page.is_visible:
            page.write_to_buffer()
            page.text_box.write_to_buffer()
            page.text_box.write_cursor_pos()


class Screen_Handler:
   POLL_INTERVAL_SEC = 0.01
   rect: Rect = Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)

   kill_event: threading.Event
   user_input_queue: Queue[Event]
   screen_buffer: Screen_Buffer

   tab_selection: Tab_Selection
   tab_pages: List[Tab_Page]
   tab_index = 0

   def __init__(self, kill_event:threading.Event, game:Game, user_input_queue:Queue[Event]):
      self.kill_event = kill_event
      self.user_input_queue = user_input_queue
      self.screen_buffer = Screen_Buffer(SCREEN_WIDTH, SCREEN_HEIGHT)
      self.tab_pages = [
         Action_Display (self.screen_buffer, game, kill_event, self.__user_input_complete),
         Speech_Display(self.screen_buffer, game, kill_event, self.__user_input_complete),
      ]
      self.tab_selection = Tab_Selection(self.screen_buffer, self.tab_pages)
      self.fd = sys.stdin.fileno()

   def update_game(self, game:Game) -> None:
      for page in self.tab_pages:
         page.update_game(game)
      self.screen_buffer.draw()

   def accept_input(self) -> None:
      for page in self.tab_pages:
         page.text_box.accepting_input = True

   def __user_input_complete(self) -> None:
      curr_tab = self.tab_pages[self.tab_index]
      text = curr_tab.text_box.curr_input
      assert text
      for page in self.tab_pages:
         page.text_box.clear_input()
         page.text_box.accepting_input = False
      curr_tab.text_box.draw()

      event: Event
      if isinstance(curr_tab, Action_Display):
         event = E.Player_Request_Action_Event(text)
      elif isinstance(curr_tab, Speech_Display):
         assert curr_tab.speak_target is not None
         event = E.Speak_Event(curr_tab.speak_target, text, True)
         self.tab_index = 0
         self.tab_selection.select(self.tab_index)
      else:
         raise ValueError(f"Got input complete callback from {type(curr_tab)}, should not have happened")
      self.user_input_queue.put(event)

   def __read_bytes(self) -> bytes:
      while not self.kill_event.is_set():
         if select.select([sys.stdin], [], [], self.POLL_INTERVAL_SEC)[0]:
            return os.read(self.fd, 16)
      return bytes()

   def change_tab(self, amount:int) -> None:
      self.tab_index += amount
      if self.tab_index < 0:
         self.tab_index += len(self.tab_pages)
      if self.tab_index >= len(self.tab_pages):
         self.tab_index -= len(self.tab_pages)
      self.tab_selection.select(self.tab_index)
      self.screen_buffer.draw()

   def run(self) -> None:
      try:
         # Borders
         self.screen_buffer.put_text_in(self.rect, 0, 4, "+" + "-"*(SCREEN_WIDTH-2) + "+")
         for y in range(5, SCREEN_HEIGHT-1):
            self.screen_buffer.put_text_in(self.rect, 0, y, "|")
            self.screen_buffer.put_text_in(self.rect, SCREEN_WIDTH-1, y, "|")
         self.screen_buffer.put_text_in(self.rect, 0, SCREEN_HEIGHT-1, "+" + "-"*(SCREEN_WIDTH-2) + "+")
         self.screen_buffer.put_text_in(self.rect, 0, INPUT_SPACE.y1-1, "+" + "-"*(SCREEN_WIDTH-2) + "+")

         # Tabs
         self.tab_selection.write_to_buffer()
         self.tab_selection.select(self.tab_index)

         # User Input
         text_box = self.tab_pages[self.tab_index].text_box
         text_box.write_to_buffer()
         text_box.write_cursor_pos()

         # Draw the whole screen
         self.screen_buffer.draw(only_dirty=False)

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
                  self.screen_buffer.draw(only_dirty=False)
               elif inp == Special_Keys.TAB:
                  self.change_tab(+1)
                  continue
               elif inp == Special_Keys.SHIFT_TAB:
                  self.change_tab(-1)
                  continue

            self.tab_pages[self.tab_index].process_input(inp)

      except Exception:
         logger.error(f"Screen Hanlder ran into error in run")
         for line in traceback.format_exc().split("\n"):
            logger.error(line)
         self.kill_event.set()
