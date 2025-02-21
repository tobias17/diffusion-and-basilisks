from common import logger, LOG_FORMAT, Event
from prompts import SYSTEM_MESSAGE
from functions import Function_Map, parse_function, match_function
import events as E
from game import Game
from screen_handler import Screen_Handler, Peek_Terminal_Input

from typing import Callable, Optional, List, Dict
import logging, os, datetime, json, requests, time, threading # type: ignore
from queue import Queue

def process_game_state(game:Game, output_from_messages:Callable[[List[Dict[str,str]]],Optional[str]], kill_event:threading.Event, decision_log:List[Dict], max_attempts:int=8) -> Optional[Game]:

   # Create the message JSON object to perform request with
   messages = [
      {"role":"system", "content":SYSTEM_MESSAGE.replace("%%API_DEFINITION%%", Function_Map.api_definition())}
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

      lines = output.split("\n")
      lines = [l.strip() for l in lines if l]

      if len(lines) == 0:
         decision_log.append({"output":output.split("\n"), "event":"ERROR: Got back 0 lines from the model"})
      else:
         delta_game = game.copy()
         for line in lines:
            call_data, msg = parse_function(line)
            if call_data is None:
               logger.error(msg)
               decision_log.append({"output":output.split("\n"), "event":"ERROR: Ran into issue parsing function", "message":msg, "on_line":line})
               continue
            func_call, msg = match_function(call_data.name, call_data.args, call_data.kwargs, Function_Map.funcs)
            if func_call is None:
               logger.error(msg)
               decision_log.append({"output":output.split("\n"), "event":"ERROR: Ran into issue matching function", "message":msg, "on_line":line})
               continue
            ok, msg = func_call(delta_game)
            if not ok:
               logger.error(msg)
               decision_log.append({"output":output.split("\n"), "event":"ERROR: Got Back Not-OK Calling Function", "message":msg, "on_line":line})
               continue
         else:
            decision_log.append({"output":output.split("\n"), "event":"Fully processed output and advanced game state"})
            return delta_game

   return None


def make_completion(messages:List[Dict[str,str]]) -> Optional[str]:
   endpoint = "http://192.168.1.200:7776/v1"
   headers = { "Content-Type": "application/json" }
   data = { "messages": messages }

   resp = requests.post(
      f"{endpoint}/chat/completions",
      headers=headers,
      json=data
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

   def __init__(self, kill_event:threading.Event, log_dirpath:str):
      self.kill_event = kill_event
      self.log_dirpath = log_dirpath
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
      with open(f"{self.log_dirpath}/decision_log.json", "w") as f: json.dump(self.decision_logs,  f, indent="\t")
      with open(f"{self.log_dirpath}/game.json",         "w") as f: json.dump(save_game.to_json(), f, indent="\t")

      return final_game


def game_loop(game:Game, log_dirpath:str):
   kill_event = threading.Event()
   ai_manager = AI_Manager(kill_event, log_dirpath)
   user_input_queue: Queue[Event] = Queue(maxsize=1)

   # Create a screen handler object and start it up
   screen_handler = Screen_Handler(kill_event, game, user_input_queue)
   thread = threading.Thread(target=screen_handler.run)
   thread.start()

   UPDATE_TIME_DELTA = 1.0
   next_update_time  = 0.0

   # Main game loop
   try:
      while not kill_event.is_set():
         if user_input_queue.full():
            event = user_input_queue.get()
            new_game1 = game.copy()
            new_game1.add_event(event)
            new_game1.new_events = 1
            screen_handler.update_game(new_game1)
            next_update_time = time.time() + UPDATE_TIME_DELTA

            logger.info("New event detected, processing AI response")
            new_game2 = ai_manager.process(new_game1)
            if new_game2 is None:
               logger.error("Could not progress game state with AI, reverting user input")
               screen_handler.update_game(game)
            else:
               logger.info("Got back AI response, processing new events")
               new_game2.new_events = len(new_game2.events) - len(new_game1.events)
               new_event_count = new_game2.new_events - 1
               while True:
                  if kill_event.is_set():
                     return
                  curr_time = time.time()
                  if curr_time >= next_update_time:
                     if new_event_count <= 0:
                        screen_handler.update_game(new_game2, True)
                        game = new_game2
                        break
                     delta_game = new_game2.copy()
                     delta_game.events = delta_game.events[:-new_event_count]
                     delta_game.new_events = new_game2.new_events - new_event_count
                     screen_handler.update_game(delta_game)
                     next_update_time = curr_time + UPDATE_TIME_DELTA
                     new_event_count -= 1
                  else:
                     time.sleep(0.01)
            screen_handler.accept_input()

         time.sleep(0.01)
   except KeyboardInterrupt:
      logger.info("Got keyboard interupt, setting kill event")
      screen_handler.kill_event.set()
      thread.join()


if __name__ == "__main__":
   FOLDER_DIR = datetime.datetime.now().strftime("logs/game/%m-%d-%Y_%H-%M-%S")
   if not os.path.exists(FOLDER_DIR):
      os.makedirs(FOLDER_DIR)
   json_log = f"{FOLDER_DIR}/prompts.json"

   file = logging.FileHandler(f"{FOLDER_DIR}/debug.log")
   file.setLevel(logging.DEBUG)
   file.setFormatter(LOG_FORMAT)
   logger.addHandler(file)

   input_game_path = "game.json"
   if os.path.exists(input_game_path):
      with open(input_game_path) as f:
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
      game_loop(game, FOLDER_DIR)

   logger.info("Game exited cleanly")
