from common import logger
from main import process_game_state
from game import Game

import json, os, sys
from typing import List, Dict

def inject():
   names_to_test = ["town_talk", "town_idle", "on_the_move"]

   for test_name in names_to_test:
      with open(f"test/inputs/{test_name}_events.json", "r") as f:
         data = json.load(f)
      with open(f"test/inputs/{test_name}_injects.json", "r") as f:
         injects: Dict[str,List[str]] = json.load(f)
      game = Game.from_json(data)

      FOLDER_DIR = "test/outputs"
      if not os.path.exists(FOLDER_DIR):
         os.makedirs(FOLDER_DIR)
      
      decision_log = []
      for key, outputs in injects.items():
         try:
            def output_from_prompt(_):
               if len(outputs) == 0:
                  return None
               return outputs.pop(0)
            decision_log.append({"break":"="*120, "event":"Starting New Session", "name":key})
            process_game_state(game, output_from_prompt, decision_log)
            output = output_from_prompt("")
            if output is not None:
               logger.error("Still had output after processing game state")
               decision_log.append({"event":"ERROR: Unhandled Output Remaining", "output":output})
         except Exception as ex:
            _, _, exc_tb = sys.exc_info()
            logger.error(str(ex))
            decision_log.append({"event":"ERROR: Unhandled Exception", "error":f"{ex} ({os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno})"})

      with open(os.path.join(FOLDER_DIR, f"{test_name}_decisions.json"), "w") as f:
         json.dump(decision_log, f, indent="\t")

if __name__ == "__main__":
   inject()
