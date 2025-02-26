from abc import ABC, abstractmethod

class Image_Backend(ABC):
   @abstractmethod
   def generate_image(self, prompt:str, filepath:str) -> None:
      pass

from .tinyapi_image import Tinyapi_Image
