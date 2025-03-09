from common import logger, LOG_FORMAT, Save_Data
import events as _ # intentionally unused, for import ordering
from game import Game
from user_controller import User_Controller, Peek_Terminal_Input
from backends.ai_backend import AI_Backend

import logging, os, json, threading, traceback, shutil, argparse
from typing import Dict


def game_loop(init_game:Game, game_dirpath:str, config:Dict):
   kill_event = threading.Event()
   
   backend_config = config.get("backend")
   assert backend_config is not None, f"Config file did not contain a backend entry, required"
   ai_backend = AI_Backend(kill_event, backend_config)
   user_controller = User_Controller(kill_event)

   with Peek_Terminal_Input():
      try:
         # Main game loop
         while not kill_event.is_set():
            logger.info("Requesting user to advance game state")
            user_game = user_controller.process_game(init_game.copy(), ai_backend)
            if kill_event.is_set():
               return
            if user_game is None:
               logger.error(f"Somehow got back None game from user_controller")
               kill_event.set()
               return

            logger.info("Requesting AI to advance game state")
            ai_game = ai_backend.process_game(user_game, user_controller)
            if kill_event.is_set():
               return
            if ai_game is None:
               logger.error(f"Got back None game from AI backend, reverting game state")
            else:
               init_game = ai_game
               game_json = ai_game.to_json()
               with open(game_dirpath, "w") as f:
                  json.dump(game_json, f, indent="\t")

      except Exception as ex:
         logger.fatal(f"Got exception in game_loop(): {ex}")
         for line in traceback.format_exc().split("\n"):
            logger.error(line)
         kill_event.set()
         raise


if __name__ == "__main__":
   parser = argparse.ArgumentParser(prog="Diffusion and Basilisks")
   parser.add_argument('config', type=str, help='Path to config json file')
   args = parser.parse_args()

   config_filepath = os.path.abspath(args.config)
   assert os.path.exists(config_filepath), f"Could not find config file, searched for {config_filepath}"
   with open(config_filepath) as f:
      config_data = json.load(f)

   Save_Data.config("saves/demo")
   if not os.path.exists(Save_Data.root):
      shutil.copytree("saves/template", Save_Data.root)

   file = logging.FileHandler(Save_Data.get_and_make(Save_Data.logs_dirpath, "debug.log", is_file=True))
   file.setLevel(logging.DEBUG)
   file.setFormatter(LOG_FORMAT)
   logger.addHandler(file)

   game_path = Save_Data.get_and_make("game.json", is_file=True)
   with open(game_path) as f:
      game = Game.from_json(json.load(f))

   game_loop(game.reset_event_count(), game_path, config_data)

   logger.info("Game exited cleanly")
