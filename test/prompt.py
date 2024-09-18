from common import logger, exc_loc_str
from main import process_game_state, make_completion
from game import Game

import json, os, datetime, argparse

def prompt(iterations:int, folder_dirpath:str):

   # names_to_test = ["town_talk", "town_idle", "on_the_move"]
   names_to_test = ["town_talk"]

   for test_name in names_to_test:
      with open(f"test/inputs/{test_name}_events.json", "r") as f:
         data = json.load(f)
      game = Game.from_json(data)

      event_log = []
      for i in range(iterations):
         key = f"Iteration_{i+1}"
         try:
            event_log.append({"break":"="*120, "event":"Starting New Session", "name":key})
            process_game_state(game, make_completion, event_log)
         except Exception as ex:
            logger.error(str(ex))
            event_log.append({"event":"ERROR: Unhandled Exception", "error":f"{ex} ({exc_loc_str()})"})

      with open(os.path.join(folder_dirpath, f"{test_name}_log.json"), "w") as f:
         json.dump(event_log, f, indent="\t")

if __name__ == "__main__":
   parser = argparse.ArgumentParser()
   parser.add_argument('-i', '--iterations', type=int, default=5)
   args = parser.parse_args()

   FOLDER_DIR = datetime.datetime.now().strftime("logs/prompt/%m-%d-%Y_%H-%M-%S")
   if not os.path.exists(FOLDER_DIR):
      os.makedirs(FOLDER_DIR)
   import main
   main.json_log = os.path.join(FOLDER_DIR, "completions.json")

   prompt(args.iterations, FOLDER_DIR)
