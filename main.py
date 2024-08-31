from common import State, Event, logger
from prompts import Template, intro, state_prompts, need_more_function_calls, overview_prompt, error_in_function_calls
from functions import Function_Map, Function, Parameter, parse_function, match_function
import events as E

from typing import List, Optional, Type, TypeVar, Tuple, Callable, Dict, Any
import logging, os, datetime, json
from dataclasses import asdict
from openai import OpenAI

T = TypeVar('T')



########################
###  Game State Obj  ###
########################

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

   def get_overview(self) -> str:
      overview = []
      current_location = self.get_last_event(E.Move_To_Location_Event).location_name
      for event in self.events:
         text = event.system(current_location)
         if text is not None:
            overview.append(text)
      return "\n".join(overview)

   def process_line(self, line:str) -> Tuple[bool,str]:
      out, err = parse_function(line)
      if out is None:
         return False, err
      call, err = match_function(*out, Function_Map.get(self.get_current_state()))
      if call is None:
         return False, err
      ok, err = call(self)
      if not ok:
         return False, err
      return True, ""

   def process_response(self, text:str) -> int:
      logger.debug(f"Processing response:\n<|{text}|>")
      event_count = 0

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
            continue
         event_count += 1
      return event_count


   def create_location(self, location_description:str, location_name:str) -> Tuple[bool,Optional[str]]:
      for event in self.events:
         if isinstance(event, E.Create_Location_Event) and event.name == location_name:
            return False, f"A location with the name '{location_name}' already exists, you do no need to create another"
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



#########################
### Func Registration ###
#########################

# Location
Function_Map.register(
   Function(
      Game.create_location, "create_location", "Create a new Hub with the description and name, make sure the name is some thing catchy that can be put on a sign",
      Parameter("location_description",str), Parameter("location_name",str)
   ),
   State.INITIALIZING, State.LOCATION_IDLE, State.LOCATION_TALK
)
Function_Map.register(
   Function(
      Game.move_to_location, "move_to_location", "Puts the player in the specified location, must be called with the same name passed into `create_location`",
      Parameter("location_name",str)
   ),
   State.LOCATION_IDLE
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
      Game.talk_to_npc, "talk_to_npc", "Begins a talking interation between the player and the specified NPC, the `event_description` is shown to the player to explain how the interaction starts",
      Parameter("character_name",str), Parameter("event_description",str)
   ),
   State.LOCATION_IDLE
)
Function_Map.register(
   Function(
      Game.stop_converstation, "stop_converstation", "Ends the current conversation, allowing other actiosn to be performed in the world, should be the last function called in a block",
   ),
   State.LOCATION_TALK
)
Function_Map.register(
   Function(
      Game.respond_as_npc, "speak_npc_to_player", "Responds to the player through the NPC they are currently talking with, do not add any prefixes just the raw text the player should say",
      Parameter("response_text",str)
   ),
   State.LOCATION_TALK
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
      Game.complete_quest, "complete_quest", "Marks the specified quest as completed",
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
      temperature=0.8,
      max_tokens=256,
      stop=["$$end_", "<|end_of_text|>", "end_calling"],
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
         "prompt":   prompt.strip().split("\n"),
         "response": resp  .strip().split("\n"),
      })
      with open(json_log, "w") as f:
         json.dump(data, f, indent="\t")

   return resp.strip()

MAX_LOOPS = 3
def update_from_prompt(prompt:str, game:Game) -> Game:
   original_prompt = prompt
   loops = 0

   while True:
      if loops >= MAX_LOOPS:
         logger.warning("Reached maximum loops, restarting")
         prompt = original_prompt
         loops = 0
      loops += 1

      resp = make_completion(prompt)
      print(resp + "\n")

      event_count = 0
      processed_lines: List[str] = []
      delta_game = game.copy()
      for line in resp.split("\n"):
         processed_lines.append(line)

         ok, err = delta_game.process_line(line)

         if ok:
            event_count += 1
         else:
            template = Template(prompt + error_in_function_calls)
            template["AI_RESPONSE"] = resp
            template["OUTPUT"] = "".join(f">>> {l}\n" for l in processed_lines) + err
            prompt = template.render()
            break
      else:
         if event_count > 0:
            return delta_game
         template = Template(prompt + need_more_function_calls)
         template["AI_RESPONSE"] = resp
         template["SYSTEM_RESPONSE"] = "Make sure to call atleast 1 function before ending the call block"
         prompt = template.render()


def get_prompt_from_game_state(game:Game) -> Tuple[str,bool]:
   current_state = game.get_current_state()

   if current_state == State.INITIALIZING:
      template = Template(intro, Function_Map.render(current_state), state_prompts[current_state])
      # prompt = template.render()

      return template.render(), False
      # game = update_from_prompt(prompt, game)
      # last_location = game.get_last_event(E.Create_Location_Event).name
      # game.events.append(E.Move_To_Location_Event(last_location))

   elif current_state == State.LOCATION_IDLE:
      current_location = game.get_last_event(E.Move_To_Location_Event).location_name
      player_input = ""
      while not player_input:
         player_input = input(f"You are currently in {current_location}, what would you like to do?\n").strip()
      
      template = Template(intro, overview_prompt, Function_Map.render(current_state), state_prompts[current_state])
      template["OVERVIEW"] = game.get_overview()
      template["PLAYER_INPUT"] = player_input
      # prompt = template.render()
      return template.render(), False

      # game = update_from_prompt(prompt, game)

   elif current_state == State.LOCATION_TALK:
      speak_target = game.get_last_event(E.Start_Conversation_Event).character_name
      conv_history = game.get_conversation_history(speak_target)
      if len(conv_history) > 0 and conv_history[-1].is_player_speaking:
         # prompt AI for response
         template = Template(intro, overview_prompt, Function_Map.render(current_state), state_prompts[current_state])
         template["OVERVIEW"] = game.get_overview()
         template["NPC_NAME"] = speak_target
         template["NPC_DESCRIPTION"] = game.get_last_event(E.Create_Character_Event, limit_fnx=(lambda e: e.character_name == speak_target)).description
         template["CONVERSATION"] = "\n".join(e.render() for e in conv_history)
         # prompt = template.render()
         return template.render(), False

         # game = update_from_prompt(prompt, game)
      else:
         # prompt player for response
         return "How to respond? ", True
         # resp = input("How to respond? ").strip()
         # if resp.lower() == "leave":
         #    game.events.append(E.End_Converstation_Event())
         # else:
         #    game.events.append(E.Speak_Event(speak_target, True, resp))

   else:
      raise ValueError(f"game_loop() does not support {current_state} state yet")


def game_loop(game:Game):
   while True:
      current_state = game.get_current_state()

      if current_state == State.INITIALIZING:
         template = Template(intro, Function_Map.render(current_state), state_prompts[current_state])
         prompt = template.render()

         game = update_from_prompt(prompt, game)
         last_location = game.get_last_event(E.Create_Location_Event).name
         game.events.append(E.Move_To_Location_Event(last_location))

      elif current_state == State.LOCATION_IDLE:
         current_location = game.get_last_event(E.Move_To_Location_Event).location_name
         player_input = ""
         while not player_input:
            player_input = input(f"You are currently in {current_location}, what would you like to do?\n").strip()
         
         template = Template(intro, overview_prompt, Function_Map.render(current_state), state_prompts[current_state])
         template["OVERVIEW"] = game.get_overview()
         template["PLAYER_INPUT"] = player_input
         prompt = template.render()

         game = update_from_prompt(prompt, game)

      elif current_state == State.LOCATION_TALK:
         speak_target = game.get_last_event(E.Start_Conversation_Event).character_name
         conv_history = game.get_conversation_history(speak_target)
         if len(conv_history) > 0 and conv_history[-1].is_player_speaking:
            # prompt AI for response
            template = Template(intro, overview_prompt, Function_Map.render(current_state), state_prompts[current_state])
            template["OVERVIEW"] = game.get_overview()
            template["NPC_NAME"] = speak_target
            template["NPC_DESCRIPTION"] = game.get_last_event(E.Create_Character_Event, limit_fnx=(lambda e: e.character_name == speak_target)).description
            template["CONVERSATION"] = "\n".join(e.render() for e in conv_history)
            prompt = template.render()

            game = update_from_prompt(prompt, game)
         else:
            # prompt player for response
            resp = input("How to respond? ").strip()
            if resp.lower() == "leave":
               game.events.append(E.End_Converstation_Event())
            else:
               game.events.append(E.Speak_Event(speak_target, True, resp))

      else:
         raise ValueError(f"game_loop() does not support {current_state} state yet")
   
      with open(f"{FOLDER_DIR}/events.json", "w") as f:
         json.dump(game.to_json(), f, indent="\t")



def main():
   game = Game()
   game_loop(game)

if __name__ == "__main__":
   FOLDER_DIR = datetime.datetime.now().strftime("logs/%m-%d-%Y_%H-%M-%S")
   if not os.path.exists(FOLDER_DIR):
      os.makedirs(FOLDER_DIR)
   json_log = f"{FOLDER_DIR}/prompts.json"

   logger.setLevel(logging.DEBUG)
   FORMAT = logging.Formatter("%(levelname)s: %(message)s")
   console = logging.StreamHandler()
   console.setLevel(logging.INFO)
   console.setFormatter(FORMAT)
   logger.addHandler(console)
   file = logging.FileHandler(f"{FOLDER_DIR}/debug.log")
   file.setLevel(logging.DEBUG)
   file.setFormatter(FORMAT)
   logger.addHandler(file)
   main()
