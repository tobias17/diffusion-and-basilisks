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
   TOWN_IDLE = "TOWN_IDLE"
   TOWN_TALK = "TOWN_TALK"

   ON_THE_MOVE = "ON_THE_MOVE"

   SHOP_ENCOUNTER   = "SHOP_ENCOUNTER"
   TRAP_ENCOUNTER   = "TRAP_ENCOUNTER"
   COMBAT_ENCOUNTER = "COMBAT_ENCOUNTER"

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
   def clean(self) -> None:
      pass

   def _strip_text(self, text:str) -> str:
      return text.strip().strip(",.")
   def _fix_name(self, text:str) -> str:
      chunks = self._strip_text(text).split(" ")
      return " ".join(c[0].upper() + (c[1:].lower() if len(c) >= 2 else "") for c in chunks if len(c) >= 1)
