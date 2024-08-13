from common import State, Event, StateTransitionEvent
from prompts import Template
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
      game.add_event(StateTransitionEvent(from_state=current_state, to_state=State.HUB_IDLE))
   else:
      raise ValueError(f"game_loop() does not support {current_state} state yet")


def main():
   t = Template("%%SOME_TEXT%% in a %%OTHER_ENTRY%% here !")
   t["SOME_TEXT"] = "apple"
   t["OTHER_ENTRY"] = "bananas"
   print(t.render())

if __name__ == "__main__":
   main()
