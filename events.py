from __future__ import annotations
from common import Event
from functions import Function_Map, Function, Parameter
from game import Game

from dataclasses import dataclass
from typing import Tuple, Optional


@dataclass
class Player_Input_Event(Event):
   text: str
   def player(self, game:Game) -> Optional[str]:
      return f'You say: "{self.text}"'
def player_input(self:Game, text:str) -> Tuple[bool,str]:
   self.add_event(Player_Input_Event(text))
   return True, ""


@dataclass
class Create_Location_Event(Event):
   loc_id: str
   name: str
   desc: str
   def player(self, game:Game) -> Optional[str]:
      return f"You discover a new location, {self.name}"
def create_location(self:Game, loc_id:str, name:str, desc:str) -> Tuple[bool,str]:
   for event in self.events:
      if isinstance(event, Create_Location_Event) and event.loc_id.lower() == loc_id.lower():
         return False, f"A location with the ID '{loc_id}' already exists, no need to create another"
   self.add_event(Create_Location_Event(loc_id, name, desc))
   return True, ""
Function_Map.funcs.append(
   create_location_func := Function(
      create_location, "GAME.create_location",
      Parameter("loc_id", str),
      Parameter("name", str),
      Parameter("desc", str),
   )
)
Create_Location_Event.system = (lambda e: create_location_func.system(e)) # type: ignore


@dataclass
class Move_Player_To_Event(Event):
   loc_id: str
   def player(self, game:Game) -> Optional[str]:
      return f"You arrive at {game.get_loc_name(self.loc_id)}"
def move_player_to(self:Game, loc_id:str) -> Tuple[bool,str]:
   self.add_event(Move_Player_To_Event(loc_id))
   return True, ""
Function_Map.funcs.append(
   move_player_to_func := Function(
      move_player_to, "GAME.move_player_to",
      Parameter("loc_id", str),
   )
)
Move_Player_To_Event.system = (lambda e: move_player_to_func.system(e)) # type: ignore


@dataclass
class Create_Npc_Event(Event):
   npc_id: str
   first_name: str
   last_name: str
   desc: str
   def player(self, game:Game) -> Optional[str]:
      return f"You meet a new character, {self.first_name} {self.last_name}"
def create_npc(self:Game, npc_id:str, first_name:str, last_name:str, desc:str) -> Tuple[bool,str]:
   for event in self.events:
      if isinstance(event, Create_Npc_Event) and event.npc_id.lower() == npc_id.lower():
         return False, f"A character with the ID '{npc_id}' already exists"
   self.add_event(Create_Npc_Event(npc_id, first_name, last_name, desc))
   return True, ""
Function_Map.funcs.append(
   create_npc_func := Function(
      create_npc, "GAME.create_npc",
      Parameter("npc_id", str),
      Parameter("first_name", str),
      Parameter("last_name", str),
      Parameter("desc", str),
   )
)
Create_Npc_Event.system = (lambda e: create_npc_func.system(e)) # type: ignore


@dataclass
class Speak_Event(Event):
   npc_id: str
   text: str
   is_player_speaking: bool
   def system(self) -> Optional[str]:
      prefix = f"PLAYER.speak_to_npc" if self.is_player_speaking else "NPC.speak_to_player"
      return f'{prefix}(npc_id="{self.npc_id}", text="{self.text}")'
   def player(self, game:Game) -> Optional[str]:
      if self.is_player_speaking:
         return f"You tell {game.get_npc_name(self.npc_id)}: {self.text}"
      else:
         return f"{game.get_npc_name(self.npc_id)} tells you: {self.text}"
def speak_player_to_npc(self:Game, npc_id:str, text:str) -> Tuple[bool,str]:
   for event in self.events:
      if isinstance(event, Create_Npc_Event) and event.npc_id == npc_id:
         self.add_event(Speak_Event(npc_id, text, True))
         return True, ""
   return False, f"Failed to find a Character with the ID '{npc_id}'"
Function_Map.funcs.append(
   Function(
      speak_player_to_npc, "PLAYER.speak_to_npc",
      Parameter("npc_id", str),
      Parameter("text", str),
   )
)
def speak_npc_to_player(self:Game, npc_id:str, text:str) -> Tuple[bool,str]:
   for event in self.events:
      if isinstance(event, Create_Npc_Event) and event.npc_id == npc_id:
         self.add_event(Speak_Event(npc_id, text, False))
         return True, ""
   return False, f"Failed to find a Character with the ID '{npc_id}'"
Function_Map.funcs.append(
   Function(
      speak_npc_to_player, "NPC.speak_to_player",
      Parameter("npc_id", str),
      Parameter("text", str),
   )
)


@dataclass
class Narrate_Event(Event):
   text: str
   def player(self, game:Game) -> Optional[str]:
      return f"Narrator: {self.text}"
def narrate(self:Game, text:str) -> Tuple[bool,str]:
   self.add_event(Narrate_Event(text))
   return True, ""
Function_Map.funcs.append(
   narrate_func := Function(
      narrate, "NARRATOR.speak",
      Parameter("text", str),
   )
)
Narrate_Event.system = (lambda e: narrate_func.system(e)) # type: ignore


event_dictionary = { n:E for n,E in locals().items() if isinstance(E, type) and issubclass(E, Event) }
