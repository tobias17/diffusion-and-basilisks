from main import Game, get_prompt_from_game_state
import json

def inject():
   with open("inputs/events_1.json", "r") as f:
      data = json.load(f)
   game = Game.from_json(data)
   print(game)

if __name__ == "__main__":
   inject()
