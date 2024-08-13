from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from abc import ABC

class State(Enum):
   HUB_IDLE = "HubIdle"
   HUB_TALKING = "HubTalking"
   TRAVEL_IDLE = "TravelIdle"
   TRAVEL_TALK = "TravelTalk"
   TRAVEL_COMBAT = "TravelCombat"
   TRAVEL_EVENT = "TravelEvent"

class Event: pass

@dataclass
class SpeakEvent(Event):
   with_character: str
   is_player_speaking: bool
   text: str

@dataclass
class StateEvent(Event):
   from_state: State
   to_state: State





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
