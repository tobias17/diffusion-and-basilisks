from common import State, Event, logger
from prompts import Template, intro, state_prompts, need_more_function_calls
from functions import Function_Map, Function, Parameter, parse_function, match_function
import events as E

from typing import List, Optional, Type, TypeVar, Tuple, Callable
import logging, os, datetime, json
from openai import OpenAI

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

   def describe_environment(self, description:str) -> Tuple[bool,Optional[str]]:
      self.events.append(E.Describe_Environment_Event(description, self.get_last_event(E.Move_To_Location_Event).location_name))
      return True, None

   def create_npc(self, name:str, character_background:str, physical_description:str) -> Tuple[bool,Optional[str]]:
      current_location = self.get_last_event(E.Move_To_Location_Event)
      for event in reversed(self.events):
         if isinstance(event, E.Create_Character_Event) and event.location_name == current_location and event.character_name == name:
            return False, f"Location '{current_location}' already has a character with the name '{name}'"
      self.events.append(E.Create_Character_Event(name, self.get_last_event(E.Move_To_Location_Event).location_name, character_background, physical_description))
      return True, None
   def talk_to_npc(self, character_name:str) -> Tuple[bool,Optional[str]]:
      existing_characters = []
      current_location = self.get_last_event(E.Move_To_Location_Event)
      for event in reversed(self.events):
         if isinstance(event, E.Create_Character_Event) and event.location_name == current_location:
            if character_name == event.character_name:
               self.events.append(E.Start_Conversation_Event(character_name))
               return True, None
            existing_characters.append(event.character_name)
      return False, f"Failed to find character named '{character_name}', the current location ({current_location}) has characters with the following names: {existing_characters}"

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



#########################
### Func Registration ###
#########################

# Location
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

# System
Function_Map.register(
   Function(
      Game.describe_environment, "describe_environment", "Allows you to describe any part of the environment to the player, generally called after the player requests an action like looking around",
      Parameter("description",str)
   ),
   State.LOCATION_IDLE
)

# NPC
Function_Map.register(
   Function(
      Game.create_npc, "create_npc", "Creates a new NPC that the player could interact with",
      Parameter("name",str), Parameter("character_background",str), Parameter("physical_description",str)
   ),
   State.LOCATION_IDLE, State.LOCATION_TALK
)
Function_Map.register(
   Function(
      Game.talk_to_npc, "talk_to_npc", "Begins a talking interation between the player and the specified NPC",
      Parameter("character_name",str)
   )
)

# Quests
Function_Map.register(
   Function(
      Game.add_quest, "add_quest", "Adds a new quest for the player to complete",
      Parameter("quest_description",str), Parameter("quest_name",str)
   ),
   State.LOCATION_IDLE, State.LOCATION_TALK
)
Function_Map.register(
   Function(
      Game.add_quest, "complete_quest", "Marks the specified quest as completed",
      Parameter("quest_name",str)
   ),
   State.LOCATION_IDLE, State.LOCATION_TALK
)



########################
###  Main Game Loop  ###
########################

json_log = None
client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
def make_completion(prompt:str):
   global client, json_log

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
   resp = resp.strip()

   if json_log is not None:
      if os.path.exists(json_log):
         with open(json_log) as f:
            data = json.load(f)
      else:
         data = { "queries": [] }
      data["queries"].append({
         "prompt": prompt,
         "response": resp,
      })
      with open(json_log, "w") as f:
         json.dump(data, f, indent="\t")

   return resp.strip()

def game_loop(game:Game):
   while True:
      current_state = game.get_current_state()

      if current_state == State.INITIALIZING:
         template = Template(intro, Function_Map.render(current_state), state_prompts[current_state])
         prompt = template.render()
         while True:
            resp = make_completion(prompt)
            print(resp)
            game.process_response(resp)
            if game.get_current_state() != State.INITIALIZING:
               break
            template = Template(prompt + need_more_function_calls)
            template["AI_RESPONSE"] = resp
            template["SYSTEM_RESPONSE"] = "Make sure to call `move_to_location` to navigate to the created location"
            prompt = template.render()

      elif current_state == State.LOCATION_IDLE:
         current_location = game.get_last_event(E.Move_To_Location_Event).location_name
         player_input = ""
         while not player_input:
            player_input = input(f"You are currently in {current_location}, what would you like to do?\n").strip()
         
         template = Template(intro, Function_Map.render(current_state), state_prompts[current_state])
         template["PLAYER_INPUT"] = player_input
         prompt = template.render()

         resp = make_completion(prompt)
         print(resp)
         game.process_response(resp)

      elif current_state == State.LOCATION_TALK:
         speak_target = game.get_last_event(E.Start_Conversation_Event).character_name
         conv_history = game.get_conversation_history(speak_target)
         if conv_history[-1].is_player_speaking:
            # prompt AI for response
            template = Template(intro, Function_Map.render(current_state), state_prompts[current_state])
            template["NPC_NAME"] = speak_target
            template["NPC_DESCRIPTION"] = game.get_last_event(E.Create_Character_Event, limit_fnx=(lambda e: e.character_name == speak_target)).description
            template["CONVERSATION"] = "\n".join(e.render() for e in conv_history)
         else:
            # prompt player for response
            resp = input("How to respond? ").strip()
            if resp.lower() == "leave":
               game.events.append(E.End_Converstation_Event())
            else:
               game.events.append(E.Speak_Event(speak_target, True, resp))

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
   filename = datetime.datetime.now().strftime("logs/%m-%d-%Y_%H-%M-%S")
   json_log = f"{filename}.json"
   file = logging.FileHandler(f"{filename}.log")
   file.setLevel(logging.DEBUG)
   file.setFormatter(FORMAT)
   logger.addHandler(file)
   main()
