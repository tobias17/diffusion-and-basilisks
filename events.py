from common import State, Event

from dataclasses import dataclass
from typing import Optional

# @dataclass
# class State_Transition_Event(Event):
#    to_state: State
#    def implication(self) -> Optional[State]:
#       return self.to_state
#    def render(self) -> str:
#       return f"Transition to {self.to_state} state"

@dataclass
class Create_Location_Event(Event):
   name: str
   description: str
   def __init__(self, location_name:str, location_description:str):
      self.name = location_name
      description = location_description.strip().strip(".,")
      self.description = description[0].lower() + description[1:]
   def render(self) -> str:
      return f"You discover {self.name}: {self.description}"

@dataclass
class Move_To_Location_Event(Event):
   location_name: str
   def implication(self) -> Optional[State]:
      return State.LOCATION_IDLE

@dataclass
class Create_Character_Event(Event):
   character_name: str
   location_name: str
   background: str
   description: str
   def render(self) -> str:
      return ""

@dataclass
class Start_Conversation_Event(Event):
   character_name: str
   def implication(self) -> Optional[State]:
      return State.LOCATION_TALK

@dataclass
class Speak_Event(Event):
   with_character: str
   is_player_speaking: bool
   text: str
   def render(self) -> str:
      return (f"Player to {self.with_character}" if self.is_player_speaking else f"{self.with_character} to Player") + f": {self.text}"

@dataclass
class Begin_Traveling_Event(Event):
   description: str
   def implication(self) -> Optional[State]:
      return State.TRAVELING
