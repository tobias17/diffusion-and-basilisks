from enum import Enum

class State(Enum):
   INITIALIZING  = "INITIALIZING"
   LOCATION_IDLE = "LOCATION_IDLE"
   LOCATION_TALK = "LOCATION_TALK"
   TRAVELING     = "TRAVELLING"

class Event:
   def render(self) -> str:
      return str(self)
