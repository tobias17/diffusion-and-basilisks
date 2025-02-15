from common import Event
from functions import Function_Map, Function, Parameter
from game import Game

from dataclasses import dataclass
from typing import Tuple


@dataclass
class Create_Location_Event(Event):
   loc_id: str
   name: str
   desc: str
def create_location(self:Game, loc_id:str, name:str, desc:str) -> Tuple[bool,str]:
   for event in self.events:
      if isinstance(event, Create_Location_Event) and event.loc_id.lower() == loc_id.lower():
         return False, f"A location with the ID '{loc_id}' already exists, no need to create another"
   self.add_event(Create_Location_Event(loc_id, name, desc))
   return True, ""
Function_Map.funcs.append(
   Function(
      create_location, "GAME.create_location",
      Parameter("town_name", str),
      Parameter("backstory", str),
      Parameter("description", str),
   )
)


@dataclass
class Move_To_Event(Event):
   loc_id: str
def move_to(self:Game, loc_id:str) -> Tuple[bool,str]:
   self.add_event(Move_To_Event(loc_id))
   return True, ""
Function_Map.funcs.append(
   Function(
      move_to, "PLAYER.move_to",
      Parameter("loc_id", str),
   )
)


@dataclass
class Create_Npc_Event(Event):
   npc_id: str
   name: str
   desc: str
def create_npc(self:Game, npc_id:str, name:str, desc:str) -> Tuple[bool,str]:
   for event in self.events:
      if isinstance(event, Create_Npc_Event) and event.npc_id.lower() == npc_id.lower():
         return False, f"A location with the ID '{npc_id}' already exists, no need to create another"
   self.add_event(Create_Npc_Event(npc_id, name, desc))
   return True, ""
Function_Map.funcs.append(
   Function(
      create_npc, "GAME.create_npc",
      Parameter("npc_id", str),
      Parameter("name", str),
      Parameter("desc", str),
   )
)


@dataclass
class Speak_Event(Event):
   npc_id: str
   text: str
   is_player_speaking: bool
def speak_player_to_npc(self:Game, npc_id:str, text:str) -> Tuple[bool,str]:
   self.add_event(Speak_Event(npc_id, text, True))
   return True, ""
Function_Map.funcs.append(
   Function(
      speak_player_to_npc, "PLAYER.speak_to_npc",
      Parameter("npc_id", str),
      Parameter("text", str),
   )
)
def speak_npc_to_player(self:Game, npc_id:str, text:str) -> Tuple[bool,str]:
   self.add_event(Speak_Event(npc_id, text, False))
   return True, ""
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
def narrate(self:Game, text:str) -> Tuple[bool,str]:
   self.add_event(Narrate_Event(text))
   return True, ""
Function_Map.funcs.append(
   Function(
      narrate, "NARRATOR.speak",
      Parameter("text", str),
   )
)


event_dictionary = { n:E for n,E in locals().items() if isinstance(E, type) and issubclass(E, Event) }
