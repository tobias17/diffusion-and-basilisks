from main import Game, get_prompt_from_game_state, make_completion, Template, Function_Map, Function, State
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
            template["OUTPUT"] = "".join(f">>> {l}\n" for l in processed_lines) + f"ERROR: {err}"
            prompt = template.render()
            break
      else:
         if event_count > 0:
            decision_log.append({"desc":"Finished Processing with an Event Created"})
            return True, decision_log
         decision_log.append({"desc":"Processed All Lines but Got 0 Events"})
         template = Template(prompt + need_more_function_calls)
         template["AI_RESPONSE"] = resp
         template["SYSTEM_RESPONSE"] = "ERROR: Make sure to call atleast 1 function before ending the call block"
         prompt = template.render()

# def populate_full_api(prompt:str, current_state:State) -> str:
#    return prompt.replace("^^API^^", Function_Map.render(current_state, lambda f: f.render_short()))

# def populate_single_api(prompt:str, current_state:State, function_name:str, comments:List[str]) -> str:
#    prompt = prompt.replace("^^API^^", Function_Map.render(current_state, lambda f: f.render_long(), function_name))
#    prompt += "\n# ".join(comments) + f"\n{function_name}("
#    return prompt

from enum import Enum, auto
class Micro_State(Enum):
   CREATE_SCRATCHPAD = auto()
   CHOOSE_FUNCTION = auto()
   FILL_FUNCTION = auto()
   UPDATE_SCRATCHPAD = auto()

from prompts import define_api, ask_for_scratchpad, end_scratchpad, ask_for_function_call, end_function_calling, update_scratchpad

class Prompt_Evolver:
   micro_state: Micro_State
   scratchpad: str
   selected_function: Function
   full_function_call: str

   def __init__(self, current_state:State):
      self.micro_state = Micro_State.CREATE_SCRATCHPAD
      self.state_functions = Function_Map.get(current_state)
   
   def get_extension(self) -> str:
      if self.micro_state == Micro_State.FILL_FUNCTION:
         api_def = "".join(f.render_long() for f in self.state_functions)
      else:
         api_def = self.selected_function.render_short()
      ext = define_api.replace("%%API%%", api_def) + "\n" + ask_for_scratchpad

      if self.micro_state == Micro_State.CREATE_SCRATCHPAD:
         return ext

      ext += "\n" + self.scratchpad + end_scratchpad + "\n" + ask_for_function_call
      if self.micro_state == Micro_State.CHOOSE_FUNCTION:
         return ext
      
      if self.micro_state == Micro_State.FILL_FUNCTION:
         return "\n" + self.selected_function.name + "("
      
      if self.micro_state == Micro_State.UPDATE_SCRATCHPAD:
         return "\n" + self.full_function_call + end_function_calling + "\n" + update_scratchpad
      


def inject():
   with open("inputs/events_1.json", "r") as f:
      data = json.load(f)
   game = Game.from_json(data)

   FOLDER_DIR = datetime.datetime.now().strftime("logs/%m-%d-%Y_%H-%M-%S")
   if not os.path.exists(FOLDER_DIR):
      os.makedirs(FOLDER_DIR)
   
   prompt, from_player, current_state = get_prompt_from_game_state(game)
   assert not from_player

   if False:
      prompt = populate_full_api(prompt, current_state)
   else:
      prompt = populate_single_api(prompt, current_state, "speak_npc_to_player", ["Tell the player hello back"])
   print(prompt)

   # all_logs = []
   # for _ in range(5):
   #    done, decision_log = update_from_prompt(prompt, game)
   #    all_logs.append(decision_log)
   # with open(f"{FOLDER_DIR}/decision_logs.json", "w") as f:
   #    json.dump(all_logs, f, indent="\t")

if __name__ == "__main__":
   inject()
