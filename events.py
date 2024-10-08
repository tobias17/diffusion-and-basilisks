from common import State, Event
from functions import Function_Map, Function, Parameter
from game import Game

from dataclasses import dataclass
from typing import Optional, Tuple, List


# Request Player Input
Function_Map.register(
   Function(
      (lambda _: (True, "")), "get_player_input", "Requests input from the player to progress the story",
   ),
   *[s for s in State]
)


# Player Input
@dataclass
class Player_Input_Event(Event):
   text: str
   def player(self) -> str:
      return f"Your Input: {self.text}"


# Create Town
@dataclass
class Create_New_Town_Event(Event):
   name: str
   backstory: str
   description: str
   def player(self) -> str:
      return f"You discover {self.name}: {self.backstory}"
   def system(self, current_town_name:str) -> Optional[str]:
      return f"A new location is created, '{self.name}', {self.backstory}"
   def clean(self) -> None:
      self.name        = self._fix_name(self.name)
      self.backstory   = self._strip_text(self.backstory)
      self.description = self._strip_text(self.description)
def create_location(self:Game, town_name:str, backstory:str, description:str) -> Tuple[bool,Optional[str]]:
   for event in self.events:
      if isinstance(event, Create_New_Town_Event) and event.name.lower() == town_name.lower():
         return False, f"A location with the name '{town_name}' already exists, no need to create another"
   self.add_event(Create_New_Town_Event(town_name, backstory, description))
   return True, None
Function_Map.register(
   Function(
      create_location, "create_new_town", "Creates a new town location that the player can travel to in the future, will not be interactable immediately after creation",
      Parameter("town_name", str, "the name of the town, a proper noun, make sure to pick something unique and catchy, should be 1 or 2 words long"),
      Parameter("backstory", str, "a quick description of what kind of town this is, what kind of people inhabit it, the mood and atmosphere, the general vibe and purpose of this town"),
      Parameter("description", str, "the physical description of what a person would see when first entering this town, make sure to include a comma-seperated list of visual elements such that this string can be passed directly to a txt2img AI model"),
   ),
   State.TOWN_IDLE, State.ON_THE_MOVE,
)


# Move to Town
@dataclass
class Arrive_At_Town_Event(Event):
   town_name: str
   def implication(self) -> Optional[State]:
      return State.TOWN_IDLE
   def player(self) -> str:
      return f"You arrive at {self.town_name}"
   def system(self, current_town_name:str) -> Optional[str]:
      return f"You move locations to '{self.town_name}'"
   def clean(self) -> None:
      self.town_name = self._fix_name(self.town_name)
def arrive_at_town(self:Game, town_name:str) -> Tuple[bool,Optional[str]]:
   existing_locations: List[str] = []
   for event in reversed(self.events):
      if isinstance(event, Begin_Traveling_Event) and len(existing_locations) == 0:
         return True, None
      if isinstance(event, Arrive_At_Town_Event) and event.town_name == town_name:
         return False, f"You are already in '{town_name}', moving there is not required"
      if isinstance(event, Create_New_Town_Event):
         if event.name == town_name:
            self.add_event(Arrive_At_Town_Event(town_name))
            return True, None
         existing_locations.append(event.name)
   return False, f"Could not find location with name '{town_name}', existing locations are: {existing_locations}"
Function_Map.register(
   Function(
      arrive_at_town, "arrive_at_town", f"Arrives at the specified town transitioning to the {State.TOWN_IDLE.value} state, the town must already exist before calling this",
      Parameter("town_name", str, "name of the town to arrive at"),
   ),
   State.ON_THE_MOVE,
)


# Leave Town
@dataclass
class Begin_Traveling_Event(Event):
   travel_goal: str
   def implication(self) -> Optional[State]:
      return State.ON_THE_MOVE
   def player(self) -> str:
      return f"You leave town and start traveling"
def begin_traveling(self:Game, travel_goal:str):
   self.add_event(Begin_Traveling_Event(travel_goal))
   return True, None
# Function_Map.register(
#    Function(
#       begin_traveling, "leave_town", f"Leaves the current town transitioning to the {State.ON_THE_MOVE.value} state, only call if the player wants to",
#       Parameter("travel_goal", str, "What your intentions are for leaving town, generally this is something like traveling to another town or checking out an event (like exploring a cave)"),
#    ),
#    State.TOWN_IDLE,
# )


# Describe Surroundings
@dataclass
class Describe_Environment_Event(Event):
   description: str
   town_name: str
   def player(self) -> str:
      return self.description
   def system(self, current_town_name:str) -> Optional[str]:
      if self.town_name == current_town_name:
         return f"Described Surroundings in '{self.town_name}': {self.description}"
      return None
   def clean(self) -> None:
      self.description = self._strip_text(self.description)
def describe_environment(self:Game, description:str) -> Tuple[bool,Optional[str]]:
   self.add_event(Describe_Environment_Event(description, self.get_last_event(Arrive_At_Town_Event).town_name))
   return True, None
Function_Map.register(
   Function(
      describe_environment, "describe_surroundings", "Provides the player with a description of a specific part of the environment",
      Parameter("description", str, "the text description, will be shown directly to the player pre-formatted, provide ONLY the description text content and nothing else"),
   ),
   State.TOWN_IDLE,
)


# Create NPC
@dataclass
class Create_Character_Event(Event):
   character_name: str
   town_name: str
   background: str
   description: str
   def render(self) -> str:
      return ""
   def player(self) -> str:
      return f"A new character is created, {self.character_name}, {self.background}"
   def system(self, current_town_name:str) -> Optional[str]:
      if self.town_name == current_town_name:
         return f"A new character is created, '{self.character_name}', {self.background}, {self.description}"
      return None
   def clean(self) -> None:
      self.character_name = self._fix_name(self.character_name)
      self.background = self._strip_text(self.background)
      self.description = self._strip_text(self.description)
def create_npc(self:Game, name:str, character_background:str, physical_description:str) -> Tuple[bool,Optional[str]]:
   current_location = self.get_last_event(Arrive_At_Town_Event).town_name
   for event in reversed(self.events):
      if isinstance(event, Create_Character_Event) and event.town_name == current_location and event.character_name == name:
         return False, f"Character '{name}' already exists, you can interact with them directly without calling `create_npc` again"
   self.add_event(Create_Character_Event(name, self.get_last_event(Arrive_At_Town_Event).town_name, character_background, physical_description))
   return True, None
Function_Map.register(
   Function(
      create_npc, "create_new_npc", "Creates a new NPC, should only be called if the NPC doesn't already exist",
      Parameter("name", str, "the name of the NPC, should be a proper noun"),
      Parameter("background", str, "the background of the character, like their profession and/or personality"),
      Parameter("physical_description", str, "what the character physically looks like, format as a comma-seperated list of physical attributes such that this parameter can be passed directly to a txt2img AI model")
   ),
   State.TOWN_IDLE,
)


# Start Conversation
@dataclass
class Start_Conversation_Event(Event):
   character_name: str
   def implication(self) -> Optional[State]:
      return State.TOWN_TALK
   def player(self) -> str:
      return f"You start talking with {self.character_name}"
def start_conversation(self:Game, npc_name:str) -> Tuple[bool,Optional[str]]:
   existing_characters = []
   current_location = self.get_last_event(Arrive_At_Town_Event).town_name
   for event in reversed(self.events):
      if isinstance(event, Create_Character_Event) and event.town_name == current_location:
         if npc_name == event.character_name:
            self.add_event(Start_Conversation_Event(npc_name))
            return True, None
         existing_characters.append(event.character_name)
   return False, f"Failed to find character named '{npc_name}', the current location ({current_location}) has characters with the following names: {existing_characters}"
Function_Map.register(
   Function(
      start_conversation, "start_conversation", f"Starts a conversation between the player and a specified NPC",
      Parameter("npc_name", str, "the name of the NPC to start a conversation with")
   ),
   State.TOWN_IDLE,
)


# Speak Events
@dataclass
class Speak_Event(Event):
   with_character: str
   is_player_speaking: bool
   text: str
   def player(self) -> str:
      return ("You" if self.is_player_speaking else self.with_character) + f": {self.text}"
   def render(self) -> str:
      cleaned_text = self.text.replace('"', "'")
      return "speak_" + ("player_to_npc" if self.is_player_speaking else "npc_to_player") + f'("{cleaned_text}")'
def respond_as_npc(self:Game, response_text:str) -> Tuple[bool,Optional[str]]:
   self.add_event(Speak_Event(self.get_last_event(Start_Conversation_Event).character_name, False, response_text))
   return True, None
Function_Map.register(
   Function(
      respond_as_npc, "speak_npc_to_player", "Initiates a response to the player",
      Parameter("response", str, "the text response, will be shown directly to the player pre-formatted, provide ONLY the response text content and nothing else"),
   ),
   State.TOWN_TALK,
)


# Stop Conversation
@dataclass
class End_Converstation_Event(Event):
   def implication(self) -> Optional[State]:
      return State.TOWN_IDLE
   def player(self) -> str:
      return f"You end the conversation"
def stop_converstation(self:Game) -> Tuple[bool,Optional[str]]:
   self.add_event(End_Converstation_Event())
   return True, None


# Add Quest
@dataclass
class Quest_Start(Event):
   quest_name: str
   quest_description: str
   def player(self) -> str:
      return f"You gain a new quest, {self.quest_name}, {self.quest_description}"
   def clean(self) -> None:
      self.quest_name = self._fix_name(self.quest_name)
      self.quest_description = self._strip_text(self.quest_description)
def add_quest(self:Game, quest_description:str, quest_name:str) -> Tuple[bool,Optional[str]]:
   for event in reversed(self.events):
      if isinstance(event, Quest_Start) and event.quest_name == quest_name:
         return False, f"A quest with the name '{quest_name}' already exists"
   self.add_event(Quest_Start(quest_name, quest_description))
   return True, None
Function_Map.register(
   Function(
      add_quest, "add_quest", "Adds a new quest for the player to complete",
      Parameter("description", str, "the text contents of what the quest objective is, should be atleast 1 sentence long, will be shown directly to the player"),
      Parameter("name", str, "the name of this quest, should be a short descriptor that can be used to reference to this quest later, will be shown directly to the player"),
   ),
   State.TOWN_IDLE, State.TOWN_TALK, State.ON_THE_MOVE,
)


# Complete Quest
@dataclass
class Quest_Complete(Event):
   quest_name: str
   def player(self) -> str:
      return f"You complete a quest, {self.quest_name}"
def complete_quest(self:Game, quest_name:str) -> Tuple[bool,Optional[str]]:
   for event in reversed(self.events):
      if isinstance(event, Quest_Complete) and event.quest_name == quest_name:
         return False, f"The quest named '{quest_name}' has already been completed"
      if isinstance(event, Quest_Start) and event.quest_name == quest_name:
         self.add_event(Quest_Complete(quest_name))
         return True, None
   return False, f"Failed to find a quest with the name '{quest_name}'"
Function_Map.register(
   Function(
      complete_quest, "complete_quest", "Marks the specified quest as completed, make sure to only call once the player has actually completed the quest",
      Parameter("name", str, "the name of the quest that has been completed"),
   ),
   State.TOWN_IDLE, State.TOWN_TALK, State.ON_THE_MOVE,
)


# Shop Encounter
@dataclass
class Shop_Encounter_Event(Event):
   merchant_name: str
   def implication(self) -> Optional[State]:
      return State.SHOP_ENCOUNTER


# Trap Encounter
@dataclass
class Trap_Encounter_Event(Event):
   trap_description: str
   def implication(self) -> Optional[State]:
      return State.TRAP_ENCOUNTER


# Combat Encounter
@dataclass
class Combat_Encounter_Event(Event):
   enemy_count: int
   def implication(self) -> Optional[State]:
      return State.TRAP_ENCOUNTER


event_dictionary = { n:E for n,E in locals().items() if isinstance(E, type) and issubclass(E, Event) }
