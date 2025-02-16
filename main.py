from common import logger, LOG_FORMAT, Event
from prompts import SYSTEM_MESSAGE
from functions import Function_Map, parse_function, match_function
import events as E
from game import Game
from screen_handler import Screen_Handler, Peek_Terminal_Input

from typing import Callable, Optional, List, Dict
import logging, os, datetime, json, requests, time # type: ignore
from threading import Thread

def process_game_state(game:Game, output_from_messages:Callable[[List[Dict[str,str]]],Optional[str]], decision_log:List[Dict], max_attempts:int=8) -> Optional[Game]:
   curr_attempts = 0

   messages = [
      {"role":"system", "content":SYSTEM_MESSAGE.replace("%%API_DEFINITION%%", Function_Map.api_definition())}
   ]
   lines: List[str] = []
   for event in game.events:
      if isinstance(event, E.Player_Input_Event):
         if len(lines) > 0:
            messages.append({"role":"assistant", "content":"\n".join(lines)})
            lines = []
         messages.append({"role":"user", "content":event.text})
      else:
         line = event.system()
         if line: lines.append(line)
   if len(lines) > 0:
      messages.append({"role":"assistant", "content":"\n".join(lines)})

   while True:
      decision_log.append({"event":"Computed API Messages", "messages":messages})
      output = output_from_messages(messages)
      assert output is not None, f"Ran out of outputs before completing processing"

      lines = output.split("\n")
      lines = [l.strip() for l in lines if l]

      if len(lines) == 0:
         decision_log.append({"event":"ERROR: Got back 0 lines from the model", "output":output.split("\n")})
      else:
         delta_game = game.copy()
         for line in lines:
            call_data, msg = parse_function(line)
            if call_data is None:
               logger.error(msg)
               decision_log.append({"event":"ERROR: Ran into issue parsing function", "output":output.split("\n"), "line":line, "message":msg})
               break
            func_call, msg = match_function(call_data.name, call_data.args, call_data.kwargs, Function_Map.funcs)
            if func_call is None:
               logger.error(msg)
               decision_log.append({"event":"ERROR: Ran into issue matching function", "output":output.split("\n"), "line":line, "message":msg})
               break
            ok, msg = func_call(delta_game)
            if not ok:
               logger.error(msg)
               decision_log.append({"event":"ERROR: Got Back Not-OK Calling Function", "output":output.split("\n"), "line":line, "message":msg})
               break
         else:
            decision_log.append({"event":"Fully processed output and advanced game state", "output":output.split("\n")})
            return delta_game

      curr_attempts += 1
      if curr_attempts >= max_attempts:
         return None


json_log = None
def make_completion(messages:List[Dict[str,str]]) -> Optional[str]:
   global client, json_log

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


def old_game_loop(game:Game, log_dirpath:str):
   decision_log = []
   while True:
      last_event = game.events[-1]

      if isinstance(last_event, E.Player_Input_Event):
         # AI's turn to produce next block
         decision_log.append({"event":f"Performing Game Loop Tick", "message":"Requesting LLM completion"})
         new_game = process_game_state(game, make_completion, decision_log)
         if new_game is not None:
            game = new_game
            new_events: List[Event] = []
            for event in game.events[::-1]:
               if isinstance(event, E.Player_Input_Event):
                  break
               new_events.insert(0, event)
            for event in new_events:
               msg = event.system()
               if msg:
                  print(msg)
         else:
            raise RuntimeError("Could not resolve from LLM")

      else:
         # User's turn to produce next block
         decision_log.append({"event":f"Performing Game Loop Tick", "message":"Requesting user input"})
         text = ""
         while not text:
            text = input("Response? ").strip()
         if text == "q":
            return
         decision_log.append({"event":"Got player input", "text":text})
         game.add_event(E.Player_Input_Event(text))

      with open(f"{log_dirpath}/decision_log.json", "w") as f: json.dump(decision_log,   f, indent="\t")
      with open(f"{log_dirpath}/game.json",         "w") as f: json.dump(game.to_json(), f, indent="\t")


def game_loop(game:Game, log_dirpath:str):
   # Create a screen handler object and start it up
   screen_handler = Screen_Handler(game)
   thread = Thread(target=screen_handler.run)
   thread.start()

   # Main game loop
   try:
      while not screen_handler.kill_event.is_set():
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

   game = Game()
   starting_events = [
      (lambda: E.create_location(game, loc_id="iosla_town_square", name="Iosla", desc="A charming seaside town centered around an ancient gnarled oak tree with massive spreading branches in the town square.")),
      (lambda: E.move_to(game, loc_id="iosla_town_square")),
      (lambda: E.player_input(game, "What kind of buildings surround me?")),
      (lambda: E.narrate(game, "You look around and see many small houses, with a tavern a little ways down the road.")),
   ]
   for call in starting_events:
      ok, msg = call()
      if not ok:
         raise RuntimeError(f"Error pre-populating game: {msg}")

   with Peek_Terminal_Input():
      game_loop(game, FOLDER_DIR)

   logger.info("Game exited cleanly")
