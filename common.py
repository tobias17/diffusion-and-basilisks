from typing import Optional
from enum import Enum

import logging, datetime
logger = logging.getLogger("Diff_and_Bas")
logger.setLevel(logging.DEBUG)
FORMAT = logging.Formatter("%(levelname)s: %(message)s")
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(FORMAT)
logger.addHandler(console)
file = logging.FileHandler(datetime.datetime.now().strftime("logs/%m-%d-%Y_%H-%M-%S.log"))
file.setLevel(logging.DEBUG)
file.setFormatter(FORMAT)
logger.addHandler(file)

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
