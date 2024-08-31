from main import Game, get_prompt_from_game_state
import json

def inject():
   with open("inputs/events_1.json", "r") as f:
      data = json.load(f)
   game = Game.from_json(data)
   
   prompt, from_player = get_prompt_from_game_state(game)
   print(prompt)

if __name__ == "__main__":
   inject()
