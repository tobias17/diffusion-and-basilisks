from common import State, Event, logger
from prompts import Template, intro, state_map
from functions import Function_Map, Function, Parameter, parse_function, match_function
import events as E

from typing import List, Optional, Type, TypeVar, Tuple
from openai import OpenAI
import logging, os, datetime

T = TypeVar('T')



########################
###  Game State Obj  ###
########################

class Game:
   events: List[Event]
   def __init__(self):
      self.events = []

   def get_current_state(self) -> State:
      for event in reversed(self.events):
         state = event.implication()
         if state is not None:
            return state
      return State.INITIALIZING
   
   def get_current_location(self) -> E.Create_Location_Event:
      for event in reversed(self.events):
         if isinstance(event, E.Create_Location_Event):
            return event
      raise RuntimeError(f"get_current_location failed to find Create_Location_Event in the event list")

   def process_response(self, text:str):
      logger.debug(f"Processing response:\n<|{text}|>")

      lines = []
      for line in text.split("\n"):
         line = line.strip()
         if not line or line.startswith("#"):
            continue
         lines.append(line)
      
      for line in lines:
         out, msg = parse_function(line)
         if out is None:
            logger.warning(f"Got error parsing function\n\tinput: <|{line}|>\n\tmessage: {msg}")
            continue
         call, msg = match_function(*out, Function_Map.get(self.get_current_state()))
         if call is None:
            logger.warning(f"Got error matching function\n\tinput: <|{line}|>\n\tmessage: {msg}")
            continue
         ok, msg = call(self)
         if not ok:
            logger.warning(f"Got back not-ok when calling function\n\tinput: <|{line}|>\n\tmessage: {msg}")


   def create_location(self, location_description:str, location_name:str) -> Tuple[bool,Optional[str]]:
      self.events.append(E.Create_Location_Event(location_name, location_description))
      return True, None

   def move_to_location(self, location_name:str) -> Tuple[bool,Optional[str]]:
      existing_locations = []
      for event in reversed(self.events):
         if isinstance(event, E.Create_Location_Event):
            if event.name == location_name:
               self.events.append(E.Move_To_Location_Event(location_name))
               return True, None
            existing_locations.append(event.name)
      return False, f"Could not find location with name '{location_name}', existing locations are: {existing_locations}"

   def create_npc(self, name:str, character_background:str, physical_description:str) -> Tuple[bool,Optional[str]]:
      current_location = self.get_current_location()
      for event in reversed(self.events):
         if isinstance(event, E.Create_Character_Event) and event.location_name == current_location and event.character_name == name:
            return False, f"Location '{current_location}' already has a character with the name '{name}'"
      self.events.append(E.Create_Character_Event(name, self.get_current_location().name, character_background, physical_description))
      return True, None

   def talk_to_npc(self, name:str) -> Tuple[bool,Optional[str]]:
      existing_characters = []
      current_location = self.get_current_location()
      for event in reversed(self.events):
         if isinstance(event, E.Create_Character_Event) and event.location_name == current_location:
            if name == event.character_name:
               self.events.append(E.Start_Conversation_Event(name))
               return True, None
            existing_characters.append(event.character_name)
      return False, f"Failed to find character named '{name}', the current location ({current_location}) has characters with the following names: {existing_characters}"



#########################
### Func Registration ###
#########################

Function_Map.register(
   Function(
      Game.create_location, "create_location", "Create a new Hub with the description and name, make sure the name is some thing catchy that can be put on a sign",
      Parameter("location_description",str), Parameter("location_name",str)
   ),
   State.INITIALIZING
)

Function_Map.register(
   Function(
      Game.move_to_location, "move_to_location", "Puts the player in the specified location, must be called with the same name passed into `create_location`",
      Parameter("location_name",str)
   ),
   State.INITIALIZING
)

Function_Map.register(
   Function(
      Game.create_npc, "create_npc", "Creates a new NPC that the player could interact with",
      Parameter("name",str), Parameter("character_background",str), Parameter("physical_description",str)
   ),
   State.LOCATION_IDLE, State.LOCATION_TALK
)



########################
###  Main Game Loop  ###
########################

client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
def make_completion(prompt:str):
   global client

   completion = client.chat.completions.create(
      model="lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF",
      messages=[
         { "role":"system", "content":prompt },
      ],
      temperature=0.7,
      max_tokens=128,
      stop=["$$end_"],
   )

   resp = completion.choices[0].message.content
   assert resp is not None
   return resp.strip()

def game_loop(game:Game):
   while True:
      current_state = game.get_current_state()

      if current_state == State.INITIALIZING:
         template = Template(intro, Function_Map.render(current_state), state_map[current_state])
         prompt = template.render()
         print(prompt)
         
         resp = make_completion(prompt)
         print(resp)
         game.process_response(resp)
      else:
         raise ValueError(f"game_loop() does not support {current_state} state yet")

      input("next loop? ")



def main():
   game = Game()
   game_loop(game)

if __name__ == "__main__":
   logger.setLevel(logging.DEBUG)
   FORMAT = logging.Formatter("%(levelname)s: %(message)s")
   console = logging.StreamHandler()
   console.setLevel(logging.INFO)
   console.setFormatter(FORMAT)
   logger.addHandler(console)
   if not os.path.exists("logs"):
      os.mkdir("logs")
   file = logging.FileHandler(datetime.datetime.now().strftime("logs/%m-%d-%Y_%H-%M-%S.log"))
   file.setLevel(logging.DEBUG)
   file.setFormatter(FORMAT)
   logger.addHandler(file)
   main()
