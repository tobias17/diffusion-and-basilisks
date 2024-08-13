from common import State, Event, StateTransitionEvent
from prompts import Template

from typing import List, Dict


class Functions:
   state_to_methods_map: Dict[State,List] = {}
   @staticmethod
   def register(fxn, *states:State):
      for state in states:
         if state not in Functions.state_to_methods_map:
            Functions.state_to_methods_map[state] = []
         Functions.state_to_methods_map[state].append(fxn)

class HubDescription: pass
def list_hubs() -> List[HubDescription]:
   return []
Functions.register(list_hubs, State.HUB_IDLE, State.HUB_TALKING, State.TRAVEL_IDLE, State.TRAVEL_TALK)

def create_hub(hub_name:str, hub_description) -> None:
   pass
Functions.register(list_hubs, State.HUB_IDLE, State.HUB_TALKING, State.TRAVEL_IDLE, State.TRAVEL_TALK)


class NpcDescription: pass
def list_npcs() -> List[NpcDescription]:
   return []

def create_npc(character_name:str, character_description:str, physical_description:str) -> None:
   """Creates a new NPC with the given properties."""

def talk_to_npc(character_name:str) -> None:
   """Initiates a converstation between the player and the specified NPC."""


class ItemDescription: pass
def list_player_items() -> List[ItemDescription]:
   return []

def give_player_item(item_name:str, item_description:str, physical_description:str) -> None:
   pass

def player_use_item(item_name:str, action_description:str, consume_amount:int=0) -> None:
   pass



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
