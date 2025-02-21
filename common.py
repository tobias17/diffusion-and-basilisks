from typing import Optional
from dataclasses import dataclass
import os, sys

import logging
logger = logging.getLogger("Diff_and_Bas")
logger.setLevel(logging.DEBUG)
LOG_FORMAT = logging.Formatter("%(levelname)s: %(message)s")

@dataclass
class Event:
   def player(self, game)-> Optional[str]:
      return None
   def system(self) -> Optional[str]:
      return None
   def clean(self) -> None:
      pass
   def is_player_provided(self) -> bool:
      return False

def exc_loc_str() -> str:
   _, _, exc_tb = sys.exc_info()
   if exc_tb is None: return "?:?"
   return f"{os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}"
