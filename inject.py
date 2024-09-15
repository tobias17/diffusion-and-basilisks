from common import logger
from main import process_game_state
from game import Game

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
            def output_from_prompt(_):
               if len(outputs) == 0:
                  return None
               return outputs.pop(0)
            event_log.append({"break":"="*120, "event":"Starting New Session", "name":key})
            process_game_state(game, output_from_prompt, event_log)
            output = output_from_prompt("")
            if output is not None:
               logger.error("Still had output after processing game state")
               event_log.append({"event":"ERROR: Unhandled Output Remaining", "output":output})
         except Exception as ex:
            _, _, exc_tb = sys.exc_info()
            logger.error(str(ex))
            event_log.append({"event":"ERROR: Unhandled Exception", "error":f"{ex} ({os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno})"})

      with open(os.path.join(FOLDER_DIR, f"{test_name}_log.json"), "w") as f:
         json.dump(event_log, f, indent="\t")

if __name__ == "__main__":
   inject()
