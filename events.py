from __future__ import annotations
from common import Event, Image_Prompt
from functions import Function_Map, Function, Parameter
from game import Game

from dataclasses import dataclass, field
from typing import Tuple, Optional
import uuid


@dataclass
class Player_Request_Action(Event):
   text: str
   def clean(self) -> None:
      self.text = self.text.replace("\\", "").replace('"', "'")
   def player(self, game:Game) -> Optional[str]:
      return f'You request: "{self.text}"'
   def system(self) -> Optional[str]:
      return f'PLAYER.request_action(text="{self.text}")'
   def is_player_provided(self) -> bool:
      return True
def player_request_action(game:Game, text:str) -> Tuple[bool,str]:
   game.add_event(Player_Request_Action(text))
   return True, ""


@dataclass
class Create_Location(Event):
   loc_id: str
   name: str
   desc: str
   tell_player: bool
   automove_player_to: bool
   image_uuid: str = field(default_factory=lambda: uuid.uuid4().hex)
   def player(self, game:Game) -> Optional[str]:
      if self.automove_player_to:
         return f"You discover a new location, {self.name}, and arrive there"
      if not self.tell_player:
         return None
      return f"You discover a new location, {self.name}"
   def image_prompt(self) -> Optional[Image_Prompt]:
      return Image_Prompt(self.desc, self.image_uuid)
def create_location(game:Game, loc_id:str, name:str, desc:str, tell_player:bool, automove_player_to:bool=True) -> Tuple[bool,str]:
   for event in game.events:
      if isinstance(event, Create_Location) and event.loc_id.lower() == loc_id.lower():
         return False, f"A location with the ID '{loc_id}' already exists, no need to create another"
   game.add_event(Create_Location(loc_id, name, desc, tell_player, automove_player_to))
   return True, ""
Function_Map.funcs.append(
   create_location_func := Function(
      create_location, "GAME.create_location",
      Parameter("loc_id", str),
      Parameter("name", str),
      Parameter("desc", str),
      Parameter("tell_player", bool),
      Parameter("automove_player_to", bool, default=True),
   )
)
Create_Location.system = (lambda e: create_location_func.system(e)) # type: ignore


@dataclass
class Move_Player_To(Event):
   loc_id: str
   def player(self, game:Game) -> Optional[str]:
      return f"You arrive at {game.get_loc_name(self.loc_id)}"
def move_player_to(game:Game, loc_id:str) -> Tuple[bool,str]:
   seen_move = False
   for event in reversed(game.events):
      if isinstance(event, Move_Player_To):
         if event.loc_id == loc_id:
            return True, "" # The player was last moved here, no action needed
         seen_move = True
      if isinstance(event, Create_Location) and event.loc_id == loc_id:
         if seen_move or not event.automove_player_to:
            # Only requires action if we have either moved since this was created or we werent automoved
            game.add_event(Move_Player_To(loc_id))
         return True, ""
   return False, f"Could not find a location with the ID '{loc_id}'"
Function_Map.funcs.append(
   move_player_to_func := Function(
      move_player_to, "GAME.move_player_to",
      Parameter("loc_id", str),
   )
)
Move_Player_To.system = (lambda e: move_player_to_func.system(e)) # type: ignore


@dataclass
class Create_Npc(Event):
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
def create_npc(game:Game, npc_id:str, start_loc_id:str, first_name:str, last_name:str, desc:str) -> Tuple[bool,str]:
   first_name = first_name.strip()
   if not first_name:
      return False, "first_name cannot be empty"
   last_name = last_name.strip()
   if not last_name:
      return False, "last_name cannot be empty"
   for event in game.events:
      if isinstance(event, Create_Npc) and event.npc_id.lower() == npc_id.lower():
         return False, f"A character with the ID '{npc_id}' already exists"
   game.add_event(Create_Npc(npc_id, start_loc_id, first_name, last_name, desc))
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
Create_Npc.system = (lambda e: create_npc_func.system(e)) # type: ignore


@dataclass
class Kill_Npc(Event):
   npc_id: str
   def player(self, game:Game) -> Optional[str]:
      return f"{game.get_npc_name(self.npc_id)} dies"
def kill_npc(game:Game, npc_id:str) -> Tuple[bool,str]:
   for event in reversed(game.events):
      if isinstance(event, Kill_Npc) and event.npc_id == npc_id:
         return True, "" # Npc is already dead, no action to perform
      if isinstance(event, Create_Npc) and event.npc_id == npc_id:
         game.add_event(Kill_Npc(npc_id))
         return True, ""
   return False, f"Could not find an NPC with ID '{npc_id}'"
Function_Map.funcs.append(
   kill_npc_func := Function(
      kill_npc, "GAME.kill_npc",
      Parameter("npc_id", str),
   )
)
Create_Npc.system = (lambda e: kill_npc_func.system(e)) # type: ignore


@dataclass
class Move_Npc(Event):
   npc_id: str
   loc_id: str
   def player(self, game:Game) -> Optional[str]:
      loc_name = game.get_loc_name(self.loc_id) if game.player_knows_about(self.loc_id) else "UNKNOWN"
      return f"{game.get_npc_name(self.npc_id)} moves to {loc_name}"
   def system(self) -> Optional[str]:
      return f'GAME.move_npc(npc_id="{self.npc_id}", to_loc_id="{self.loc_id}")'
def move_npc(game:Game, npc_id:str, to_loc_id:str) -> Tuple[bool,str]:
   found_npc = found_loc = found_move = False
   for event in reversed(game.events):
      if isinstance(event, Create_Npc) and event.npc_id == npc_id:
         if event.start_loc_id == to_loc_id and not found_move:
            return True, "" # The NPC got created here and has not moved since, no action needed
         found_npc = True
      elif isinstance(event, Move_Npc) and not found_move:
         if event.loc_id == to_loc_id:
            return True, "" # The NPC was last moved here, no action needed
         found_move = True
      elif isinstance(event, Create_Location) and event.loc_id == to_loc_id:
         found_loc = True
      if found_npc and found_loc:
         game.add_event(Move_Npc(npc_id, to_loc_id))
         return True, ""
   if not found_npc:
      return False, f"Failed to find NPC with ID '{npc_id}'"
   if not found_loc:
      return False, f"Failed to find Location with ID '{to_loc_id}'"
   raise RuntimeError("Invalid state")
Function_Map.funcs.append(
   move_npc_func := Function(
      move_npc, "GAME.move_npc",
      Parameter("npc_id", str),
      Parameter("to_loc_id", str),
   )
)


@dataclass
class Speak_Player_to_Npc(Event):
   npc_id: str
   text: str
   def system(self) -> Optional[str]:
      return f'PLAYER.speak_to_npc(npc_id="{self.npc_id}", text="{self.text}")'
   def player(self, game:Game) -> Optional[str]:
      return f'You tell {game.get_npc_name(self.npc_id)}: "{self.text}"'
   def is_player_provided(self) -> bool:
      return True
def speak_player_to_npc(game:Game, npc_id:str, text:str) -> Tuple[bool,str]:
   for event in game.events:
      if isinstance(event, Create_Npc) and event.npc_id == npc_id:
         game.add_event(Speak_Player_to_Npc(npc_id, text))
         return True, ""
   return False, f"Failed to find a NPC with the ID '{npc_id}'"


@dataclass
class Speak_Npc_to_Player(Event):
   npc_id: str
   text: str
   def player(self, game:Game) -> Optional[str]:
      return f'{game.get_npc_name(self.npc_id)} tells You: "{self.text}"'
def speak_npc_to_player(game:Game, npc_id:str, text:str) -> Tuple[bool,str]:
   curr_loc_id = game.get_curr_loc_id()
   npc_infos = game.get_npc_infos()
   for npc_info in npc_infos:
      if npc_id == npc_info.npc_id:
         if curr_loc_id != npc_info.loc_id:
            return False, f"NPC with ID '{npc_id}' not in current location '{curr_loc_id}', is instead in '{npc_info.loc_id}'"
         game.add_event(Speak_Npc_to_Player(npc_id, text))
         return True, ""
   return False, f"Failed to find a NPC with the ID '{npc_id}'"
Function_Map.funcs.append(
   speak_npc_to_player_func := Function(
      speak_npc_to_player, "NPC.speak_to_player",
      Parameter("npc_id", str),
      Parameter("text", str),
   )
)
Speak_Npc_to_Player.system = (lambda e: speak_npc_to_player_func.system(e)) # type: ignore


@dataclass
class Speak_Npc_to_Npc(Event):
   from_npc_id: str
   to_npc_id: str
   text: str
   def player(self, game:Game) -> Optional[str]:
      return f'{game.get_npc_name(self.from_npc_id)} tells {game.get_npc_name(self.to_npc_id)}: "{self.text}"'
def speak_npc_to_npc(game:Game, from_npc_id:str, to_npc_id:str, text:str) -> Tuple[bool,str]:
   if from_npc_id == to_npc_id:
      return False, "An NPC cannot talk to themselves"

   curr_loc_id = game.get_curr_loc_id()
   npc_infos = game.get_npc_infos()
   found_from = found_to = False
   for npc_info in npc_infos:
      if from_npc_id == npc_info.npc_id:
         if curr_loc_id != npc_info.loc_id:
            return False, f"NPC with ID '{from_npc_id}' not in current location '{curr_loc_id}', is instead in '{npc_info.loc_id}'"
         found_from = True
      elif to_npc_id == npc_info.npc_id:
         if curr_loc_id != npc_info.loc_id:
            return False, f"NPC with ID '{to_npc_id}' not in current location '{curr_loc_id}', is instead in '{npc_info.loc_id}'"
         found_to = True
      if found_from and found_to:
         game.add_event(Speak_Npc_to_Npc(from_npc_id, to_npc_id, text))
         return True, ""

   if not found_from:
      return False, f"Failed to find a NPC with the ID '{from_npc_id}'"
   if not found_to:
      return False, f"Failed to find a NPC with the ID '{to_npc_id}'"
   raise RuntimeError("Invalid state")
Function_Map.funcs.append(
   speak_npc_to_npc_func := Function(
      speak_npc_to_npc, "NPC.speak_to_npc",
      Parameter("from_npc_id", str),
      Parameter("to_npc_id", str),
      Parameter("text", str),
   )
)
Speak_Npc_to_Npc.system = (lambda e: speak_npc_to_npc_func.system(e)) # type: ignore


@dataclass
class Narrate(Event):
   text: str
   def player(self, game:Game) -> Optional[str]:
      return f'Narrator: "{self.text}"'
def narrate(game:Game, text:str) -> Tuple[bool,str]:
   game.add_event(Narrate(text))
   return True, ""
Function_Map.funcs.append(
   narrate_func := Function(
      narrate, "NARRATOR.speak",
      Parameter("text", str),
   )
)
Narrate.system = (lambda e: narrate_func.system(e)) # type: ignore


@dataclass
class Start_Quest(Event):
   quest_id: str
   name: str
   desc: str
   def player(self, game:Game) -> Optional[str]:
      return f"You gained a new quest, {self.name}: {self.desc}"
def start_quest(game:Game, quest_id:str, name:str, desc:str) -> Tuple[bool,str]:
   for event in game.events:
      if isinstance(event, Start_Quest) and event.quest_id == quest_id:
         return False, f"A quest with ID '{quest_id}' already exists"
   game.add_event(Start_Quest(quest_id, name, desc))
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
class End_Quest(Event):
   quest_id: str
   def player(self, game:Game) -> Optional[str]:
      return f"You completed a quest, {game.get_quest_name(self.quest_id)}"
def end_quest(game:Game, quest_id:str) -> Tuple[bool,str]:
   for event in reversed(game.events):
      if isinstance(event, End_Quest) and event.quest_id == quest_id:
         return False, f"The quest with ID '{quest_id}' has already been completed"
      if isinstance(event, Start_Quest) and event.quest_id == quest_id:
         game.add_event(End_Quest(quest_id))
         return True, ""
   return False, f"Could not find quest with ID '{quest_id}'"
Function_Map.funcs.append(
   Function(
      end_quest, "GAME.complete_quest",
      Parameter("quest_id", str),
   )
)


@dataclass
class Give_Player_Unique_Item(Event):
   item_id: str
   name: str
   desc: str
   def player(self, game:Game) -> Optional[str]:
      return f"You gained a new item, {self.name}: {self.desc}"
def give_player_unique_item(game:Game, item_id:str, name:str, desc:str) -> Tuple[bool,str]:
   for event in game.events:
      if isinstance(event, Give_Player_Stackable_Items) and event.item_id == item_id:
         return False, f"A Stackable item with ID '{item_id}' already exists"
   for event in reversed(game.events):
      if isinstance(event, Give_Player_Unique_Item) and event.item_id == item_id:
         return False, f"The player already has an item with ID '{item_id}'"
      if isinstance(event, Remove_Player_Unique_Item) and event.item_id == item_id:
         break
   game.add_event(Give_Player_Unique_Item(item_id, name, desc))
   return True, ""
Function_Map.funcs.append(
   give_player_unique_item_func := Function(
      give_player_unique_item, "GAME.give_player_unique_item",
      Parameter("item_id", str),
      Parameter("name", str),
      Parameter("desc", str),
   )
)
Give_Player_Unique_Item.system = (lambda e: give_player_unique_item_func.system(e)) # type: ignore


@dataclass
class Remove_Player_Unique_Item(Event):
   item_id: str
   reason: str
   def player(self, game:Game) -> Optional[str]:
      return f"You lost an item, {game.get_item_name(self.item_id)}: {self.reason}"
def remove_player_unique_item(game:Game, item_id:str, reason:str) -> Tuple[bool,str]:
   for event in reversed(game.events):
      if isinstance(event, Give_Player_Unique_Item) and event.item_id == item_id:
         return False, f"The player already has an item with ID '{item_id}'"
      if isinstance(event, Remove_Player_Unique_Item) and event.item_id == item_id:
         break
   for event in reversed(game.events):
      if isinstance(event, Give_Player_Unique_Item) and event.item_id == item_id:
         game.add_event(Remove_Player_Unique_Item(item_id, reason))
         return True, ""
      if isinstance(event, Remove_Player_Unique_Item) and event.item_id == item_id:
         break
   return False, f"The player does not have an item with ID '{item_id}'"
Function_Map.funcs.append(
   remove_player_unique_item_func := Function(
      remove_player_unique_item, "GAME.remove_player_unique_item",
      Parameter("item_id", str),
      Parameter("reason", str),
   )
)
Remove_Player_Unique_Item.system = (lambda e: remove_player_unique_item_func.system(e)) # type: ignore


@dataclass
class Give_Player_Stackable_Items(Event):
   item_id: str
   name: str
   count: int
   desc: str
   def player(self, game:Game) -> Optional[str]:
      return f"You gained {self.count} {self.name}: {self.desc}"
def give_player_stackable_items(game:Game, item_id:str, name:str, count:int, desc:str) -> Tuple[bool,str]:
   if count <= 0:
      return False, f"Cannot give non-positive amount {count} of items to player"
   game.add_event(Give_Player_Stackable_Items(item_id, name, count, desc))
   return True, ""
Function_Map.funcs.append(
   give_player_stackable_items_func := Function(
      give_player_stackable_items, "GAME.give_player_stackable_items",
      Parameter("item_id", str),
      Parameter("name", str),
      Parameter("count", int),
      Parameter("desc", str),
   )
)
Give_Player_Stackable_Items.system = (lambda e: give_player_stackable_items_func.system(e)) # type: ignore


@dataclass
class Remove_Player_Stackable_Items(Event):
   item_id: str
   count: int
   reason: str
   def player(self, game:Game) -> Optional[str]:
      return f"You lost an item, {game.get_item_name(self.item_id)}: {self.reason}"
def remove_player_stackable_items(game:Game, item_id:str, count:int, reason:str) -> Tuple[bool,str]:
   current = 0
   for event in game.events:
      if isinstance(event, Give_Player_Stackable_Items) and event.item_id == item_id:
         current += event.count
      if isinstance(event, Remove_Player_Stackable_Items) and event.item_id == item_id:
         current -= event.count
   if current < count:
      return False, f"The player only has {current} items with ID '{item_id}', cannot remove {count}"
   game.add_event(Remove_Player_Stackable_Items(item_id, count, reason))
   return True, ""
Function_Map.funcs.append(
   remove_player_stackable_items_func := Function(
      remove_player_stackable_items, "GAME.remove_player_stackable_items",
      Parameter("item_id", str),
      Parameter("count", int),
      Parameter("reason", str),
   )
)
Remove_Player_Stackable_Items.system = (lambda e: remove_player_stackable_items_func.system(e)) # type: ignore


event_dictionary = { n:E for n,E in locals().items() if isinstance(E, type) and issubclass(E, Event) }
