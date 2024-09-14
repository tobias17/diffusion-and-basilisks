from common import logger
from main import get_prompt_from_game_state
from game import Game
from evolver import Prompt_Evolver, Micro_State

import json, os, sys
from typing import List, Dict

def inject():
   names_to_test = ["town_talk", "town_idle"]

   for test_name in names_to_test:
      with open(f"inputs/{test_name}_events.json", "r") as f:
         data = json.load(f)
      with open(f"inputs/{test_name}_injects.json", "r") as f:
         injects: Dict[str,List[str]] = json.load(f)
      game = Game.from_json(data)

      # FOLDER_DIR = datetime.datetime.now().strftime("logs/%m-%d-%Y_%H-%M-%S")
      FOLDER_DIR = "logs/inject"
      if not os.path.exists(FOLDER_DIR):
         os.makedirs(FOLDER_DIR)
      
      event_log = []
      for key, outputs in injects.items():
         try:
            event_log.append({"break":"="*120, "event":"Starting New Session", "name":key})
            delta_game = game.copy()
            prompt, current_state = get_prompt_from_game_state(delta_game)
            event_log.append({"event":"Got Initial Prompt", "prompt":prompt.split("\n")})
            evolver = Prompt_Evolver(current_state)

            for output in outputs:
               if evolver.micro_state == Micro_State.DONE:
                  evolver.loop()
                  prompt, current_state = get_prompt_from_game_state(delta_game)
                  event_log.append({"event":"Looping Evolver", "prompt":prompt.split("\n")})

               ext = evolver.get_extension()
               event_log.append({"event":"Got Extension", "extension":ext.split("\n"), "micro_state":evolver.micro_state.value})
               ok, msg = evolver.process_output(output)
               if not ok:
                  event_log.append({"event":"Got Back Not-OK Processing Output", "output":output.split("\n"), "message":msg})
               else:
                  event_log.append({"event":"Processed Output OK", "output":output.split("\n"), "micro_state":evolver.micro_state.value})
               if evolver.should_call():
                  ok, msg = evolver.call(delta_game)
                  if not ok:
                     event_log.append({"event":"Got Back Not-OK Calling Function", "message":msg})
                  else:
                     event_log.append({"event":"Called Function OK"})
            if evolver.micro_state == Micro_State.DONE:
               event_log.append({"event":"Ended on DONE State", "scratchpad":evolver.scratchpad.split("\n")})
         except Exception as ex:
            _, _, exc_tb = sys.exc_info()
            logger.error(str(ex))
            event_log.append({"event":"ERROR: Unhandled Exception", "error":f"{ex} ({os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno})"})

      with open(os.path.join(FOLDER_DIR, f"{test_name}_log.json"), "w") as f:
         json.dump(event_log, f, indent="\t")

if __name__ == "__main__":
   inject()
