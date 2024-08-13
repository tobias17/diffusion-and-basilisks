from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from abc import ABC

class State(Enum):
   HUB_IDLE      = "HUB_IDLE"
   HUB_TALKING   = "HUB_TALKING"
   TRAVEL_IDLE   = "TRAVEL_IDLE"
   TRAVEL_TALK   = "TRAVEL_TALK"
   TRAVEL_COMBAT = "TRAVEL_COMBAT"
   TRAVEL_EVENT  = "TRAVEL_EVENT"

class Event: pass

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
   description: str
   def __str__(self) -> str:
      return f"Transition from {self.from_state} to {self.to_state}: {self.description}"



@dataclass
class Serializable(ABC):
   def to_json(self) -> Dict:
      return { k: (v.to_json() if isinstance(v, Serializable) else v) for k, v in asdict(self) } # type: ignore
   
   @classmethod
   def from_json(cls, obj:Dict):
      return cls(**cls.clean_json(obj))
   
   @classmethod
   def clean_json(cls, obj:Dict) -> Dict:
      return obj

@dataclass
class Character(Serializable):
   name: str
   character_description: str
   physical_description: str

@dataclass
class Converstation(Serializable):
   character_name: str
   dialogs: List[str]

@dataclass
class Hub(Serializable):
   characters: List[Character]
   @classmethod
   def clean_json(cls, obj:Dict) -> Dict:
      obj["characters"] = [Character.from_json(c) for c in obj["characters"]]
      return obj

@dataclass
class World(Serializable):
   state: State
   hub_alias: str
   hubs: List[Hub]
   @classmethod
   def clean_json(cls, obj:Dict) -> Dict:
      obj["hubs"] = [Hub.from_json(c) for c in obj["hubs"]]
      return obj
