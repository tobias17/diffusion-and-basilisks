from common import Screen_Config
from game import Game
from user import Rect, Text_Box, Image_Screen_Buffer, Game_Window, Special_Keys
from utils import trim_text

from typing import List, Union
import threading


INPUT_HEIGHT = 6

class Events_Display(Game_Window):
   NAME = "Events"
   rect: Rect
   text_box: Text_Box
   screen_buffer: Image_Screen_Buffer
   event_page_index: int = 0
   event_lines: List[str]

   def __init__(self, screen_buffer:Image_Screen_Buffer, kill_event:threading.Event, input_complete_callback):
      self.rect = Rect(2, 1, Screen_Config.WIDTH - 4 - Screen_Config.image_width(), Screen_Config.HEIGHT - INPUT_HEIGHT - 3)
      tb_rect = Rect(2, self.rect.y2 + 1, Screen_Config.WIDTH - 4 - Screen_Config.image_width(), INPUT_HEIGHT)
      self.text_box = Text_Box(screen_buffer, kill_event, tb_rect, input_complete_callback)
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
            self.__move_index(+self.rect.h//2)
         elif inp == Special_Keys.PAGE_DOWN:
            self.__move_index(-self.rect.h//2)
         else:
            self.text_box.process_input(inp)

   def visualize_game(self, game:Game) -> None:
      self.event_lines = []
      for i, event in enumerate(game.events):
         text = event.player(game)
         if text is not None:
            if game.new_events > 0 and len(game.events) - i <= game.new_events:
               text = f"* {text}"
            self.event_lines += trim_text(text, self.rect.w-2)
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
