from __future__ import annotations
from common import Event, Save_Data, logger, Image_Prompt, IMAGE_CHARS_TALL, IMAGE_CHARS_WIDE
import events as E
from game import Game, Game_Processor
from prompts import SYSTEM_MESSAGE, STARTING_USER_MESSAGE, GENERIC_USER_MESSAGE, FINAL_USER_MESSAGE
from functions import Function_Map, parse_function, match_function
from process_images import image_to_ascii

from backends.image import Image_Backend, Tinyapi_Image
from backends.text import Text_Backend, Tinyapi_Text

from typing import List, Dict, Optional, Set
import threading, time, json, os, traceback
from queue import Queue


URL = "http://192.168.1.200:7776/v1"
UPDATE_TIME_DELTA = 2.0


class AI_Backend(Game_Processor):
   kill_event: threading.Event
   image_backend: Image_Backend
   text_backend: Text_Backend
   decision_logs: List[List[Dict]]

   generate_queue:  Queue[Image_Prompt]
   convert_queue:   Queue[str]
   processed_uuids: Set[str]

   def __init__(self, kill_event:threading.Event):
      self.kill_event = kill_event
      self.image_backend = Tinyapi_Image(URL)
      self.text_backend  = Tinyapi_Text(URL)
      self.decision_logs = []

      self.generate_queue = Queue()
      self.convert_queue = Queue()
      self.processed_uuids = set()
      threading.Thread(target=self.__process_generate_queue).start()
      threading.Thread(target=self.__process_convert_queue).start()

   def __get_image_path(self, uuid:str) -> str:
      return Save_Data.get_and_make(Save_Data.images_dirpath, uuid, "image.png", is_file=True)

   def __process_generate_queue(self) -> None:
      try:

         while not self.kill_event.is_set():
            if self.generate_queue.empty():
               time.sleep(0.01)
               continue
            prompt = self.generate_queue.get()
            self.image_backend.generate_image(prompt.text, self.__get_image_path(prompt.uuid))
            self.convert_queue.put(prompt.uuid)

      except Exception as ex:
         logger.error(f"Error in __process_generate_queue() thread")
         for line in traceback.format_exc().split("\n"):
            logger.error(line)
         self.kill_event.set()
         raise ex from ex

   def __process_convert_queue(self) -> None:
      try:

         while not self.kill_event.is_set():
            if self.convert_queue.empty():
               time.sleep(0.01)
               continue
            uuid = self.convert_queue.get()
            image_path = self.__get_image_path(uuid)
            lines = image_to_ascii(image_path, IMAGE_CHARS_TALL, IMAGE_CHARS_WIDE)
            json_path = os.path.join(os.path.dirname(image_path), f"{IMAGE_CHARS_WIDE}x{IMAGE_CHARS_TALL}.json")
            with open(json_path, "w") as f:
               json.dump(lines, f)
            self.processed_uuids.add(uuid)

      except Exception as ex:
         logger.error(f"Error in __process_convert_queue() thread")
         for line in traceback.format_exc().split("\n"):
            logger.error(line)
         self.kill_event.set()
         raise ex from ex

   def __get_messages_from_game(self, game:Game) -> List[Dict[str,str]]:
      class Message_Queue:
         messages: List[Dict[str,str]]
         lines: List[str]
         index: int = 0
         is_user: bool = True

         def __init__(self):
            self.messages = [
               {"role":"system", "content":SYSTEM_MESSAGE.format(api_definition=Function_Map.api_definition())}
            ]
            self.lines = []

         def step(self, event:Event) -> None:
            if self.index == 0 and isinstance(event, (E.Give_Player_Unique_Item, E.Give_Player_Stackable_Items)):
               text = event.system()
               assert text
               self.lines.append(text + "\n")
               return

            if event.is_player_provided() != self.is_user:
               self.accumulate()
            text = event.system()
            if self.is_user:
               assert text
            if text:
               self.lines.append(text)

         def accumulate(self) -> None:
            if self.index == 0:
               assert self.is_user
               self.messages.append({"role":"user", "content":STARTING_USER_MESSAGE.format(starting_events="".join(self.lines))})
            else:
               if self.is_user:
                  self.messages.append({"role":"user", "content":GENERIC_USER_MESSAGE.format(content="\n".join(self.lines))})
               else:
                  self.messages.append({"role":"assistant", "content":"\n".join(self.lines)})

            self.is_user = not self.is_user
            self.lines = []
            self.index += 1

         def finalize(self, g:Game) -> List[Dict[str,str]]:
            assert self.is_user
            quest_str = "".join([f'Quest(quest_id="{q.quest_id}", name="{q.name}", desc="{q.desc}")\n' for q in g.get_active_quests()])
            items_str = ""
            for i in g.get_inventory_items():
               if i.stackable: items_str += f'StackableItem(item_id="{i.item_id}", name="{i.name}", count={i.count}, desc="{i.desc}")\n'
               else:           items_str += f'UniqueItem(item_id="{i.item_id}", name="{i.name}", desc="{i.desc}")\n'
            self.messages.append({"role":"user", "content":FINAL_USER_MESSAGE.format(quests=quest_str, items=items_str, content="\n".join(self.lines))})
            return self.messages

      q = Message_Queue()
      for event in game.events:
         q.step(event)
      return q.finalize(game)

   def __get_next_game_state(self, game:Game, decision_log:List[Dict], max_attempts:int=8) -> Optional[Game]:
      # Create the message JSON object to perform request with
      messages = self.__get_messages_from_game(game)

      # Log the messages in a clean way
      spread_messages = []
      for msg in messages:
         spread_messages.append({ k: (v.split("\n") if k=="content" else v) for k, v in msg.items() })
      decision_log.append({"event":"Computed API Messages", "messages":spread_messages})

      # Get model response with retry attempts
      for _ in range(max_attempts):
         if self.kill_event.is_set():
            return None

         output = self.text_backend.generate_response(messages)
         assert output is not None, f"Ran out of outputs before completing processing"
         if not output.isascii():
            decision_log.append({"output":output.split("\n"), "event":"ERROR: Model output was not ascii"})
            continue

         lines = output.split("\n")
         lines = [l.strip() for l in lines if l]

         if len(lines) == 0:
            decision_log.append({"output":output.split("\n"), "event":"ERROR: Got back 0 lines from the model"})
         else:
            delta_game = game.copy(reset_event_count=True)
            for line in lines:
               call_data, msg = parse_function(line) # type: ignore
               if call_data is None:
                  logger.error(msg)
                  decision_log.append({"output":output.split("\n"), "event":"ERROR: Ran into issue parsing function", "message":msg, "on_line":line})
                  break
               func_call, msg = match_function(call_data.name, call_data.args, call_data.kwargs, Function_Map.funcs) # type: ignore
               if func_call is None:
                  logger.error(msg)
                  decision_log.append({"output":output.split("\n"), "event":"ERROR: Ran into issue matching function", "message":msg, "on_line":line})
                  break
               ok, msg = func_call(delta_game)
               if not ok:
                  logger.error(msg)
                  decision_log.append({"output":output.split("\n"), "event":"ERROR: Got Back Not-OK Calling Function", "message":msg, "on_line":line})
                  break
            else:
               decision_log.append({"output":output.split("\n"), "event":"Fully processed output and advanced game state"})
               return delta_game

      return None

   def __wait_for_uuid(self, uuid:str):
      while not self.kill_event.is_set():
         if uuid in self.processed_uuids:
            return
         time.sleep(0.05)

   def process_game(self, game:Game, other_proc:Game_Processor) -> Optional[Game]:
      next_update_time = time.time() + UPDATE_TIME_DELTA/2

      # Get the next game state from the AI
      decision_log: List[Dict] = []
      ai_game = self.__get_next_game_state(game, decision_log)

      # Save the decision log
      self.decision_logs.append(decision_log)
      with open(Save_Data.get_and_make(Save_Data.logs_dirpath, "decisions.json", is_file=True), "w") as f:
         json.dump(self.decision_logs, f, indent="\t")

      if ai_game is None or self.kill_event.is_set():
         return None
      delta_game = game.copy(reset_event_count=True)
      delta_events = ai_game.events[len(game.events):]

      # Queue up all images required
      for event in delta_events:
         prompt = event.image_prompt()
         if prompt is not None:
            self.generate_queue.put(prompt)

      # Slowly process game events while sending them to the other processor
      while len(delta_events) > 0:
         if self.kill_event.is_set():
            return None
         if time.time() > next_update_time:
            next_event = delta_events.pop(0)
            prompt = next_event.image_prompt()
            if prompt is not None:
               self.__wait_for_uuid(prompt.uuid)
               if self.kill_event.is_set():
                  return None
            delta_game.add_event(next_event)
            other_proc.peek_game(delta_game)
            next_update_time = time.time() + UPDATE_TIME_DELTA # intentionally call time.time() again
         else:
            time.sleep(0.05)

      return ai_game
