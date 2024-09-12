from common import Event, State, logger
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
      current_location = self.get_last_event(E.Move_To_Location_Event).location_name
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


   def create_location(self, location_description:str, location_name:str) -> Tuple[bool,Optional[str]]:
      for event in self.events:
         if isinstance(event, E.Create_Location_Event) and event.name == location_name:
            return False, f"A location with the name '{location_name}' already exists, no need to create another"
      self.events.append(E.Create_Location_Event(location_name, location_description))
      return True, None
   def move_to_location(self, location_name:str) -> Tuple[bool,Optional[str]]:
      existing_locations = []
      for event in reversed(self.events):
         if isinstance(event, E.Move_To_Location_Event) and event.location_name == location_name:
            return False, f"You are already in '{location_name}', moving there is not required"
         if isinstance(event, E.Create_Location_Event):
            if event.name == location_name:
               self.events.append(E.Move_To_Location_Event(location_name))
               return True, None
            existing_locations.append(event.name)
      return False, f"Could not find location with name '{location_name}', existing locations are: {existing_locations}"

   def describe_environment(self, description:str) -> Tuple[bool,Optional[str]]:
      self.events.append(E.Describe_Environment_Event(description, self.get_last_event(E.Move_To_Location_Event).location_name))
      return True, None

   def create_npc(self, name:str, character_background:str, physical_description:str) -> Tuple[bool,Optional[str]]:
      current_location = self.get_last_event(E.Move_To_Location_Event).location_name
      for event in reversed(self.events):
         if isinstance(event, E.Create_Character_Event) and event.location_name == current_location and event.character_name == name:
            return False, f"Character '{name}' already exists, you can interact with them directly without calling `create_npc` again"
      self.events.append(E.Create_Character_Event(name, self.get_last_event(E.Move_To_Location_Event).location_name, character_background, physical_description))
      return True, None
   def talk_to_npc(self, character_name:str, event_description:str) -> Tuple[bool,Optional[str]]:
      existing_characters = []
      current_location = self.get_last_event(E.Move_To_Location_Event).location_name
      for event in reversed(self.events):
         if isinstance(event, E.Create_Character_Event) and event.location_name == current_location:
            if character_name == event.character_name:
               self.events.append(E.Start_Conversation_Event(character_name, event_description))
               return True, None
            existing_characters.append(event.character_name)
      return False, f"Failed to find character named '{character_name}', the current location ({current_location}) has characters with the following names: {existing_characters}"
   def stop_converstation(self) -> Tuple[bool,Optional[str]]:
      self.events.append(E.End_Converstation_Event())
      return True, None
   def respond_as_npc(self, response_text:str) -> Tuple[bool,Optional[str]]:
      self.events.append(E.Speak_Event(self.get_last_event(E.Start_Conversation_Event).character_name, False, response_text))
      return True, None

   def add_quest(self, quest_description:str, quest_name:str) -> Tuple[bool,Optional[str]]:
      for event in reversed(self.events):
         if isinstance(event, E.Quest_Start) and event.quest_name == quest_name:
            return False, f"A quest with the name '{quest_name}' already exists"
      self.events.append(E.Quest_Start(quest_name, quest_description))
      return True, None
   def complete_quest(self, quest_name:str) -> Tuple[bool,Optional[str]]:
      for event in reversed(self.events):
         if isinstance(event, E.Quest_Complete) and event.quest_name == quest_name:
            return False, f"The quest named '{quest_name}' has already been completed"
         if isinstance(event, E.Quest_Start) and event.quest_name == quest_name:
            self.events.append(E.Quest_Complete(quest_name))
            return True, None
      return False, f"Failed to find a quest with the name '{quest_name}'"

   def add_internal_goal(self, goal_description:str, goal_name:str) -> Tuple[bool,Optional[str]]:
      for event in reversed(self.events):
         if isinstance(event, E.Goal_Add) and event.goal_name == goal_name:
            return False, f"An internal goal with the name '{goal_name}' already exists"
      self.events.append(E.Goal_Add(goal_name, goal_description))
      return True, None
   def complete_internal_goal(self, goal_name:str) -> Tuple[bool,Optional[str]]:
      for event in reversed(self.events):
         if isinstance(event, E.Goal_Complete) and event.goal_name == goal_name:
            return False, f"The quest named '{goal_name}' has already been completed"
         if isinstance(event, E.Goal_Add) and event.goal_name == goal_name:
            self.events.append(E.Goal_Complete(goal_name))
            return True, None
      return False, f"Failed to find an internal goal with the name '{goal_name}'"
