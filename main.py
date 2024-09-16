from common import State, logger, LOG_FORMAT
from prompts import Template, make_intro_prompt
from evolver import Prompt_Evolver, Micro_State
import events as E
from game import Game

from typing import Tuple, Callable, Optional, List, Dict
import logging, os, datetime, json
from openai import OpenAI

def get_prompt_from_game_state(game:Game) -> Tuple[str,State]:
   current_state = game.get_current_state()
   template = Template(make_intro_prompt(current_state))
   template["OVERVIEW"] = game.get_overview()
   template["QUESTS"] = "".join(f'"{e.quest_name}": {e.quest_description}\n' for e in game.get_active_quests())

   if current_state == State.TOWN_IDLE:
      template["PLAYER_INPUT"] = game.get_last_event(E.Player_Input_Event).text + "\n"
      template["CHARACTERS"] = "".join(f"'{e.character_name}': {e.background}\n" for e in game.get_characters())

   elif current_state == State.TOWN_TALK:
      speak_target = game.get_last_event(E.Start_Conversation_Event).character_name
      template["NPC_NAME"] = speak_target
      template["NPC_DESCRIPTION"] = game.get_last_event(E.Create_Character_Event, limit_fnx=(lambda e: e.character_name == speak_target)).description
      template["CONVERSATION"] = "".join(e.render()+"\n" for e in game.get_conversation_history(speak_target))

   elif current_state == State.ON_THE_MOVE:
      template["TRAVEL_GOAL"] = game.get_last_event(E.Begin_Traveling_Event).travel_goal

   else:
      raise ValueError(f"game_loop() does not support {current_state.value} state yet")
   
   return template.render(), current_state

def process_game_state(game:Game, output_from_prompt:Callable[[str],Optional[str]], decision_log:List[Dict]) -> Game:
   delta_game = game.copy()
   prompt, current_state = get_prompt_from_game_state(delta_game)
   decision_log.append({"event":"Got Initial Prompt", "prompt":prompt.split("\n")})
   evolver = Prompt_Evolver(current_state)

   while True:
      if evolver.micro_state == Micro_State.DONE:
         if not evolver.can_loop()[0]:
            break
         evolver.loop()
         prompt, current_state = get_prompt_from_game_state(delta_game)
         decision_log.append({"event":"Looping Evolver", "prompt":prompt.split("\n")})

      output = output_from_prompt(prompt)
      assert output is not None, f"Ran out of outputs before completing evolver"

      ext = evolver.get_extension()
      decision_log.append({"event":"Got Extension", "extension":ext.split("\n"), "micro_state":evolver.micro_state.value})
      ok, msg = evolver.process_output(output)
      if not ok:
         logger.error(msg)
         decision_log.append({"event":"ERROR: Got Back Not-OK Processing Output", "output":output.split("\n"), "message":msg})
      else:
         decision_log.append({"event":"Processed Output OK", "output":output.split("\n"), "micro_state":evolver.micro_state.value})
      if evolver.should_call():
         ok, msg = evolver.call(delta_game)
         if not ok:
            logger.error(msg)
            decision_log.append({"event":"ERROR: Got Back Not-OK Calling Function", "message":msg})
         else:
            decision_log.append({"event":"Called Function OK"})

   return delta_game

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
      stop=["</", "<|"],
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

def game_loop(game:Game, log_dirpath:str):
   decision_log = []
   while True:
      current_state = game.get_current_state()

      if current_state in { State.TOWN_IDLE, State.ON_THE_MOVE }:
         if isinstance(game.events[-1], E.Player_Input_Event):
            decision_log.append({"event":f"Processing {current_state.value} State", "message":"Requesting LLM completion"})
            game = process_game_state(game, make_completion, decision_log)
         else:
            decision_log.append({"event":f"Processing {current_state.value} State", "message":"Requesting player input"})
            print("="*40 + "".join("\n" + e.player() for e in game.events))
            text = ""
            while not text:
               text = input("Response? ").strip()
            decision_log.append({"event":"Got player input", "text":text})
            game.add_event(E.Player_Input_Event(text))

      elif current_state == State.TOWN_TALK:
         speak_target = game.get_last_event(E.Start_Conversation_Event).character_name
         conv_history = game.get_conversation_history(speak_target)
         if len(conv_history) == 0 or conv_history[-1].is_player_speaking:
            decision_log.append({"event":f"Processing {current_state.value} State", "message":"Requesting LLM completion"})
            game = process_game_state(game, make_completion, decision_log)
         else:
            decision_log.append({"event":f"Processing {current_state.value} State", "message":"Requesting player response"})
            print("="*40 + "".join("\n" + c.player() for c in conv_history))
            text = ""
            while not text:
               text = input("How do you respond or [leave]? ").strip()
            if text.lower() == "leave":
               decision_log.append({"event":"User chose to end conversation"})
               game.add_event(E.End_Converstation_Event())
            else:
               decision_log.append({"event":"Got player response", "text":text})
               decision_log.append(E.Speak_Event(speak_target, True, text))

      else:
         raise ValueError(f"game_loop() does not support {current_state} state yet")

      with open(f"{log_dirpath}/decision_log.json", "w") as f: json.dump(decision_log,   f, indent="\t")
      with open(f"{log_dirpath}/game.json",         "w") as f: json.dump(game.to_json(), f, indent="\t")

if __name__ == "__main__":
   FOLDER_DIR = datetime.datetime.now().strftime("logs/game/%m-%d-%Y_%H-%M-%S")
   if not os.path.exists(FOLDER_DIR):
      os.makedirs(FOLDER_DIR)
   json_log = f"{FOLDER_DIR}/prompts.json"

   file = logging.FileHandler(f"{FOLDER_DIR}/debug.log")
   file.setLevel(logging.DEBUG)
   file.setFormatter(LOG_FORMAT)
   logger.addHandler(file)

   game = Game()
   game.add_event(E.Create_New_Town_Event("Whisperwind Village", "a small village nestled between two large hills with a quaint main street lined with shops and houses", ""))
   game.add_event(E.Arrive_At_Town_Event("Whisperwind Village"))
   game_loop(game, FOLDER_DIR)
