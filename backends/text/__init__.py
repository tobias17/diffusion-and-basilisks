from abc import ABC, abstractmethod
from typing import List, Dict

class Text_Backend(ABC):
   @abstractmethod
   def generate_response(self, messages:List[Dict[str,str]]) -> str:
      pass

from .tinyapi_text import Tinyapi_Text
