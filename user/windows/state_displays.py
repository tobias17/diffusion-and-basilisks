from game import Game
from user import Game_Window, Rect, Screen_Buffer
from utils import trim_text

from typing import List


class State_Display(Game_Window):
   lines: List[str]
   index: int = 0
   rect: Rect
   def __init__(self, screen_buffer:Screen_Buffer):
      self.screen_buffer = screen_buffer
      self.rect = Rect(2, 2, self.screen_buffer.width - 4, self.screen_buffer.height - 4)
      self.lines = []
   def write_to_buffer(self) -> None:
      for i in range(self.rect.h):
         if i + self.index >= len(self.lines):
            line = ""
         else:
            line = self.lines[-(i+self.index+1)]
         self.screen_buffer.put_text_in(self.rect, 0, self.rect.h - i - 1, line + " "*(self.rect.w-len(line)))


class Quests_Display(State_Display):
   NAME = "Quests"
   def visualize_game(self, game:Game) -> None:
      self.lines = []
      quests = game.get_active_quests()
      if len(quests) == 0:
         self.lines.append("You have no quests.")
      else:
         for item in quests:
            self.lines += trim_text(f"{item.name}: {item.desc}", self.rect.w-2) + [""]
         self.lines.pop(-1) # remove last newline
      self.index = 0
      self.write_to_buffer()


class Inventory_Display(State_Display):
   NAME = "Inventory"
   def visualize_game(self, game:Game) -> None:
      self.lines = []
      items = game.get_inventory_items()
      if len(items) == 0:
         self.lines.append("You have no items.")
      else:
         for item in reversed(items):
            self.lines += trim_text((f"{item.count} " if item.stackable else "") + f"{item.name}: {item.desc}", self.rect.w-2) + [""]
         self.lines.pop(-1) # remove last newline
      self.index = 0
      self.write_to_buffer()
