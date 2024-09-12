from common import State
from functions import Function, Function_Map, parse_function, match_function
from prompts import define_api, ask_for_scratchpad, end_scratchpad, ask_for_function_call, end_function_calling, update_scratchpad

from typing import Callable, Tuple
from enum import Enum

class Micro_State(Enum):
   CREATE_SCRATCHPAD = "CREATE_SCRATCHPAD"
   CHOOSE_FUNCTION   = "CHOOSE_FUNCTION"
   FILL_FUNCTION     = "FILL_FUNCTION"
   UPDATE_SCRATCHPAD = "UPDATE_SCRATCHPAD"
   DONE              = "DONE"

   def __repr__(self) -> str: return self.value
   __str__ = __repr__

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
