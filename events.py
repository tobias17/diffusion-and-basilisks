from common import State, Event

from dataclasses import dataclass

@dataclass
class CreateHubEvent(Event):
   hub_name: str
   hub_description: str
   def __init__(self, hub_name:str, hub_description:str):
      self.hub_name = hub_name
      hub_description = hub_description.strip().strip(".,")
      self.hub_description = hub_description[0].lower() + hub_description[1:]
   def __str__(self) -> str:
      return f"You discover {self.hub_name}, {self.hub_description}"

@dataclass
class SpeakEvent(Event):
   with_character: str
   is_player_speaking: bool
   text: str
   def __str__(self) -> str:
      return (f"Player to {self.with_character}" if self.is_player_speaking else f"{self.with_character} to Player") + f": {self.text}"

@dataclass
class StateTransitionEvent(Event):
   from_state: State
   to_state: State
   def __str__(self) -> str:
      return f"Transition from {self.from_state} to {self.to_state}"
