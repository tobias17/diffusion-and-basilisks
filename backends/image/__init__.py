from abc import ABC, abstractmethod
from typing import Type, Dict

class Image_Backend(ABC):
   @abstractmethod
   def generate_image(self, prompt:str, filepath:str) -> None:
      pass

class Image_Registry:
   mapping: Dict[str,Type[Image_Backend]] = {}
   @staticmethod
   def add(name:str, backend:Type[Image_Backend]) -> None:
      assert name not in Image_Registry.mapping, f"The image backend directory tried registering the name '{name}' more than once"
      Image_Registry.mapping[name] = backend
   @staticmethod
   def get(name:str) -> Type[Image_Backend]:
      value = Image_Registry.mapping.get(name)
      assert value is not None, f"Could not find image backend with name '{name}', options are {list(Image_Registry.mapping.values())}"
      return value

from . import tinyapi_image as _
