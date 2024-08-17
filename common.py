from typing import Optional
from enum import Enum

class State(Enum):
   INITIALIZING  = "INITIALIZING"
   LOCATION_IDLE = "LOCATION_IDLE"
   LOCATION_TALK = "LOCATION_TALK"
   TRAVELING     = "TRAVELLING"

class Event:
   def implication(self) -> Optional[State]:
      return None
   def render(self) -> str:
      return str(self)
