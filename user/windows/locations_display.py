from common import Screen_Config, Save_Data
from game import Game
import events as E
from user import Game_Window, Rect, Image_Screen_Buffer, Special_Keys

from typing import List, Union
import os, json


class Locations_Display(Game_Window):
   NAME = "Locations"
   locs: List[E.Create_Location]
   curr_loc_id: str = ""
   index: int = 0
   rect: Rect
   screen_buffer: Image_Screen_Buffer

   def __init__(self, screen_buffer:Image_Screen_Buffer):
      self.screen_buffer = screen_buffer
      self.rect = Rect(1, 2, self.screen_buffer.width - Screen_Config.image_width() - 3, self.screen_buffer.height - 4)
      self.locs = []

   def process_input(self, inp:Union[str,Special_Keys]) -> None:
      if len(self.locs) == 0:
         return
      if isinstance(inp, str):
         return
      elif inp == Special_Keys.UP:
         self.index = min(self.index + 1, len(self.locs) - 1)
      elif inp == Special_Keys.DOWN:
         self.index = max(self.index - 1, 0)
      else:
         return
      self.write_to_buffer()
      self.screen_buffer.draw()

   def visualize_game(self, game:Game) -> None:
      self.locs = []
      for event in game.events:
         if isinstance(event, E.Create_Location):
            self.locs.insert(0, event)
      assert len(self.locs) > 0
      self.curr_loc_id = game.get_curr_loc_id()
      self.index = 0
      self.write_to_buffer()

   def __to_line(self, info:E.Create_Location, is_selected:bool=False) -> List[str]:
      prefix = "* " if is_selected else ""
      return [
         "",
         prefix + info.name + (" (Here!)" if info.loc_id == self.curr_loc_id else ""),
      ]

   def write_to_buffer(self) -> None:
      self.screen_buffer.clear_text(self.rect)

      # Normal buffer writing
      assert len(self.locs) > 0
      selected_ptr = -1
      all_lines: List[str] = []
      for i, info in enumerate(self.locs):
         if i == self.index:
            selected_ptr = len(all_lines)
         all_lines += self.__to_line(info, is_selected=(i == self.index))
      assert selected_ptr != -1, f"selected_ptr was somehow not set..."
      all_lines.pop(0)

      if len(all_lines) > self.rect.h:
         si = selected_ptr - self.rect.h//2
         ei = si + self.rect.h
         if si < 0:
            si = 0
            ei = self.rect.h
         elif ei >= len(all_lines):
            ei = len(all_lines)
            si = ei - self.rect.h
         all_lines = all_lines[si:ei]

      for i, line in enumerate(all_lines):
         self.screen_buffer.put_text_in(self.rect, 1, self.rect.h-i-1, line)

      # Handle images
      image_uuid = self.locs[self.index].image_uuid
      if image_uuid not in self.screen_buffer.img_cache:
         lines_filepath = Save_Data.get_and_make("images", image_uuid, f"{Screen_Config.image_width()}x{Screen_Config.image_height()}.json", is_file=True)
         if os.path.exists(lines_filepath):
            with open(lines_filepath) as f:
               lines = json.load(f)
            self.screen_buffer.img_cache[image_uuid] = lines
      self.screen_buffer.set_image(image_uuid)
