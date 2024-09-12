from typing import Optional
from enum import Enum
from dataclasses import dataclass

import logging, datetime, os
logger = logging.getLogger("Diff_and_Bas")

class State(Enum):
   TOWN_IDLE   = "TOWN_IDLE"
   TOWN_TALK   = "TOWN_TALK"
   ON_THE_MOVE = "ON_THE_MOVE"
   IN_EVENT    = "IN_EVENT"

   INITIALIZING  = "INITIALIZING"
   LOCATION_IDLE = "LOCATION_IDLE"
   LOCATION_TALK = "LOCATION_TALK"
   TRAVELING     = "TRAVELLING"

@dataclass
class Event:
   def implication(self) -> Optional[State]:
      return None
   def render(self) -> str:
      return str(self)
   def player(self)-> str:
      return str(self)
   def system(self, current_location_name:str) -> Optional[str]:
      return None
