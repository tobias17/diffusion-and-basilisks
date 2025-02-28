from common import logger, LOG_FORMAT, Save_Data
import events as E
from game import Game
from screen_handler import Screen_Handler, Peek_Terminal_Input
from backends.ai_backend import AI_Backend

import logging, os, json, threading
import shutil


def game_loop(init_game:Game, game_dirpath:str):
   kill_event = threading.Event()
   ai_backend = AI_Backend(kill_event)
   screen_handler = Screen_Handler(kill_event)

   # Main game loop
   while not kill_event.is_set():
      logger.info("Requesting user to advance game state")
      user_game = screen_handler.process_game(init_game, ai_backend)
      if kill_event.is_set():
         return
      if user_game is None:
         logger.error(f"Somehow got back None game from screen_handler")
         kill_event.set()
         return

      logger.info("Requesting AI to advance game state")
      ai_game = ai_backend.process_game(user_game, screen_handler)
      if kill_event.is_set():
         return
      if ai_game is None:
         logger.error(f"Got back None game from AI backend, reverting game state")
      else:
         init_game = ai_game
         game_json = ai_game.to_json()
         with open(game_dirpath, "w") as f:
            json.dump(game_json, f, indent="\t")


if __name__ == "__main__":
   Save_Data.config("saves/demo")
   if not os.path.exists(Save_Data.root):
      shutil.copytree("saves/template", Save_Data.root)

   file = logging.FileHandler(Save_Data.get_and_make(Save_Data.logs_dirpath, "debug.log", is_file=True))
   file.setLevel(logging.DEBUG)
   file.setFormatter(LOG_FORMAT)
   logger.addHandler(file)

   game_path = Save_Data.get_and_make("game.json", is_file=True)
   if os.path.exists(game_path):
      with open(game_path) as f:
         game = Game.from_json(json.load(f))
   else:
      game = Game()
      starting_events = [
         (lambda: E.create_location(game, loc_id="iosla_town_square", name="Iosla", desc="A charming seaside town centered around an ancient gnarled oak tree with massive spreading branches in the town square.")),
         (lambda: E.move_player_to(game, loc_id="iosla_town_square")),
         (lambda: E.player_request_action(game, "What kind of buildings surround me?")),
         (lambda: E.narrate(game, "You look around and see many small houses, with a tavern a little ways down the road.")),
      ]
      for call in starting_events:
         ok, msg = call()
         if not ok:
            raise RuntimeError(f"Error pre-populating game: {msg}")

   with Peek_Terminal_Input():
      game_loop(game.reset_event_count(), game_path)

   logger.info("Game exited cleanly")
