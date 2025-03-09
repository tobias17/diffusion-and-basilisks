from __future__ import annotations
from common import Event
import events as E

from typing import List, Optional, Dict, Any, List, Callable, Type, TypeVar, Tuple
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod

T = TypeVar('T')

@dataclass
class Npc_Info:
   npc_id: str
   npc_name: str
   loc_id: str
   loc_name: str
   last_interaction: int
   image_uuid: str

@dataclass
class Inventory_Item:
   item_id: str
   name: str
   desc: str
   last_seen: int
   stackable: bool
   count: int = -1

class Game:
   events: List[Event]
   new_events: int = 0

   def __init__(self, events:Optional[List[Event]]=None, new_events:int=0):
      self.events = [] if events is None else events
      self.new_events = new_events

   def copy(self, reset_event_count:bool=False) -> 'Game':
      return Game(self.events.copy(), 0 if reset_event_count else self.new_events)

   def to_json(self) -> List[Dict[str,Any]]:
      data: List[Dict[str,Any]] = []
      for event in self.events:
         entry: Dict[str,Any] = { "cls": event.__class__.__name__ }
         entry.update(asdict(event))
         data.append(entry)
      return data

   @staticmethod
   def from_json(data:List[Dict]) -> 'Game':
      assert isinstance(data, list) and all(isinstance(e, dict) for e in data)
      events: List[Event] = []
      for event_data in data:
         event_data = event_data.copy()
         event_name = event_data.pop("cls", None)
         assert event_name is not None, f"could not find cls in data: {event_data}"
         event_cls = E.event_dictionary.get(event_name, None)
         assert event_cls is not None, f"could not find event with name '{event_name}' in dictionary"
         events.append(event_cls(**event_data))
      return Game(events)

   def add_event(self, event:Event) -> None:
      event.clean()
      self.events.append(event)
      self.new_events += 1

   def reset_event_count(self) -> 'Game':
      self.new_events = 0
      return self

   def get_npc_name(self, npc_id:str) -> str:
      options = []
      for event in self.events:
         if isinstance(event, E.Create_Npc):
            if event.npc_id == npc_id:
               return f"{event.first_name} {event.last_name}"
            options.append(event.npc_id)
      raise ValueError(f"Failed to find NPC with ID '{npc_id}', options were {options}")

   def get_loc_name(self, loc_id:str) -> str:
      options = []
      for event in self.events:
         if isinstance(event, E.Create_Location):
            if event.loc_id == loc_id:
               return event.name
            options.append(event.loc_id)
      raise ValueError(f"Failed to find Location with ID '{loc_id}', options were {options}")

   def get_loc_image_uuid(self, loc_id:str) -> str:
      options = []
      for event in self.events:
         if isinstance(event, E.Create_Location):
            if event.loc_id == loc_id:
               return event.image_uuid
            options.append(event.loc_id)
      raise ValueError(f"Failed to find Location with ID '{loc_id}', options were {options}")

   def get_quest_name(self, quest_id:str) -> str:
      options = []
      for event in self.events:
         if isinstance(event, E.Start_Quest):
            if event.quest_id == quest_id:
               return event.name
            options.append(event.quest_id)
      raise ValueError(f"Failed to find Quest with ID '{quest_id}', options were {options}")
   
   def get_active_quests(self) -> List[E.Start_Quest]:
      quests: List[E.Start_Quest] = []
      completed = set()
      for event in reversed(self.events):
         if isinstance(event, E.End_Quest):
            completed.add(event.quest_id)
         elif isinstance(event, E.Start_Quest) and event.quest_id not in completed:
            quests.insert(0, event)
      return quests

   def get_item_name(self, item_id:str) -> str:
      options = []
      for event in self.events:
         if isinstance(event, (E.Give_Player_Unique_Item, E.Give_Player_Stackable_Items)):
            if event.item_id == item_id:
               return event.name
            options.append(event.item_id)
      raise ValueError(f"Failed to find Quest with ID '{item_id}', options were {options}")

   def get_inventory_items(self) -> List[Inventory_Item]:
      inventory_items: Dict[str,Inventory_Item] = {}
      seen_items = set()

      for i, event in enumerate(reversed(self.events)):
         if isinstance(event, E.Remove_Player_Unique_Item) and event.item_id not in seen_items:
            seen_items.add(event.item_id)
         elif isinstance(event, E.Give_Player_Unique_Item) and event.item_id not in seen_items:
            inventory_items[event.item_id] = Inventory_Item(event.item_id, event.name, event.desc, len(self.events)-i-1, False)
            seen_items.add(event.item_id)
      
      for i, event in enumerate(self.events):
         if isinstance(event, E.Give_Player_Stackable_Items):
            item = inventory_items.get(event.item_id)
            if item is None:
               item = Inventory_Item(event.item_id, event.name, event.desc, i, True, 0)
               inventory_items[event.item_id] = item
            item.count += event.count
         elif isinstance(event, E.Remove_Player_Stackable_Items):
            inventory_items[event.item_id].count -= event.count

      return sorted(list(inventory_items.values()), key=lambda a: a.last_seen, reverse=True)

   def get_curr_loc_id(self) -> str:
      for event in reversed(self.events):
         if isinstance(event, E.Move_Player_To):
            return event.loc_id
         if isinstance(event, E.Create_Location) and event.automove_player_to:
            return event.loc_id
      raise RuntimeError(f"Failed to find a player move event")

   def player_knows_about(self, loc_id:str) -> bool:
      for event in reversed(self.events):
         if isinstance(event, E.Move_Player_To) and event.loc_id == loc_id:
            return True
         elif isinstance(event, E.Create_Location) and event.loc_id == loc_id:
            return event.tell_player or event.automove_player_to
      raise RuntimeError(f"Failed to find a creation event for location with ID '{loc_id}'")

   def get_npc_infos(self) -> List[Npc_Info]:
      loc_id_to_name: Dict[str,str] = {}
      npc_infos: Dict[str,Npc_Info] = {}
      curr_loc_id = None

      INTERACT_EVENT_MAP: Dict[Type[Event],List[str]] = {
         E.Speak_Player_to_Npc: ["npc_id"],
         E.Speak_Npc_to_Player: ["npc_id"],
         E.Speak_Npc_to_Npc: ["from_npc_id", "to_npc_id"],
      }

      for i, event in enumerate(self.events):
         if isinstance(event, E.Create_Location):
            loc_id_to_name[event.loc_id] = event.name
            if event.automove_player_to:
               curr_loc_id = event.loc_id
         elif isinstance(event, E.Move_Player_To):
            curr_loc_id = event.loc_id
         elif isinstance(event, E.Create_Npc):
            assert curr_loc_id is not None, f"Found a create NPC event {event} before a location was established"
            loc_name = loc_id_to_name.get(curr_loc_id, None)
            assert loc_name is not None, f"Failed to find loc_name for loc_id '{curr_loc_id}' referenced by {event}"
            npc_infos[event.npc_id] = Npc_Info(event.npc_id, f"{event.first_name} {event.last_name}", event.start_loc_id, loc_name, i, event.image_uuid)
         elif isinstance(event, E.Move_Npc):
            npc_infos[event.npc_id].loc_id = event.loc_id
         elif isinstance(event, tuple(INTERACT_EVENT_MAP.keys())):
            attrs = INTERACT_EVENT_MAP[type(event)]
            for attr in attrs:
               npc_id = getattr(event, attr)
               npc_info = npc_infos.get(npc_id, None)
               assert npc_info is not None, f"Failed to find npc_info with npc_id '{npc_id}' referenced by {event}"
               npc_info.last_interaction = i
         elif isinstance(event, E.Kill_Npc):
            npc_infos.pop(event.npc_id)

      return list(npc_infos.values())


class Game_Processor(ABC):
   @abstractmethod
   def process_game(self, game:Game, other_proc:Game_Processor) -> Optional[Game]:
      """
      Main processing turn, returns back the modified game state.

      Can pass a work-in-progress game state to the other_proc using other_proc.peek_game().
      """
      pass

   def peek_game(self, game:Game) -> None:
      """
      Called by the other processor to let this one know what is happening with the game state.

      Since it's called directly by the other processor this function needs to be non-blocking.
      """
      pass
