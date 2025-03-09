from typing import Optional
from dataclasses import dataclass
import os, sys, datetime

import logging
logger = logging.getLogger("Diff_and_Bas")
logger.setLevel(logging.DEBUG)
LOG_FORMAT = logging.Formatter("%(levelname)s: %(message)s")

IMAGE_CHARS_WIDE = 90
IMAGE_CHARS_TALL = 60

class Save_Data:
   root: str
   logs_dirpath: str
   images_dirpath: str

   @staticmethod
   def config(root:str):
      Save_Data.root = root
      Save_Data.logs_dirpath = os.path.join("logs", datetime.datetime.now().strftime("%m-%d-%Y_%H-%M-%S"))
      Save_Data.images_dirpath = "images"

   @staticmethod
   def get_and_make(*path:str, is_file:bool=False) -> str:
      assert len(path) > 0 or not is_file
      comps = path[:-1] if is_file else path
      dirpath = os.path.join(Save_Data.root, *comps)
      os.makedirs(dirpath, exist_ok=True)
      return os.path.join(dirpath, path[-1]) if is_file else dirpath

@dataclass
class Image_Prompt:
   text: str
   uuid: str

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
   def image_prompt(self) -> Optional[Image_Prompt]:
      return None

def exc_loc_str() -> str:
   _, _, exc_tb = sys.exc_info()
   if exc_tb is None: return "?:?"
   return f"{os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}"
