from main import Game, get_prompt_from_game_state, Function_Map, Function, State
import json, datetime, os, sys
from typing import List, Tuple, Callable, Dict

from enum import Enum
class Micro_State(Enum):
   CREATE_SCRATCHPAD = "CREATE_SCRATCHPAD"
   CHOOSE_FUNCTION   = "CHOOSE_FUNCTION"
   FILL_FUNCTION     = "FILL_FUNCTION"
   UPDATE_SCRATCHPAD = "UPDATE_SCRATCHPAD"
   DONE              = "DONE"

   def __repr__(self) -> str: return self.value
   __str__ = __repr__

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
   
   def should_call(self) -> bool:
      return self.micro_state == Micro_State.UPDATE_SCRATCHPAD
   
   def loop(self) -> None:
      assert self.micro_state == Micro_State.DONE, f"Tried looping evolver in {self.micro_state} state, expected {Micro_State.DONE} state"
      assert len(self.scratchpad) > 0, "Tried looping evolver with an empty scratchpad"
      self.micro_state = Micro_State.CHOOSE_FUNCTION

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
         output = f"{self.selected_function.name}({output}"
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
         self.full_function_call = lines[0]
         self.micro_state = Micro_State.UPDATE_SCRATCHPAD
         return True, ""
      
      elif self.micro_state == Micro_State.UPDATE_SCRATCHPAD:
         self.scratchpad = output
         self.micro_state = Micro_State.DONE
         return True, ""
      
      assert self.micro_state != Micro_State.DONE, "Prompt_Evolver in done state, cannot process_output"
      
      raise RuntimeError(f"[INVALID_STATE] Reached the end of process_output, should have gotten a handled return by now")


def inject():
   names_to_test = ["town_talk"]

   for test_name in names_to_test:
      with open(f"inputs/{test_name}_events.json", "r") as f:
         data = json.load(f)
      with open(f"inputs/{test_name}_injects.json", "r") as f:
         injects: Dict[str,List[str]] = json.load(f)
      game = Game.from_json(data)

      # FOLDER_DIR = datetime.datetime.now().strftime("logs/%m-%d-%Y_%H-%M-%S")
      FOLDER_DIR = "logs/inject"
      if not os.path.exists(FOLDER_DIR):
         os.makedirs(FOLDER_DIR)
      
      event_log = []
      for key, outputs in injects.items():
         try:
            event_log.append({"break":"="*120, "event":"Starting New Session", "name":key})
            delta_game = game.copy()
            prompt, current_state = get_prompt_from_game_state(delta_game)
            event_log.append({"event":"Got Initial Prompt", "prompt":prompt.split("\n")})
            evolver = Prompt_Evolver(current_state)

            for output in outputs:
               if evolver.micro_state == Micro_State.DONE:
                  evolver.loop()
                  prompt, current_state = get_prompt_from_game_state(delta_game)
                  event_log.append({"event":"Looping Evolver", "prompt":prompt.split("\n")})

               ext = evolver.get_extension()
               event_log.append({"event":"Got Extension", "extension":ext.split("\n"), "micro_state":evolver.micro_state.value})
               ok, msg = evolver.process_output(output)
               if not ok:
                  event_log.append({"event":"Got Back Not-OK Processing Output", "output":output.split("\n"), "message":msg})
               else:
                  event_log.append({"event":"Processed Output OK", "output":output.split("\n"), "micro_state":evolver.micro_state.value})
               if evolver.should_call():
                  ok, msg = evolver.call(delta_game)
                  if not ok:
                     event_log.append({"event":"Got Back Not-OK Calling Function", "message":msg})
                  else:
                     event_log.append({"event":"Called Function OK"})
            if evolver.micro_state == Micro_State.DONE:
               event_log.append({"event":"Ended on DONE State", "scratchpad":evolver.scratchpad.split("\n")})
         except Exception as ex:
            _, _, exc_tb = sys.exc_info()
            event_log.append({"event":"ERROR: Unhandled Exception", "error":f"{ex} ({os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno})"})

      with open(os.path.join(FOLDER_DIR, f"{test_name}_log.json"), "w") as f:
         json.dump(event_log, f, indent="\t")

if __name__ == "__main__":
   inject()
