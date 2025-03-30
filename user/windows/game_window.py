from game import Game
from user import Screen_Buffer, Special_Keys

from abc import ABC, abstractmethod
from typing import Union


class Game_Window(ABC):
   NAME: str
   screen_buffer: Screen_Buffer

   def accept_input(self) -> None:
      pass

   def clear_input(self, accept_input:bool=False) -> None:
      pass

   @abstractmethod
   def visualize_game(self, game:Game) -> None:
      pass

   @abstractmethod
   def write_to_buffer(self) -> None:
      pass

   def process_input(self, inp:Union[str,Special_Keys]) -> None:
      pass
