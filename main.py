from common import logger, LOG_FORMAT, Event, Save_Data
from prompts import SYSTEM_MESSAGE, FINAL_USER_MESSAGE
from functions import Function_Map, parse_function, match_function
import events as E
from game import Game
from screen_handler import Screen_Handler, Peek_Terminal_Input

from typing import Callable, Optional, List, Dict, Tuple
import logging, os, datetime, json, requests, time, threading, base64 # type: ignore
from queue import Queue
from io import BytesIO
from PIL import Image
import shutil

def process_game_state(game:Game, output_from_messages:Callable[[List[Dict[str,str]]],Optional[str]], kill_event:threading.Event, decision_log:List[Dict], max_attempts:int=8) -> Optional[Game]:

   # Create the message JSON object to perform request with
   messages = [
      {"role":"system", "content":SYSTEM_MESSAGE.format(api_definition=Function_Map.api_definition())}
   ]
   lines: List[str] = []
   for event in game.events:
      if event.is_player_provided():
         if len(lines) > 0:
            messages.append({"role":"assistant", "content":"\n".join(lines)})
            lines = []
         text = event.system()
         assert text
         messages.append({"role":"user", "content":text})
      else:
         line = event.system()
         if line: lines.append(line)
   if len(lines) > 0:
      logger.warning(f"Got assistant events at the end of the game when requesting AI response, skipping")

   # Update last message
   quest_str = "".join([f'Quest(quest_id="{q.quest_id}", name="{q.name}", desc="{q.desc}")\n' for q in game.get_active_quests()])
   messages[-1]["content"] = FINAL_USER_MESSAGE.format(quests=quest_str, content=messages[-1]["content"])

   # Log the messages in a clean way
   spread_messages = []
   for msg in messages:
      spread_messages.append({ k: (v.split("\n") if k=="content" else v) for k, v in msg.items() })
   decision_log.append({"event":"Computed API Messages", "messages":spread_messages})

   # Get model response with retry attempts
   for _ in range(max_attempts):
      if kill_event.is_set():
         return None

      output = output_from_messages(messages)
      assert output is not None, f"Ran out of outputs before completing processing"
      if not output.isascii():
         decision_log.append({"output":output.split("\n"), "event":"ERROR: Model output was not ascii"})
         continue

      lines = output.split("\n")
      lines = [l.strip() for l in lines if l]

      if len(lines) == 0:
         decision_log.append({"output":output.split("\n"), "event":"ERROR: Got back 0 lines from the model"})
      else:
         delta_game = game.copy()
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


ENDPOINT = "http://192.168.1.200:7776/v1"


def make_completion(messages:List[Dict[str,str]]) -> Optional[str]:
   resp = requests.post(
      f"{ENDPOINT}/chat/completions",
      headers={"Content-Type":"application/json"},
      json={"messages":messages}
   )

   if resp.status_code == 200:
      body = resp.text.split(":", 1)[-1].strip()
      try:
         data = json.loads(body)
      except Exception as ex:
         logger.error(f"Failed to load json data:\n{body}")
         raise ex from ex
      return data["choices"][0]["message"]["content"] # type: ignore
   else:
      logger.info(f"Got back: {resp.text}")
      raise RuntimeError(f"Endpoint returned non-200 status code {resp.status_code}")


class AI_Manager:
   MAX_ATTEMPTS: int = 8
   kill_event: threading.Event
   log_dirpath: str
   decision_logs: List[List[Dict]]

   def __init__(self, kill_event:threading.Event, log_dirpath:str, game_filepath:str):
      self.kill_event = kill_event
      self.log_dirpath = log_dirpath
      self.game_filepath = game_filepath
      self.decision_logs = []

   def process(self, game:Game) -> Optional[Game]:
      final_game = None
      decision_log = []
      decision_log.append({"event":f"Performing Game Loop Tick", "message":"Requesting LLM completion"})

      new_game = process_game_state(game, make_completion, self.kill_event, decision_log)
      if new_game is not None:
         final_game = new_game

      self.decision_logs.append(decision_log)
      save_game = game if final_game is None else final_game
      with open(self.game_filepath, "w") as f: json.dump(save_game.to_json(), f, indent="\t")
      with open(f"{self.log_dirpath}/decision_log.json", "w") as f: json.dump(self.decision_logs,  f, indent="\t")

      return final_game


class Image_Generator:
   kill_event: threading.Event
   input_queue: Queue[Tuple[str,str]]
   completed_uuids: set[str]

   def __init__(self, kill_event:threading.Event):
      self.kill_event = kill_event
      self.input_queue = Queue()
      self.completed_uuids = set()
      threading.Thread(target=self.__process_queue).start()

   def __process_queue(self):
      while not self.kill_event.is_set():
         if self.input_queue.empty():
            time.sleep(0.01)
         else:
            uuid, prompt = self.input_queue.get()
            try:
               response = requests.post(
                  f"{ENDPOINT}/txt2img",
                  headers={"Content-Type":"application/json"},
                  json={"prompt":f"high fantasy, portrait, {prompt}, pixel art"},
                  stream=True
               )

               if response.status_code == 200:
                  body = response.text.split(":", 1)[-1].strip()
                  try:
                     data = json.loads(body)
                  except Exception as ex:
                     print(f"Failed to load json data:\n{body}")
                     raise ex from ex
                  image_b64 = data["image"]
                  image = Image.open(BytesIO(base64.b64decode(image_b64)))
                  image.save(Save_Data.get_and_make("images", uuid, "image.png", is_file=True))
               else:
                  logger.error("Got back non-200 code from image API:")
                  for line in response.text.split("\n"):
                     logger.error(line)
            except Exception as ex:
               logger.error(f"Ran into exception while processing image API request: {ex}")
            finally:
               self.completed_uuids.add(uuid)

   def wait_for(self, uuid:str) -> None:
      while not self.kill_event.is_set():
         if uuid in self.completed_uuids:
            return
         time.sleep(0.05)


def game_loop(init_game:Game, log_dirpath:str, game_dirpath:str):
   kill_event = threading.Event()
   ai_manager = AI_Manager(kill_event, log_dirpath, game_dirpath)
   image_gen  = Image_Generator(kill_event)
   user_input_queue: Queue[Game] = Queue(maxsize=1)

   # Create a screen handler object and start it up
   screen_handler = Screen_Handler(kill_event, init_game, user_input_queue)
   thread = threading.Thread(target=screen_handler.run)
   thread.start()

   UPDATE_TIME_DELTA = 1.0
   next_update_time  = 0.0

   # Main game loop
   try:
      while not kill_event.is_set():
         if user_input_queue.full():
            user_game = user_input_queue.get()
            next_update_time = time.time() + UPDATE_TIME_DELTA

            logger.info("New event detected, processing AI response")
            ai_game = ai_manager.process(user_game)
            if ai_game is None:
               logger.error("Could not progress game state with AI, reverting user input")
               screen_handler.accept_input(init_game)
            else:
               logger.info("Got back AI response, processing new events")
               delta_game = user_game.copy()
               delta_events = ai_game.events[len(user_game.events):]

               for event in delta_events:
                  uuid_and_prompt = event.uuid_and_prompt()
                  if uuid_and_prompt is not None:
                     image_gen.input_queue.put(uuid_and_prompt)

               while len(delta_events) > 0:
                  if kill_event.is_set():
                     return
                  curr_time = time.time()
                  if curr_time > next_update_time:
                     uuid_and_prompt = delta_events[0].uuid_and_prompt()
                     if uuid_and_prompt is not None:
                        image_gen.wait_for(uuid_and_prompt[0])
                     delta_game.add_event(delta_events.pop(0))
                     screen_handler.visualize_game(delta_game)
                     next_update_time = curr_time + UPDATE_TIME_DELTA
                  else:
                     time.sleep(0.01)
               screen_handler.accept_input(ai_game)

         time.sleep(0.01)
   except KeyboardInterrupt:
      logger.info("Got keyboard interupt, setting kill event")
      screen_handler.kill_event.set()
      thread.join()


if __name__ == "__main__":
   Save_Data.config("saves/demo")
   if not os.path.exists(Save_Data.root):
      shutil.copytree("saves/template", Save_Data.root)

   file = logging.FileHandler(Save_Data.get_and_make(Save_Data.logs_dirpath, "debug.log", is_file=True))
   file.setLevel(logging.DEBUG)
   file.setFormatter(LOG_FORMAT)
   logger.addHandler(file)

   game_path = Save_Data.get_and_make("game.json", is_file=True)
   if os.path.exists(game_path):
      with open(game_path) as f:
         game = Game.from_json(json.load(f))
   else:
      game = Game()
      starting_events = [
         (lambda: E.create_location(game, loc_id="iosla_town_square", name="Iosla", desc="A charming seaside town centered around an ancient gnarled oak tree with massive spreading branches in the town square.")),
         (lambda: E.move_player_to(game, loc_id="iosla_town_square")),
         (lambda: E.player_request_action(game, "What kind of buildings surround me?")),
         (lambda: E.narrate(game, "You look around and see many small houses, with a tavern a little ways down the road.")),
      ]
      for call in starting_events:
         ok, msg = call()
         if not ok:
            raise RuntimeError(f"Error pre-populating game: {msg}")

   with Peek_Terminal_Input():
      game_loop(game.reset_event_count(), LOGS_DIR, game_path)

   logger.info("Game exited cleanly")
