from common import State, Event
from events import StateTransitionEvent
from prompts import Template, intro, state_map
from functions import Function_Map, Function

from typing import List, Dict, Tuple, Optional
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

func_pattern = re.compile(r'^([a-zA-Z0-9_]+)\((.+\))$')
def process_functions(text:str, funcs:List[Function]) -> List[Event]:
   text  = text.split("$$end_")[0]
   lines = [l.strip() for l in text.split("\n") if l]

   events = []
   for line in lines:
      if line.startswith("#"):
         continue
      match = func_pattern.match(line)
      if not match:
         print(f"WARNING: Failed to match function pattern to line:\n<|{line}|>")
      else:
         func_name = match.group(1)
         for func in funcs:
            if func.name == func_name:
               scope_key = None
               ended = False
               args, kwargs = [], {} # type: ignore
               name, block = None, ""
               params = match.group(2)
               for c in params:
                  if scope_key is not None:
                     if c == scope_key:
                        if name is None:
                           assert len(kwargs) == 0
                           args.append(block)
                           # print(f"{c}: Added block as pos arg")
                        else:
                           kwargs[name.strip()] = block
                           # print(f"{c}: Added block as kwarg")
                        name, block = None, ""
                        scope_key = None
                        ended = True
                     else:
                        block += c
                        # print(f"{c}: Appended to scoped block")
                  elif c in ['"', '"']:
                     scope_key = c
                     # print(f"{c}: Entered scope")
                  elif c == "=":
                     assert name is None
                     assert block, f"name={name}, block={block}, scope_key={scope_key}"
                     name = block
                  elif c in [",", ")"]:
                     if ended:
                        # print(f"{c}: skipping")
                        pass
                     else:
                        assert block, f"name={name}, block={block}, scope_key={scope_key}"
                        if name is None:
                           assert len(kwargs) == 0
                           args.append(block)
                        else:
                           kwargs[name.strip()] = block
                           name, block = None, ""
                  elif c:
                     block += c
               
               assert scope_key is None

         events.extend(func.call(*args, **kwargs))

   return events

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
         args.append(pieces[0])
      elif len(pieces) == 2:
         kwargs[pieces[0]] = pieces[1]
      else:
         return None, "Found too many '=' characters in a single parameter"
   
   return (func_name, args, kwargs), ""


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
