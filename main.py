from common import logger, LOG_FORMAT, Save_Data
import events as E
from game import Game
from user_controller import User_Controller, Peek_Terminal_Input
from backends.ai_backend import AI_Backend
from pathlib import Path

import logging, os, json, threading, traceback, argparse
from typing import Dict


def configure_game_root(game_root:str):
   Save_Data.config(game_root)
   Save_Data.get_and_make(Save_Data.logs_dirpath)
   Save_Data.get_and_make(Save_Data.images_dirpath)
   logger.setLevel(logging.DEBUG)
   file = logging.FileHandler(Save_Data.get_and_make(Save_Data.logs_dirpath, "debug.log", is_file=True))
   file.setLevel(logging.DEBUG)
   file.setFormatter(LOG_FORMAT)
   logger.addHandler(file)


def game_loop(config:Dict, save_root:str):
   kill_event = threading.Event()

   backend_config = config.get("backend")
   assert backend_config is not None, f"Config file did not contain a backend entry, required"
   ai_backend = AI_Backend(kill_event, backend_config)

   GAME_FILENAME = "game.json"
   if not os.path.exists(save_root):
      os.makedirs(save_root)
   filenames = [f for f in os.listdir(save_root) if os.path.exists(os.path.join(save_root, f, GAME_FILENAME))]
   saves = sorted(filenames, key=lambda p: os.path.getmtime(os.path.join(save_root, p, GAME_FILENAME)), reverse=True)

   with Peek_Terminal_Input():
      try:
         user_controller = User_Controller(kill_event, saves)
         game_name, is_new_game = user_controller.wait_for_save_selection()
         if kill_event.is_set():
            return
         configure_game_root(os.path.join(save_root, game_name))
         game_dirpath = Save_Data.get_and_make(GAME_FILENAME, is_file=True)

         # Either create a new game or load an existing one
         if is_new_game:
            init_game = Game()
            init_game.add_event(E.Give_Player_Unique_Item("steel_sword", "Steel Sword", "a long and heft sword made of steel, great for hitting things with"))
            init_game.add_event(E.Give_Player_Stackable_Items("gold_coins", "Gold Coins", 50, "coins made of gold, perhaps they could be traded for goods and services"))
            init_game.add_event(E.Create_Location("iosla_town_square", "Iosla Town Square", "gigantic oak tree, golden leaves, ancient, gnarled, massive spreading branches, in a country town square", True, True))
            init_game.add_event(E.Narrate("You arrive at the town of Iosla, a charming country farming town featuring a prominent ancient gnarled oak tree with golden leaves. You currently stand in the town square in front of the tree."))
            for event in init_game.events:
               prompt = event.image_prompt()
               if prompt:
                  ai_backend.generate_queue.put(prompt)
                  ai_backend.wait_for_uuid(prompt.uuid)
            game_json = init_game.to_json()
            with open(game_dirpath, "w") as f:
               json.dump(game_json, f, indent="\t")
         else:
            with open(game_dirpath) as f:
               init_game = Game.from_json(json.load(f))

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
            ai_backend.can_peek_text = False
            ai_game = ai_backend.process_game(user_game, user_controller)
            ai_backend.can_peek_text = True
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

   saves_root = os.path.join(os.path.dirname(__file__), "saves")
   game_loop(config_data, saves_root)

   logger.info("Game exited cleanly")
