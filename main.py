from common import State, Event, logger
from prompts import Template, intro, overview_prompt, quests_prompt, mega_prompts
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





#########################
### Func Registration ###
#########################

# Town
Function_Map.register(
   Function(
      Game.create_location, "create_new_town", "Creates a new town location that the player can travel to in the future, cannot be interacted with now",
      Parameter("town_name", str, "the name of the town, a proper noun, make sure to pick something unique and catchy, should be 1 or 2 words long"),
      Parameter("backstory", str, "a quick description of what kind of town this is, what kind of people inhabit it, the mood and atmosphere, the general vibe and purpose of this town"),
      Parameter("description", str, "the physical description of what a person would see when first entering this town, make sure to include a comma-seperated list of visual elements such that this string can be passed directly to a txt2img AI model"),
   ),
   State.TOWN_IDLE, State.ON_THE_MOVE,
)
Function_Map.register(
   Function( # FIXME: func
      lambda x: x, "arrive_at_town", f"Arrives at the specified town transitioning to the {State.TOWN_IDLE.value} state, the town must already exist before calling this",
      Parameter("town_name", str, "name of the town to arrive at"),
   ),
   State.ON_THE_MOVE,
)
Function_Map.register(
   Function( # FIXME: func
      lambda x: x, "leave_town", f"Leaves the current town transitioning to the {State.ON_THE_MOVE.value} state, only call if the player wants to",
   ),
   State.TOWN_IDLE,
)

Function_Map.register(
   Function(
      Game.describe_environment, "describe_surroundings", "Provides the player with a description of a specific part of the environment",
      Parameter("description", str, "the text description, will be shown directly to the plater pre-formatted, provide ONLY the description text content and nothing else"),
   ),
   State.TOWN_IDLE,
)

# NPC Characters
Function_Map.register(
   Function(
      Game.create_npc, "create_new_npc", "Creates a new NPC, should only be called if the NPC doesn't already exist",
      Parameter("name", str, "the name of the NPC, should be a proper noun"),
      Parameter("background", str, "the background of the character, like their profession and/or personality"),
      Parameter("physical_description", str, "what the character physically looks like, format as a comma-seperated list of physical attributes such that this parameter can be passed directly to a txt2img AI model")
   ),
   State.TOWN_IDLE,
)
Function_Map.register(
   Function(
      Game.respond_as_npc, "speak_npc_to_player", "Initiates a response to the player",
      Parameter("response", str, "the text response, will be shown directly to the player pre-formatted, provide ONLY the response text content and nothing else"),
   ),
   State.TOWN_TALK,
)
Function_Map.register(
   Function(
      Game.talk_to_npc, "start_conversation", f"Starts a conversation between the player and a specified NPC",
      Parameter("npc_name", str, "the name of the NPC to start a conversation with"),
   ),
   State.TOWN_IDLE,
)

# Quests
Function_Map.register(
   Function(
      Game.add_quest, "add_quest", "Adds a new quest for the player to complete",
      Parameter("description", str, "the text contents of what the quest objective is, should be atleast 1 sentence long, will be shown directly to the player"),
      Parameter("name", str, "the name of this quest, should be a short descriptor that can be used to reference to this quest later, will be shown directly to the player"),
   ),
   State.TOWN_IDLE, State.TOWN_TALK, State.ON_THE_MOVE,
)
Function_Map.register(
   Function(
      Game.complete_quest, "complete_quest", "Marks the specified quest as completed, make sure to only call once the player has actually completed the quest",
      Parameter("name", str, "the name of the quest that has been completed"),
   ),
   State.TOWN_IDLE, State.TOWN_TALK, State.ON_THE_MOVE,
)

# # NPC
# Function_Map.register(
#    Function(
#       Game.create_npc, "create_npc", "Creates a new NPC that the player could interact with",
#       Parameter("name",str), Parameter("character_background",str), Parameter("physical_description",str)
#    ),
#    State.LOCATION_IDLE, State.LOCATION_TALK
# )
# Function_Map.register(
#    Function(
#       Game.respond_as_npc, "speak_npc_to_player", "Responds to the player through the NPC they are currently talking with, do not add any prefixes just the raw text the player should say",
#       Parameter("response_text",str)
#    ),
#    State.LOCATION_TALK
# )





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
      stop=["</call", "<|end_of_text|>", "<|im_end|>"],
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

   return resp.split("<")[0].strip()

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


def get_prompt_from_game_state(game:Game) -> Tuple[str,bool,State]:
   current_state = game.get_current_state()

   if current_state == State.INITIALIZING:
      assert False
      # template = Template(intro, Function_Map.render(current_state), state_prompts[current_state])
      # # prompt = template.render()

      # return template.render(), False
      # # game = update_from_prompt(prompt, game)
      # # last_location = game.get_last_event(E.Create_Location_Event).name
      # # game.events.append(E.Move_To_Location_Event(last_location))

   elif current_state == State.LOCATION_IDLE:
      assert False
      # current_location = game.get_last_event(E.Move_To_Location_Event).location_name
      # player_input = ""
      # while not player_input:
      #    player_input = input(f"You are currently in {current_location}, what would you like to do?\n").strip()
      
      # template = Template(intro, overview_prompt, quests_prompt, Function_Map.render(current_state), state_prompts[current_state])
      # template["OVERVIEW"] = game.get_overview()
      # template["QUESTS"] = "".join(f'"{e.quest_name}": {e.quest_description}\n' for e in game.get_active_quests())
      # template["PLAYER_INPUT"] = player_input
      # # prompt = template.render()
      # return template.render(), False

      # # game = update_from_prompt(prompt, game)

   elif current_state == State.LOCATION_TALK:
      speak_target = game.get_last_event(E.Start_Conversation_Event).character_name
      conv_history = game.get_conversation_history(speak_target)
      if len(conv_history) > 0 and conv_history[-1].is_player_speaking:
         # prompt AI for response
         # template = Template(intro, overview_prompt, quests_prompt, Function_Map.render(current_state), state_prompts[current_state])
         template = Template(mega_prompts[current_state])
         template["OVERVIEW"] = game.get_overview()
         # template["API"] = Function_Map.render(current_state, lambda f: f.render_short())
         template["QUESTS"] = "".join(f'"{e.quest_name}": {e.quest_description}\n' for e in game.get_active_quests())
         template["NPC_NAME"] = speak_target
         template["NPC_DESCRIPTION"] = game.get_last_event(E.Create_Character_Event, limit_fnx=(lambda e: e.character_name == speak_target)).description
         template["CONVERSATION"] = "".join(e.render()+"\n" for e in conv_history)
         # prompt = template.render()
         return template.render(), False, current_state

         # game = update_from_prompt(prompt, game)
      else:
         # prompt player for response
         return "How to respond? ", True, current_state
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
