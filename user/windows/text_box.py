from common import logger, Event, Save_Data, Screen_Config
from game import Game
import events as E
from user import Rect, Image_Screen_Buffer, Special_Keys

from typing import Type, Dict, List, Tuple, Union
from dataclasses import dataclass
import threading, os, json


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
   rect: Rect
   accepting_input: bool = False

   screen_buffer: Image_Screen_Buffer
   kill_event: threading.Event
   datas: List[Input_Data]
   index: int = 0
   actions_line = ""
   actions_bold: List[Tuple[int,int]]
   waiting_line = "Awaiting model response..."

   def __init__(self, screen_buffer:Image_Screen_Buffer, kill_event:threading.Event, rect:Rect, input_complete_callback):
      self.rect = rect
      self.screen_buffer = screen_buffer
      self.kill_event = kill_event
      self.input_complete_callback = input_complete_callback
      self.datas = []
      self.actions_bold = []
      self.screen_buffer.put_text_in(Rect(0, self.rect.y1-1, self.rect.w+3, self.rect.h-1), 0, 0, "+" + "-"*(self.rect.w+1) + "+") # kinda hacky but best with current architecture

   def visualize_game(self, game:Game) -> None:
      curr_loc_id = game.get_curr_loc_id()
      latest_event = 0
      for i, event in enumerate(reversed(game.events)):
         if isinstance(event, E.Player_Request_Action):
            latest_event = max(latest_event, len(game.events) - i - 1)
         elif isinstance(event, E.Move_Player_To) or (isinstance(event, E.Create_Location) and event.automove_player_to):
            curr_loc_id = event.loc_id
            latest_event = max(latest_event, len(game.events) - i - 1)
            self.index = 0
            break
      else:
         raise ValueError(f"Somehow found 0 move to events")
      self.datas  = [Input_Data(f"Request Action", E.Player_Request_Action, {}, game.get_loc_image_uuid(curr_loc_id))]

      all_npc_infos = game.get_npc_infos()
      loc_npc_infos = [i for i in all_npc_infos if i.loc_id == curr_loc_id]
      for info in loc_npc_infos:
         if info.last_interaction > latest_event:
            latest_event = info.last_interaction
            self.index = len(self.datas)
         self.datas.append(Input_Data(f"Speak to {info.npc_name}", E.Speak_Player_to_Npc, {'npc_id':info.npc_id}, info.image_uuid))

      self.actions_line = ""
      self.actions_bold = []
      for data in self.datas:
         entry = f"[{data.name}] "
         self.actions_bold.append((len(self.actions_line),len(entry)-1))
         self.actions_line += entry

      self.write_to_buffer()
      self.write_cursor_pos()

   def clear_input(self, accept_input:bool=False):
      self.accepting_input = accept_input

   def write_to_buffer(self) -> None:
      # Normal buffer writing
      self.screen_buffer.clear_text(self.rect)
      self.screen_buffer.set_region_bold(self.rect, 0, 0, self.rect.w, 1, False)
      if not self.accepting_input:
         self.screen_buffer.put_text_in(self.rect, 0, 0, self.waiting_line)
      else:
         actions_prefix = "Press Tab to Cycle: "
         actions_width = self.rect.w - len(actions_prefix) - 2
         actions_line = self.actions_line
         orig_size = len(actions_line)
         bold_start, bold_count = self.actions_bold[self.index]
         if len(actions_line) > actions_width:
            pad_rem = actions_width - bold_count
            left_i  = bold_start - (pad_rem // 2)
            right_i = left_i + actions_width
            if left_i < 0:
               left_i  = 0
               right_i = actions_width
            elif right_i >= actions_width:
               right_i = len(actions_line) - 1
               left_i  = right_i - actions_width
            actions_line = actions_line[left_i:right_i]
            if left_i > 0:
               actions_line = "..." + actions_line[3:]
            if right_i < orig_size - 1:
               actions_line = actions_line[:-3] + "..."
            bold_start -= left_i
         self.screen_buffer.put_text_in(self.rect, 0, 0, actions_prefix+actions_line)
         self.screen_buffer.set_region_bold(self.rect, bold_start+len(actions_prefix), 0, bold_count, 1, True)
         data = self.datas[self.index]
         text = data.name + self.SEPERATOR + data.text
         for y in range(2, self.rect.h):
            line, text = text[:self.rect.w], text[self.rect.w:]
            line += " "*(self.rect.w - len(line))
            self.screen_buffer.put_text_in(self.rect, 0, y, line)

      # Handle images
      image_uuid = self.datas[self.index].image_uuid
      if image_uuid not in self.screen_buffer.img_cache:
         lines_filepath = Save_Data.get_and_make("images", image_uuid, f"{Screen_Config.image_width()}x{Screen_Config.image_height()}.json", is_file=True)
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
