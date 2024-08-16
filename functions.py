from common import State, Event
from events import CreateHubEvent, CreateCharacterEvent

from typing import List, Dict, Optional, Type, Callable
from dataclasses import dataclass

@dataclass
class Parameter:
   name: str
   type: Type
   default: Optional[str] = None
   def render(self) -> str:
      return f"{self.name}:{self.type.__name__}" + (f"={self.default}" if self.default is not None else "")

class Function:
   call: Callable
   name: str
   comment: str
   params: List[Parameter]
   def __init__(self, call:Callable, name:str, comment:str, *params:Parameter):
      self.call = call
      self.name = name
      self.comment = comment
      self.params = list(params)
   def render(self) -> str:
      return f"def {self.name}({', '.join(p.render() for p in self.params)}): # {self.comment}"

class Function_Map:
   mapping: Dict[State,List[Function]] = {}

   @staticmethod
   def register(fxn:Function, *states:State) -> None:
      for state in states:
         if state not in Function_Map.mapping:
            Function_Map.mapping[state] = []
         Function_Map.mapping[state].append(fxn)

   @staticmethod
   def get(key:State) -> List[Function]:
      return Function_Map.mapping.get(key, [])

   @staticmethod
   def render(key:State) -> str:
      return "$$begin_api$$\n" + "\n".join(f.render() for f in Function_Map.get(key)) + "\n$$end_api$$" # type: ignore

def create_hub(hub_name:str, hub_description:str) -> List[Event]:
   return [CreateHubEvent(hub_name, hub_description)]
Function_Map.register(
   Function(create_hub, "create_hub", "Creates a new hub with the given name and description", Parameter("hub_name",str), Parameter("hub_description",str)),
   State.INITIALIZING
)

def create_npc(name:str, character_background:str, physical_description:str) -> List[Event]:
   return [CreateCharacterEvent(name, character_background, physical_description)]
Function_Map.register(
   Function(create_npc, "create_npc", "Creates a new NPC that the player could interact with", Parameter("name",str), Parameter("character_background",str), Parameter("physical_description",str)),
   State.HUB_IDLE, State.HUB_TALKING
)

def list_npc() -> List[Event]:
   return []
