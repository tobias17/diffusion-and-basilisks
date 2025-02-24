from __future__ import annotations
from common import Event
import events as E

from typing import List, Optional, Dict, Any, List, Callable, Type, TypeVar, Tuple
from dataclasses import dataclass, asdict

T = TypeVar('T')

@dataclass
class Npc_Info:
   npc_id: str
   npc_name: str
   loc_id: str
   loc_name: str
   last_interaction: int
   image_uuid: str

class Game:
   events: List[Event]
   new_events: int = 0

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
      self.new_events += 1

   def reset_event_count(self) -> 'Game':
      self.new_events = 0
      return self

   def get_npc_name(self, npc_id:str) -> str:
      options = []
      for event in self.events:
         if isinstance(event, E.Create_Npc_Event):
            if event.npc_id == npc_id:
               return f"{event.first_name} {event.last_name}"
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

   def get_loc_image_uuid(self, loc_id:str) -> str:
      options = []
      for event in self.events:
         if isinstance(event, E.Create_Location_Event):
            if event.loc_id == loc_id:
               return event.image_uuid
            options.append(event.loc_id)
      raise ValueError(f"Failed to find Location with ID '{loc_id}', options were {options}")

   def get_quest_name(self, quest_id:str) -> str:
      options = []
      for event in self.events:
         if isinstance(event, E.Start_Quest_Event):
            if event.quest_id == quest_id:
               return event.name
            options.append(event.quest_id)
      raise ValueError(f"Failed to find Quest with ID '{quest_id}', options were {options}")

   def get_active_quests(self) -> List[E.Start_Quest_Event]:
      quests = []
      for event in self.events:
         if isinstance(event, E.Start_Quest_Event):
            quests.append(event)
         elif isinstance(event, E.End_Quest_Event):
            i = 0
            while True:
               if i >= len(quests):
                  break
               if quests[i].quest_id == event.quest_id:
                  quests.pop(i)
               else:
                  i += 1
      return quests

   def get_curr_loc_id(self) -> str:
      for event in reversed(self.events):
         if isinstance(event, E.Move_Player_To_Event):
            return event.loc_id
      raise RuntimeError(f"Failed to find a player move event")

   def get_npc_infos(self) -> List[Npc_Info]:
      loc_id_to_name: Dict[str,str] = {}
      npc_infos: Dict[str,Npc_Info] = {}
      curr_loc_id = None

      INTERACT_EVENT_MAP: Dict[Type[Event],List[str]] = {
         E.Speak_Player_to_Npc_Event: ["npc_id"],
         E.Speak_Npc_to_player: ["npc_id"],
         E.Speak_Npc_to_Npc_Event: ["from_npc_id", "to_npc_id"],
      }

      for i, event in enumerate(self.events):
         if isinstance(event, E.Create_Location_Event):
            loc_id_to_name[event.loc_id] = event.name
         elif isinstance(event, E.Move_Player_To_Event):
            curr_loc_id = event.loc_id
         elif isinstance(event, E.Create_Npc_Event):
            assert curr_loc_id is not None, f"Found a create NPC event {event} before a location was established"
            loc_name = loc_id_to_name.get(curr_loc_id, None)
            assert loc_name is not None, f"Failed to find loc_name for loc_id '{curr_loc_id}' referenced by {event}"
            npc_infos[event.npc_id] = Npc_Info(event.npc_id, f"{event.first_name} {event.last_name}", event.start_loc_id, loc_name, i, event.image_uuid)
         elif isinstance(event, tuple(INTERACT_EVENT_MAP.keys())):
            attrs = INTERACT_EVENT_MAP[type(event)]
            for attr in attrs:
               npc_id = getattr(event, attr)
               npc_info = npc_infos.get(npc_id, None)
               assert npc_info is not None, f"Failed to find npc_info with npc_id '{npc_id}' referenced by {event}"
               npc_info.last_interaction = i

      return list(npc_infos.values())
