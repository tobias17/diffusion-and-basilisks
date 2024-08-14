from common import State

from typing import List, Dict

class Functions:
   state_to_methods_map: Dict[State,List[str]] = {}

   @staticmethod
   def register(fxn, *states:State):
      for state in states:
         if state not in Functions.state_to_methods_map:
            Functions.state_to_methods_map[state] = []
         Functions.state_to_methods_map[state].append(fxn)
   
   @staticmethod
   def from_state(state:State) -> str:
      return "$$begin_python_api$$\n" + "\n\n".join(Functions.state_to_methods_map.get(state, [])) + "\n$$end_python_api$$"

class HubDescription: pass
def list_hubs() -> List[HubDescription]:
   return []
# Functions.register(list_hubs, State.HUB_IDLE, State.HUB_TALKING, State.TRAVEL_IDLE, State.TRAVEL_TALK)

Functions.register('''
def create_hub(hub_name:str, hub_description:str) -> None:
   """Creates a new hub with the given name and description"""
'''.strip(), State.INITIALIZING)

Functions.register('''
def travel_to_hub(hub_name:str, hub_description:str) -> None:
   """Moves the player into the specified hub, allowing them to act in this hub"""
'''.strip(), State.TRAVEL_IDLE)


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