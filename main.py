from common import State, Event
from events import StateTransitionEvent
from prompts import Template, intro, state_map
from functions import Function_Map, Function, Parameter

from typing import List, Dict, Tuple, Optional, Callable, Type, Any
from openai import OpenAI
import re

class Game:
   events: List[Event]
   def __init__(self):
      self.events = []

   def get_current_state(self) -> State:
      for event in reversed(self.events):
         if isinstance(event, StateTransitionEvent):
            return event.to_state
      return State.INITIALIZING

   def add_events(self, *events:Event) -> None:
      for event in events:
         self.events.append(event)

func_pattern = re.compile(r'^([a-zA-Z0-9_]+)\((.+)\)$')
def parse_function(line:str) -> Tuple[Optional[Tuple[str,List,Dict]],str]:
   if "\t" in line: return None, "Function calling blocks cannont contain the \\t character"
   if "\r" in line: return None, "Function calling blocks cannont contain the \\r character"
   special_map = {
      ",": "\t",
      "=": "\r",
   }
   
   match = func_pattern.match(line)
   if not match:
      return None, "Go bad input, could not parse a function from this"
   func_name   = match.group(1)
   orig_params = match.group(2)

   cleaned_params = ""
   quote_char = None
   for char in orig_params:
      if quote_char:
         if char in ("'", '"'):
            quote_char = None
      else:
         if char in ("'", '"'):
            quote_char = char
         elif char in special_map:
            cleaned_params += special_map[char]
            continue
      cleaned_params += char
   if quote_char:
      return None, "Got uneven number of quote characters"

   args:   List = []
   kwargs: Dict = {}
   chunks = cleaned_params.split(special_map[","])
   for chunk in chunks:
      pieces = chunk.split(special_map["="])
      if len(pieces) == 1:
         if len(kwargs) > 0:
            return None, "Found position argument after keyword argument"
         args.append(pieces[0].strip())
      elif len(pieces) == 2:
         kwargs[pieces[0].strip()] = pieces[1].strip()
      else:
         return None, "Found too many '=' characters in a single parameter"
   
   return (func_name, args, kwargs), ""


def cast_value(value:str, param:Parameter) -> Tuple[Any,str]:
   if param.dtype is str:
      for quote in ('"', "'"):
         if value.startswith(quote) and value.endswith(quote) and len(value) >= 2:
            return value[1:-1], ""
      return None, f"Paramater '{param.name}' expected string value but failed to find quote characters"
   elif param.dtype is int:
      try:
         return int(value), ""
      except Exception:
         return None, f"Error converting parameter '{param.name}' to an integer"
   else:
      raise RuntimeError(f"Got Parameter.dtype of '{param.dtype.__name__}' which is not get supported by cast_value()")

def match_function(func_name:str, args:List, kwargs:Dict, functions:List[Function]) -> Tuple[Optional[Callable],str]:
   cleaned_args:   List = []
   cleaned_kwargs: Dict = {}
   for function in functions:
      if func_name == function.name:
         arg_idx = 0
         for param in function.params:
            if arg_idx < len(args):
               value, err = cast_value(args[arg_idx], param)
               if value is None:
                  return None, err
               cleaned_args.append(value)
               arg_idx += 1
            else:
               if param.name in kwargs:
                  value, err = cast_value(kwargs[param.name], param)
                  if value is None:
                     return None, err
                  cleaned_kwargs[param.name] = value
               else:
                  return None, f"Unknown keyword argument '{param.name}' to function '{func_name}'"
         
         if arg_idx < len(args):
            return None, f"Found {len(args)} positional arguments but function '{func_name}' expected only {len(function.params)}"
         for name in kwargs.keys():
            if name not in cleaned_kwargs:
               return None, f"Unexpected keyword argument '{name}' for function '{func_name}'"
         
         return (lambda: function.call(*cleaned_args, **cleaned_kwargs)), ""
   
   return None, f"Could not find function named '{func_name}'"


client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
def make_completion(prompt:str):
   global client

   completion = client.chat.completions.create(
      model="lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF",
      messages=[
         { "role":"system", "content":prompt },
      ],
      temperature=0.7,
      max_tokens=128,
      stop=["$$end_"],
   )

   resp = completion.choices[0].message.content
   assert resp is not None
   return resp


def game_loop(game:Game):
   while True:
      current_state = game.get_current_state()

      if current_state == State.INITIALIZING:
         template = Template(intro, Function_Map.render(current_state), state_map[current_state])
         prompt = template.render()
         print(prompt)
         resp = make_completion(prompt)
         events = process_functions(resp, Function_Map.get(current_state))
         assert len(events) == 1, f"len(events)={len(events)}"
         print(events[0].render())
         game.add_events(*events, StateTransitionEvent(from_state=current_state, to_state=State.HUB_IDLE))
      elif current_state == State.HUB_IDLE:
         template = Template(intro, Function_Map.render(current_state), state_map[current_state])
         template["PLAYER_INPUT"] = input("What would you like to do?\n").strip()
         prompt = template.render()
         print(prompt)
         resp = make_completion(prompt)
         events = process_functions(resp, Function_Map.get(current_state))
         print(events)
      else:
         raise ValueError(f"game_loop() does not support {current_state} state yet")



def main():
   game = Game()
   game_loop(game)

if __name__ == "__main__":
   main()
