from typing import Optional
from enum import Enum
from dataclasses import dataclass

import logging
logger = logging.getLogger("Diff_and_Bas")
logger.setLevel(logging.DEBUG)
LOG_FORMAT = logging.Formatter("%(levelname)s: %(message)s")
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(LOG_FORMAT)
logger.addHandler(console)

class State(Enum):
   TOWN_IDLE   = "TOWN_IDLE"
   TOWN_TALK   = "TOWN_TALK"
   ON_THE_MOVE = "ON_THE_MOVE"
   EVENT_INIT  = "EVENT_INIT"

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
