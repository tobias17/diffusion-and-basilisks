from typing import List
import os, sys

def exc_loc_str() -> str:
   _, _, exc_tb = sys.exc_info()
   if exc_tb is None: return "?:?"
   return f"{os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}"

def trim_text(text:str, max_width:int) -> List[str]:
   lines = []
   while len(text) > max_width:
      lines.append(text[:max_width])
      text = text[max_width:]
   lines.append(text)
   return lines
