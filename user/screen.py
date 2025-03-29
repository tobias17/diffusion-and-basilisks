from common import Screen_Config

from dataclasses import dataclass
from typing import List, Dict
import sys, threading
import numpy as np


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

      self.img_x_start = width - Screen_Config.image_width() - 1
      self.img_x_end   = width - 1
      self.void_rows = [" "*Screen_Config.image_width() for _ in range(height-2)]
      not_found = "Image not found"
      self.void_rows[0] = not_found + " "*(Screen_Config.image_width()-len(not_found))
      self.img_rows = self.void_rows
      self.img_cache = { }

      # Draw initial borders
      init_rect = Rect(0, 0, width, height)
      left_dash  = width - 3 - Screen_Config.image_width()
      right_dash = width - 3 - left_dash
      self.put_text_in(init_rect, 0, 0, "+" + "-"*left_dash + "+" + "-"*right_dash + "+")
      for y in range(1, height-1):
         self.put_text_in(init_rect, 0, y, "|")
         self.put_text_in(init_rect, width-Screen_Config.image_width()-2, y, "|")
         self.put_text_in(init_rect, width-1, y, "|")
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
