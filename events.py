from common import State, Event

from dataclasses import dataclass
from typing import Optional

@dataclass
class Create_Location_Event(Event):
   name: str
   description: str
   def render(self) -> str:
      return f"You discover {self.name}: {self.description}"
   def system(self, current_location_name:str) -> Optional[str]:
      return f"A new location is created, '{self.name}', {self.description}"

@dataclass
class Move_To_Location_Event(Event):
   location_name: str
   def implication(self) -> Optional[State]:
      return State.LOCATION_IDLE
   def system(self, current_location_name:str) -> Optional[str]:
      return f"You move locations to '{self.location_name}'"

@dataclass
class Describe_Environment_Event(Event):
   description: str
   location_name: str
   def system(self, current_location_name:str) -> Optional[str]:
      if self.location_name == current_location_name:
         return f"Environment Description in '{self.location_name}': {self.description}"
      return None

@dataclass
class Create_Character_Event(Event):
   character_name: str
   location_name: str
   background: str
   description: str
   def render(self) -> str:
      return ""
   def system(self, current_location_name:str) -> Optional[str]:
      if self.location_name == current_location_name:
         return f"A new character is created, '{self.character_name}', {self.background}, {self.description}"
      return None

@dataclass
class Start_Conversation_Event(Event):
   character_name: str
   event_description: str
   def implication(self) -> Optional[State]:
      return State.LOCATION_TALK

@dataclass
class End_Converstation_Event(Event):
   def implication(self) -> Optional[State]:
      return State.LOCATION_IDLE

@dataclass
class Speak_Event(Event):
   with_character: str
   is_player_speaking: bool
   text: str
   def render(self) -> str:
      cleaned_text = self.text.replace('"', "'")
      return "speak_" + ("player_to_npc" if self.is_player_speaking else "npc_to_player") + f'("{cleaned_text}")'

@dataclass
class Begin_Traveling_Event(Event):
   description: str
   def implication(self) -> Optional[State]:
      return State.TRAVELING

@dataclass
class Quest_Start(Event):
   quest_name: str
   quest_description: str

@dataclass
class Quest_Complete(Event):
   quest_name: str

event_dictionary = { n:E for n,E in locals().items() if isinstance(E, type) and issubclass(E, Event) }
