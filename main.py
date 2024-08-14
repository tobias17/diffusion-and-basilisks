from common import State, Event, StateTransitionEvent
from prompts import Template, intro, state_map
from functions import Functions

from typing import List

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
      # game.add_event(StateTransitionEvent(from_state=current_state, to_state=State.HUB_IDLE))
   else:
      raise ValueError(f"game_loop() does not support {current_state} state yet")


def main():
   game = Game()
   game_loop(game)

if __name__ == "__main__":
   main()
