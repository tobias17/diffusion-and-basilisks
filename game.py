from __future__ import annotations
from common import Event, State
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

   def get_current_state(self) -> State:
      for event in reversed(self.events):
         state = event.implication()
         if state is not None:
            return state
      return State.ON_THE_MOVE
   
   def get_last_event(self, target_event:Type[T], limit_fnx:Callable[[T],bool]=(lambda e: True), default=None) -> T:
      for event in reversed(self.events):
         if isinstance(event, target_event) and limit_fnx(event):
            return event
      if default is not None:
         return default
      raise RuntimeError(f"get_last_event() failed to find a {target_event.__name__} in the event list")

   def get_conversation_history(self, character_name:str) -> List[E.Speak_Event]:
      history = []
      for event in self.events:
         if isinstance(event, E.Speak_Event) and event.with_character == character_name:
            history.append(event)
      return history

   def get_overview(self) -> str:
      overview = []
      current_location = self.get_last_event(E.Arrive_At_Town_Event).town_name
      for event in self.events:
         text = event.system(current_location)
         if text is not None:
            overview.append(text+"\n")
      return "".join(overview)

   def get_active_quests(self) -> List[E.Quest_Start]:
      active_quests = []
      completed_quests = set()
      for event in reversed(self.events):
         if isinstance(event, E.Quest_Complete):
            completed_quests.add(event.quest_name)
         elif isinstance(event, E.Quest_Start) and event.quest_name not in completed_quests:
            active_quests.append(event)
      return active_quests

   def get_characters(self) -> List[E.Create_Character_Event]:
      characters = []
      current_location = self.get_last_event(E.Arrive_At_Town_Event).town_name
      for event in reversed(self.events):
         if isinstance(event, E.Create_Character_Event) and event.location_name == current_location:
            characters.append(event)
      return characters
