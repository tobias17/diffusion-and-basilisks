from abc import ABC, abstractmethod
from typing import List, Dict, Type

class Text_Backend(ABC):
   @abstractmethod
   def generate_response(self, messages:List[Dict[str,str]]) -> str:
      pass

class Text_Registry:
   mapping: Dict[str,Type[Text_Backend]] = {}
   @staticmethod
   def add(name:str, backend:Type[Text_Backend]) -> None:
      assert name not in Text_Registry.mapping, f"The image backend directory tried registering the name '{name}' more than once"
      Text_Registry.mapping[name] = backend
   @staticmethod
   def get(name:str) -> Type[Text_Backend]:
      value = Text_Registry.mapping.get(name)
      assert value is not None, f"Could not find image backend with name '{name}', options are {list(Text_Registry.mapping.values())}"
      return value

from . import tinyapi_text as _
