from common import State, Event

from dataclasses import dataclass

@dataclass
class Create_Hub_Event(Event):
   name: str
   description: str
   def __init__(self, hub_name:str, hub_description:str):
      self.name = hub_name
      description = hub_description.strip().strip(".,")
      self.description = description[0].lower() + description[1:]
   def render(self) -> str:
      return f"You discover {self.name}: {self.description}"

@dataclass
class Create_Character_Event(Event):
   npc_name: str
   hub_name: str
   background: str
   description: str
   def render(self) -> str:
      return ""

@dataclass
class Speak_Event(Event):
   with_character: str
   is_player_speaking: bool
   text: str
   def render(self) -> str:
      return (f"Player to {self.with_character}" if self.is_player_speaking else f"{self.with_character} to Player") + f": {self.text}"

@dataclass
class State_Transition_Event(Event):
   from_state: State
   to_state: State
   def render(self) -> str:
      return f"Transition from {self.from_state} to {self.to_state}"
