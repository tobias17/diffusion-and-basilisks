from __future__ import annotations
from common import Event, Image_Prompt
from functions import Function_Map, Function, Parameter
from game import Game

from dataclasses import dataclass, field
from typing import Tuple, Optional
import uuid


@dataclass
class Player_Request_Action_Event(Event):
   text: str
   def clean(self) -> None:
      self.text = self.text.replace("\\", "").replace('"', "'")
   def player(self, game:Game) -> Optional[str]:
      return f'You request: "{self.text}"'
   def system(self) -> Optional[str]:
      return f'PLAYER.request_action(text="{self.text}")'
   def is_player_provided(self) -> bool:
      return True
def player_request_action(self:Game, text:str) -> Tuple[bool,str]:
   self.add_event(Player_Request_Action_Event(text))
   return True, ""


@dataclass
class Create_Location_Event(Event):
   loc_id: str
   name: str
   desc: str
   image_uuid: str = field(default_factory=lambda: uuid.uuid4().hex)
   def player(self, game:Game) -> Optional[str]:
      return f"You discover a new location, {self.name}"
   def image_prompt(self) -> Optional[Image_Prompt]:
      return Image_Prompt(self.desc, self.image_uuid)
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
   for event in self.events:
      if isinstance(event, Create_Location_Event) and event.loc_id == loc_id:
         self.add_event(Move_Player_To_Event(loc_id))
         return True, ""
   return False, f"Could not find a location with the ID '{loc_id}'"
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
   start_loc_id: str
   first_name: str
   last_name: str
   desc: str
   image_uuid: str = field(default_factory=lambda: uuid.uuid4().hex)
   def player(self, game:Game) -> Optional[str]:
      return f"You meet a new character, {self.first_name} {self.last_name}"
   def image_prompt(self) -> Optional[Image_Prompt]:
      return Image_Prompt(self.desc, self.image_uuid)
def create_npc(self:Game, npc_id:str, start_loc_id:str, first_name:str, last_name:str, desc:str) -> Tuple[bool,str]:
   first_name = first_name.strip()
   if not first_name:
      return False, "first_name cannot be empty"
   last_name = last_name.strip()
   if not last_name:
      return False, "last_name cannot be empty"
   for event in self.events:
      if isinstance(event, Create_Npc_Event) and event.npc_id.lower() == npc_id.lower():
         return False, f"A character with the ID '{npc_id}' already exists"
   self.add_event(Create_Npc_Event(npc_id, start_loc_id, first_name, last_name, desc))
   return True, ""
Function_Map.funcs.append(
   create_npc_func := Function(
      create_npc, "GAME.create_npc",
      Parameter("npc_id", str),
      Parameter("start_loc_id", str),
      Parameter("first_name", str),
      Parameter("last_name", str),
      Parameter("desc", str),
   )
)
Create_Npc_Event.system = (lambda e: create_npc_func.system(e)) # type: ignore


@dataclass
class Speak_Player_to_Npc_Event(Event):
   npc_id: str
   text: str
   def system(self) -> Optional[str]:
      return f'PLAYER.speak_to_npc(npc_id="{self.npc_id}", text="{self.text}")'
   def player(self, game:Game) -> Optional[str]:
      return f'You tell {game.get_npc_name(self.npc_id)}: "{self.text}"'
   def is_player_provided(self) -> bool:
      return True
def speak_player_to_npc(self:Game, npc_id:str, text:str) -> Tuple[bool,str]:
   for event in self.events:
      if isinstance(event, Create_Npc_Event) and event.npc_id == npc_id:
         self.add_event(Speak_Player_to_Npc_Event(npc_id, text))
         return True, ""
   return False, f"Failed to find a Character with the ID '{npc_id}'"


@dataclass
class Speak_Npc_to_player(Event):
   npc_id: str
   text: str
   def player(self, game:Game) -> Optional[str]:
      return f'{game.get_npc_name(self.npc_id)} tells You: "{self.text}"'
def speak_npc_to_player(self:Game, npc_id:str, text:str) -> Tuple[bool,str]:
   for event in self.events:
      if isinstance(event, Create_Npc_Event) and event.npc_id == npc_id:
         self.add_event(Speak_Npc_to_player(npc_id, text))
         return True, ""
   return False, f"Failed to find a Character with the ID '{npc_id}'"
Function_Map.funcs.append(
   speak_npc_to_player_func := Function(
      speak_npc_to_player, "NPC.speak_to_player",
      Parameter("npc_id", str),
      Parameter("text", str),
   )
)
Speak_Npc_to_player.system = (lambda e: speak_npc_to_player_func.system(e)) # type: ignore


@dataclass
class Speak_Npc_to_Npc_Event(Event):
   from_npc_id: str
   to_npc_id: str
   text: str
   def player(self, game:Game) -> Optional[str]:
      return f'{game.get_npc_name(self.from_npc_id)} tells {game.get_npc_name(self.to_npc_id)}: "{self.text}"'
def speak_npc_to_npc(self:Game, from_npc_id:str, to_npc_id:str, text:str) -> Tuple[bool,str]:
   if from_npc_id == to_npc_id:
      return False, "An NPC cannot talk to themselves"
   found_from = found_to = False
   for event in self.events:
      if isinstance(event, Create_Npc_Event):
         if event.npc_id == from_npc_id:
            found_from = True
         elif event.npc_id == to_npc_id:
            found_to = True
         if found_from and found_to:
            self.add_event(Speak_Npc_to_Npc_Event(from_npc_id, to_npc_id, text))
            return True, ""
   if not found_from:
      return False, f"Failed to find a Character with the ID '{from_npc_id}'"
   if not found_to:
      return False, f"Failed to find a Character with the ID '{to_npc_id}'"
   raise RuntimeError("Invalid state")
Function_Map.funcs.append(
   speak_npc_to_npc_func := Function(
      speak_npc_to_npc, "NPC.speak_to_npc",
      Parameter("from_npc_id", str),
      Parameter("to_npc_id", str),
      Parameter("text", str),
   )
)
Speak_Npc_to_Npc_Event.system = (lambda e: speak_npc_to_npc_func.system(e)) # type: ignore


@dataclass
class Narrate_Event(Event):
   text: str
   def player(self, game:Game) -> Optional[str]:
      return f'Narrator: "{self.text}"'
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


@dataclass
class Start_Quest_Event(Event):
   quest_id: str
   name: str
   desc: str
   def player(self, game:Game) -> Optional[str]:
      return f"You gained a new quest, {self.name}: {self.desc}"
def start_quest(self:Game, quest_id:str, name:str, desc:str) -> Tuple[bool,str]:
   for event in self.events:
      if isinstance(event, Start_Quest_Event) and event.quest_id == quest_id:
         return False, f"A quest with ID '{quest_id}' already exists"
   self.add_event(Start_Quest_Event(quest_id, name, desc))
   return True, ""
Function_Map.funcs.append(
   Function(
      start_quest, "GAME.give_player_quest",
      Parameter("quest_id", str),
      Parameter("name", str),
      Parameter("desc", str),
   )
)


@dataclass
class End_Quest_Event(Event):
   quest_id: str
   def player(self, game:Game) -> Optional[str]:
      return f"You completed a quest, {game.get_quest_name(self.quest_id)}"
def end_quest(self:Game, quest_id:str) -> Tuple[bool,str]:
   for event in reversed(self.events):
      if isinstance(event, End_Quest_Event) and event.quest_id == quest_id:
         return False, f"The quest with ID '{quest_id}' has already been completed"
      if isinstance(event, Start_Quest_Event) and event.quest_id == quest_id:
         self.add_event(End_Quest_Event(quest_id))
         return True, ""
   return False, f"Could not find quest with ID '{quest_id}'"
Function_Map.funcs.append(
   Function(
      end_quest, "GAME.complete_quest",
      Parameter("quest_id", str),
   )
)


event_dictionary = { n:E for n,E in locals().items() if isinstance(E, type) and issubclass(E, Event) }
