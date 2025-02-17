from __future__ import annotations
from common import Event
import events as E

from typing import List, Optional, Dict, Any, List, Callable, Type, TypeVar, Tuple
from dataclasses import asdict

T = TypeVar('T')

class Game:
   events: List[Event]
   def __init__(self, events:Optional[List[Event]]=None):
      self.events = [] if events is None else events

   def copy(self) -> 'Game':
      return Game(self.events.copy())

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

   def get_npc_name(self, npc_id:str) -> str:
      options = []
      for event in self.events:
         if isinstance(event, E.Create_Npc_Event):
            if event.npc_id == npc_id:
               return event.name
            options.append(event.npc_id)
      raise ValueError(f"Failed to find NPC with ID '{npc_id}', options were {options}")

   def get_loc_name(self, loc_id:str) -> str:
      options = []
      for event in self.events:
         if isinstance(event, E.Create_Location_Event):
            if event.loc_id == loc_id:
               return event.name
            options.append(event.loc_id)
      raise ValueError(f"Failed to find Location with ID '{loc_id}', options were {options}")
