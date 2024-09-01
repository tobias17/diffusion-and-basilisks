from main import Game, get_prompt_from_game_state, make_completion, Template, error_in_function_calls, need_more_function_calls
import json
from typing import List

MAX_LOOPS = 3
def update_from_prompt(prompt:str, game:Game):
   loops = 0

   while True:
      if loops >= MAX_LOOPS:
         return
      loops += 1

      resp = make_completion(prompt)
      print("="*120 + "\n")
      print(f"output: <|{resp}|>\n")

      event_count = 0
      processed_lines: List[str] = []
      delta_game = game.copy()
      for line in resp.split("\n"):
         processed_lines.append(line)

         ok, err = delta_game.process_line(line)

         if ok:
            event_count += 1
         else:
            template = Template(prompt + error_in_function_calls)
            template["AI_RESPONSE"] = resp
            template["OUTPUT"] = "".join(f">>> {l}\n" for l in processed_lines) + err
            prompt = template.render()
            break
      else:
         if event_count > 0:
            return
         template = Template(prompt + need_more_function_calls)
         template["AI_RESPONSE"] = resp
         template["SYSTEM_RESPONSE"] = "Make sure to call atleast 1 function before ending the call block"
         prompt = template.render()

def inject():
   with open("inputs/events_1.json", "r") as f:
      data = json.load(f)
   game = Game.from_json(data)
   
   prompt, from_player = get_prompt_from_game_state(game)
   assert not from_player
   print(prompt)

   update_from_prompt(prompt, game)

if __name__ == "__main__":
   inject()
