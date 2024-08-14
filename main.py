from common import State, Event, StateTransitionEvent
from prompts import Template, intro, state_map
from functions import Functions

from typing import List
from openai import OpenAI

class Game:
   events: List[Event]
   def __init__(self):
      self.events = []

   def get_current_state(self) -> State:
      for event in reversed(self.events):
         if isinstance(event, StateTransitionEvent):
            return event.to_state
      return State.INITIALIZING

   def add_event(self, event:Event) -> None:
      self.events.append(event)

def game_loop(game:Game):
   current_state = game.get_current_state()
   
   if current_state == State.INITIALIZING:
      template = Template(intro, Functions.from_state(current_state), state_map[current_state])
      prompt = template.render()
      print(prompt)
      client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
      completion = client.chat.completions.create(
         model="lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF",
         messages=[
            { "role":"system", "content":prompt },
         ],
         temperature=0.7,
         max_tokens=128,
         # stop=["```", "$$end_"],
      )
      print(completion.choices[0].message.content)
      # game.add_event(StateTransitionEvent(from_state=current_state, to_state=State.HUB_IDLE))
   else:
      raise ValueError(f"game_loop() does not support {current_state} state yet")


def main():
   game = Game()
   game_loop(game)

if __name__ == "__main__":
   main()
