from common import State, Event, logger
from prompts import Template, make_intro_prompt
from functions import Function_Map, Function, Parameter, parse_function, match_function
import events as E
from game import Game

from typing import List, Optional, Type, TypeVar, Tuple, Callable, Dict, Any
import logging, os, datetime, json
from dataclasses import asdict
from openai import OpenAI

#########################
### Func Registration ###
#########################

Function_Map.register(
   Function(
      lambda x: x, "do_nothing", "Performs no action, call this if you cannot complete your scratchpad with the available functions",
   ),
   State.TOWN_IDLE, State.TOWN_TALK, State.ON_THE_MOVE, State.EVENT_INIT,
)

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


def get_prompt_from_game_state(game:Game) -> Tuple[str,State]:
   current_state = game.get_current_state()

   prompt = make_intro_prompt(current_state)

   if current_state == State.TOWN_TALK:
      speak_target = game.get_last_event(E.Start_Conversation_Event).character_name
      conv_history = game.get_conversation_history(speak_target)
      # prompt AI for response
      template = Template(prompt)
      template["OVERVIEW"] = game.get_overview()
      template["QUESTS"] = "".join(f'"{e.quest_name}": {e.quest_description}\n' for e in game.get_active_quests())
      template["NPC_NAME"] = speak_target
      template["NPC_DESCRIPTION"] = game.get_last_event(E.Create_Character_Event, limit_fnx=(lambda e: e.character_name == speak_target)).description
      template["CONVERSATION"] = "".join(e.render()+"\n" for e in conv_history)
      return template.render(), current_state

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
