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
