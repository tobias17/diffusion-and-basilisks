from main import Game, get_prompt_from_game_state, make_completion, Template, Function_Map, Function, State
import json, datetime, os, sys
from typing import List, Tuple, Callable, Optional, Dict

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

from enum import Enum
class Micro_State(Enum):
   CREATE_SCRATCHPAD = "CREATE_SCRATCHPAD"
   CHOOSE_FUNCTION   = "CHOOSE_FUNCTION"
   FILL_FUNCTION     = "FILL_FUNCTION"
   UPDATE_SCRATCHPAD = "UPDATE_SCRATCHPAD"
   DONE              = "DONE"

from prompts import define_api, ask_for_scratchpad, end_scratchpad, ask_for_function_call, end_function_calling, update_scratchpad
from functions import parse_function, match_function

class Prompt_Evolver:
   micro_state: Micro_State
   scratchpad: str
   selected_function: Function
   full_function_call: str
   call: Callable

   def __init__(self, current_state:State):
      self.micro_state = Micro_State.CREATE_SCRATCHPAD
      self.state_functions = Function_Map.get(current_state)
   
   def get_extension(self) -> str:
      if self.micro_state != Micro_State.FILL_FUNCTION:
         api_def = "".join(f.render_short() for f in self.state_functions)
      else:
         api_def = self.selected_function.render_long()
      ext = define_api.replace("%%API%%", api_def) + "\n" + ask_for_scratchpad

      if self.micro_state == Micro_State.CREATE_SCRATCHPAD:
         return ext

      ext += "\n" + self.scratchpad + "\n" + end_scratchpad + "\n" + ask_for_function_call
      if self.micro_state == Micro_State.CHOOSE_FUNCTION:
         return ext
      
      if self.micro_state == Micro_State.FILL_FUNCTION:
         return ext + "\n" + self.selected_function.name + "("
      
      if self.micro_state == Micro_State.UPDATE_SCRATCHPAD:
         return ext + "\n" + self.full_function_call + end_function_calling + "\n" + update_scratchpad
      
      assert self.micro_state != Micro_State.DONE, "Prompt_Evolver in done state, cannot get_extension"

      raise RuntimeError(f"[INVALID_STATE] Reached the end of get_extension, should have gotten a handled return by now")
   
   def process_output(self, output:str) -> Tuple[bool,str]:
      if self.micro_state == Micro_State.CREATE_SCRATCHPAD:
         self.scratchpad = output.strip()
         self.micro_state = Micro_State.CHOOSE_FUNCTION
         return True, ""
   
      elif self.micro_state == Micro_State.CHOOSE_FUNCTION:
         lines = output.strip().split("\n")
         if len(lines) != 1:
            return False, f"Got {len(lines)} lines when choosing a function, expected exactly 1"
         ret, msg = parse_function(lines[0])
         if ret is None:
            return False, msg
         func_name, args, kwargs = ret
         if (param_count := (len(args) + len(kwargs))) > 0:
            return False, f"Got {param_count} parameters to function call, expected exactly 0"
         for func in self.state_functions:
            if func.name == func_name:
               self.selected_function = func
               self.micro_state = Micro_State.FILL_FUNCTION
               return True, ""
         else:
            return False, f"Could not find function named '{func_name}', options are {[f.name for f in self.state_functions]}"
      
      elif self.micro_state == Micro_State.FILL_FUNCTION:
         lines = output.strip().split("\n")
         if len(lines) != 1:
            return False, f"Got {len(lines)} lines when choosing a function, expected exactly 1"
         ret, msg = parse_function(lines[0])
         if ret is None:
            return False, msg
         func_name, args, kwargs = ret
         call, msg = match_function(func_name, args, kwargs, [self.selected_function])
         if call is None:
            return False, msg
         self.call = call
         self.micro_state = Micro_State.UPDATE_SCRATCHPAD
         return True, ""
      
      elif self.micro_state == Micro_State.UPDATE_SCRATCHPAD:
         self.scratchpad = output
         self.micro_state = Micro_State.DONE
         return True, ""
      
      assert self.micro_state != Micro_State.DONE, "Prompt_Evolver in done state, cannot process_output"
      
      raise RuntimeError(f"[INVALID_STATE] Reached the end of process_output, should have gotten a handled return by now")


def inject():
   with open("inputs/events_1.json", "r") as f:
      data = json.load(f)
   with open("inputs/injects_1.json", "r") as f:
      injects: Dict[str,List[str]] = json.load(f)
   game = Game.from_json(data)

   # FOLDER_DIR = datetime.datetime.now().strftime("logs/%m-%d-%Y_%H-%M-%S")
   FOLDER_DIR = "logs/inject"
   if not os.path.exists(FOLDER_DIR):
      os.makedirs(FOLDER_DIR)
   
   event_log = []

   prompt, from_player, current_state = get_prompt_from_game_state(game)
   assert not from_player
   event_log.append({"event":"Got Initial Prompt", "prompt":prompt.split("\n")})

   for key, outputs in injects.items():
      event_log.append({"break":"="*120, "event":"Starting New Session", "name":key})
      evolver = Prompt_Evolver(current_state)
      try:
         for output in outputs:
            ext = evolver.get_extension()
            event_log.append({"event":"Got Extension", "extension":ext.split("\n"), "micro_state":evolver.micro_state.value})
            ok, msg = evolver.process_output(output)
            if not ok:
               event_log.append({"event":"Got Back Not-OK Processing Output", "output":output.split("\n"), "message":msg})
            else:
               event_log.append({"event":"Processed Output OK", "output":output.split("\n"), "micro_state":evolver.micro_state.value})
      except Exception as ex:
         _, _, exc_tb = sys.exc_info()
         event_log.append({"event":"ERROR: Unhandled Exception", "error":f"{ex} ({os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno})"})

   with open(os.path.join(FOLDER_DIR, "event_log.json"), "w") as f:
      json.dump(event_log, f, indent="\t")

if __name__ == "__main__":
   inject()
