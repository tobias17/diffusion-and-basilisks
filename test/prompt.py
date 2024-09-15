from common import logger
from main import process_game_state, make_completion
from game import Game

import json, os, sys, datetime

ITERATIONS = 5

def prompt():
   names_to_test = ["town_talk", "town_idle"]

   for test_name in names_to_test:
      with open(f"test/inputs/{test_name}_events.json", "r") as f:
         data = json.load(f)
      game = Game.from_json(data)

      FOLDER_DIR = datetime.datetime.now().strftime("logs/prompt/%m-%d-%Y_%H-%M-%S")
      if not os.path.exists(FOLDER_DIR):
         os.makedirs(FOLDER_DIR)

      event_log = []
      for i in range(ITERATIONS):
         key = f"Iteration_{i+1}"
         try:
            event_log.append({"break":"="*120, "event":"Starting New Session", "name":key})
            process_game_state(game, make_completion, event_log)
         except Exception as ex:
            _, _, exc_tb = sys.exc_info()
            logger.error(str(ex))
            event_log.append({"event":"ERROR: Unhandled Exception", "error":f"{ex} ({os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno})"})

      with open(os.path.join(FOLDER_DIR, f"{test_name}_log.json"), "w") as f:
         json.dump(event_log, f, indent="\t")

if __name__ == "__main__":
   prompt()
