from main import Game, get_prompt_from_game_state, make_completion, Template, error_in_function_calls, need_more_function_calls
import json, datetime, os
from typing import List, Tuple

MAX_LOOPS = 3
def update_from_prompt(prompt:str, game:Game, decision_log=None) -> Tuple[bool,List]:
   loops = 0
   if decision_log is None:
      decision_log = []

   while True:
      if loops >= MAX_LOOPS:
         decision_log.append({"desc":f"Reached Max Loop Count of {loops}"})
         return False, decision_log
      loops += 1

      decision_log.append({"desc":f"Requesting Completion {loops}", "prompt":prompt.split("\n")})
      resp = make_completion(prompt)
      decision_log.append({"desc":"Got Back Completion", "resp":resp.split("\n")})

      event_count = 0
      processed_lines: List[str] = []
      delta_game = game.copy()
      for line in ("# " + resp).split("\n"):
         line = line.strip()
         processed_lines.append(line)
         if line.startswith("#"):
            decision_log.append({"desc":"Skipping Comment Line", "line":line})
            continue

         ok, err = delta_game.process_line(line)

         if ok:
            decision_log.append({"desc":"Processed Line OK", "line":line})
            event_count += 1
         else:
            decision_log.append({"desc":"Error During Line Processing", "line":line, "error":err})
            template = Template(prompt + error_in_function_calls)
            template["AI_RESPONSE"] = resp
            template["OUTPUT"] = "".join(f">>> {l}\n" for l in processed_lines) + err
            prompt = template.render()
            break
      else:
         if event_count > 0:
            decision_log.append({"desc":"Finished Processing with an Event Created"})
            return True, decision_log
         decision_log.append({"desc":"Processed All Lines but Got 0 Events"})
         template = Template(prompt + need_more_function_calls)
         template["AI_RESPONSE"] = resp
         template["SYSTEM_RESPONSE"] = "Make sure to call atleast 1 function before ending the call block"
         prompt = template.render()

def inject():
   with open("inputs/events_1.json", "r") as f:
      data = json.load(f)
   game = Game.from_json(data)

   FOLDER_DIR = datetime.datetime.now().strftime("logs/%m-%d-%Y_%H-%M-%S")
   if not os.path.exists(FOLDER_DIR):
      os.makedirs(FOLDER_DIR)
   
   prompt, from_player = get_prompt_from_game_state(game)
   assert not from_player
   print(prompt)

   done, decision_log = update_from_prompt(prompt, game)
   with open(f"{FOLDER_DIR}/decision_log.json", "w") as f:
      json.dump(decision_log, f, indent="\t")

if __name__ == "__main__":
   inject()
