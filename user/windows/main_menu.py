from user import Screen_Buffer, Rect, Special_Keys

from typing import List, Optional, Union


MAX_SAVE_NAME_LENGTH = 32

class Main_Menu:
   screen_buffer: Screen_Buffer
   rect: Rect
   lines: List[str]
   line_offset: int
   index: int = 0
   selections: List[str]

   making_new_game: bool = False
   new_game_name: str = ""

   selected_save: Optional[str] = None
   status: Optional[str] = None

   def __init__(self, screen_buffer:Screen_Buffer, saves:List[str]):
      self.screen_buffer = screen_buffer
      self.rect = Rect(1, 1, screen_buffer.width-2, screen_buffer.height-2)
      self.lines = [
         "Diffusion and Basilisks",
         "Created by: tobi",
         "",
         "Ingame Controls",
         "        Ctrl+C | Stop the game           ",
         "        Ctrl+R | Reload the screen       ",
         "        Escape | Brings up the menu items",
         "Up/Down Arrows | Scroll the page up/down ",
         "  Page Up/Down | Scroll the page up/down ",
         "End input with an & character to input again",
         "",
         "Select a Save",
      ]
      self.line_offset = len(self.lines)
      self.selections = saves + ["New Game"]
      self.lines += self.selections
      self.write_to_buffer()

   def process_input(self, inp:Union[str,Special_Keys]) -> None:
      if isinstance(inp, Special_Keys) and inp == Special_Keys.CTRL_R:
         self.write_to_buffer()
         self.screen_buffer.draw(only_dirty=False)
         return

      if self.making_new_game:
         if isinstance(inp, str):
            self.new_game_name += inp
         else:
            if inp == Special_Keys.BACKSPACE:
               if len(self.new_game_name) > 0:
                  self.new_game_name = self.new_game_name[:-1]
            elif inp == Special_Keys.ENTER:
               save_name = self.new_game_name.strip()
               if not save_name:
                  self.status = "Must provide input"
               elif save_name in self.selections:
                  self.status = "A save with that name already exists"
               elif len(save_name) > MAX_SAVE_NAME_LENGTH:
                  self.status = "Name too long"
               else:
                  self.status = "Generating start"
                  self.selected_save = save_name
            else:
               return
      else:
         if isinstance(inp, str):
            return
         if inp in (Special_Keys.UP, Special_Keys.DOWN):
            self.index += -1 if inp == Special_Keys.UP else 1
            if self.index < 0:
               self.index += len(self.selections)
            if self.index >= len(self.selections):
               self.index -= len(self.selections)
         elif inp == Special_Keys.ENTER:
            if self.index == len(self.selections) - 1:
               self.making_new_game = True
            else:
               self.selected_save = self.selections[self.index]
         else:
            return
      self.write_to_buffer()
      self.screen_buffer.draw()
      self.status = None

   def write_to_buffer(self) -> None:
      self.screen_buffer.clear_text(self.rect)
      if self.selected_save:
         y_offset = (self.rect.h - 1) // 2
         line = "Loading game..."
         x_offset = (self.rect.w - len(line)) // 2
         assert x_offset >= 0
         self.screen_buffer.put_text_in(self.rect, x_offset, y_offset, line)
      else:
         if self.making_new_game:
            lines = ["Enter Game Name:", self.new_game_name]
            if self.status is not None:
               lines += ["", self.status]
            y_offset = (self.rect.h - len(lines)) // 2
            for i, line in enumerate(lines):
               x_offset = (self.rect.w - len(line)) // 2
               assert x_offset >= 0
               self.screen_buffer.put_text_in(self.rect, x_offset, y_offset + i, line)
            self.screen_buffer.move_cursor(self.rect.x1 + ((self.rect.w - len(self.new_game_name)) // 2) + len(self.new_game_name), self.rect.y1 + y_offset + 1)
         else:
            y_offset = (self.rect.h - len(self.lines)) // 2
            assert y_offset >= 0
            for i, line in enumerate(self.lines):
               if i - self.line_offset == self.index:
                  line = f">>> {line} <<<"
               x_offset = (self.rect.w - len(line)) // 2
               assert x_offset >= 0
               self.screen_buffer.put_text_in(self.rect, x_offset, y_offset + i, line)
