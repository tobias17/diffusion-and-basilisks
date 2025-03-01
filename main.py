from common import logger, LOG_FORMAT, Save_Data
import events as E
from game import Game
from user_controller import User_Controller, Peek_Terminal_Input
from backends.ai_backend import AI_Backend

import logging, os, json, threading
import shutil

# TODO
# - Make action list scroll as to not crash the game
# - Add events for NPCs to move around
# - Add AI query events
# - Add more user screens to look at game state
# - Scrollbar in events list (and others) ?
# - Only let NPCs speak if they are in current location


def game_loop(init_game:Game, game_dirpath:str):
   kill_event = threading.Event()

   try:
      ai_backend = AI_Backend(kill_event)
      user_controller = User_Controller(kill_event)

      # Main game loop
      while not kill_event.is_set():
         logger.info("Requesting user to advance game state")
         user_game = user_controller.process_game(init_game, ai_backend)
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
      kill_event.set()
      raise


if __name__ == "__main__":
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

   with Peek_Terminal_Input():
      game_loop(game.reset_event_count(), game_path)

   logger.info("Game exited cleanly")
