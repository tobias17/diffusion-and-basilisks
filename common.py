from typing import Optional, Tuple
from dataclasses import dataclass
import os, sys

import logging
logger = logging.getLogger("Diff_and_Bas")
logger.setLevel(logging.DEBUG)
LOG_FORMAT = logging.Formatter("%(levelname)s: %(message)s")

class Save_Data:
   root: str
   def get_and_make(*path:str, is_file:bool=False) -> str:
      assert len(path) > 0 or not is_file
      comps = path[:-1] if is_file else path
      dirpath = os.path.join(Save_Data.root, *comps)
      os.makedirs(dirpath, exist_ok=True)
      return os.path.join(dirpath, path[-1]) if is_file else dirpath

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
   def uuid_and_prompt(self) -> Optional[Tuple[str,str]]:
      return None

def exc_loc_str() -> str:
   _, _, exc_tb = sys.exc_info()
   if exc_tb is None: return "?:?"
   return f"{os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}"
