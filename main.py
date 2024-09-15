from common import State, logger, LOG_FORMAT
from prompts import Template, make_intro_prompt
import events as E
from game import Game

from typing import Tuple
import logging, os, datetime, json
from openai import OpenAI



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

   if current_state == State.TOWN_IDLE:
      template = Template(prompt)
      template["OVERVIEW"] = game.get_overview()
      template["QUESTS"] = "".join(f'"{e.quest_name}": {e.quest_description}\n' for e in game.get_active_quests())
      template["PLAYER_INPUT"] = game.get_last_event(E.Player_Input_Event).text + "\n"
      template["CHARACTERS"] = "".join(f"'{e.character_name}': {e.background}\n" for e in game.get_characters())
      return template.render(), current_state

   elif current_state == State.TOWN_TALK:
      speak_target = game.get_last_event(E.Start_Conversation_Event).character_name
      template = Template(prompt)
      template["OVERVIEW"] = game.get_overview()
      template["QUESTS"] = "".join(f'"{e.quest_name}": {e.quest_description}\n' for e in game.get_active_quests())
      template["NPC_NAME"] = speak_target
      template["NPC_DESCRIPTION"] = game.get_last_event(E.Create_Character_Event, limit_fnx=(lambda e: e.character_name == speak_target)).description
      template["CONVERSATION"] = "".join(e.render()+"\n" for e in game.get_conversation_history(speak_target))
      return template.render(), current_state

   else:
      raise ValueError(f"game_loop() does not support {current_state.value} state yet")
   
   raise ValueError(f"[INVALID_STATE] game_loop() did not return when in {current_state.value} state")


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

   file = logging.FileHandler(f"{FOLDER_DIR}/debug.log")
   file.setLevel(logging.DEBUG)
   file.setFormatter(LOG_FORMAT)
   logger.addHandler(file)
   main()
