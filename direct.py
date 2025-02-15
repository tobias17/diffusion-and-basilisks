import requests, json

STARTING_MESSAGES = [
   {
"role": "system", "content": """
You are a helpful assistant who will play the role of Dungeon Master in a high fantasy role playing game. You will advance the game state via function calls.

While this looks and functions like python, you only have access to the functions themselves and no higher-level programming functions. The following is the API you will have access to:
```
GAME.create_town(name:str) -> Town: pass
GAME.make_new_background(id:str, desc:str) -> Background: pass
GAME.get_background(id:str) -> Background: pass
PLAYER.move_to(town:Town, background:Background) -> None: pass
GAME.make_new_npc(name:str, desc:str) -> Character: pass
GAME.get_npc(name:str) -> Character: pass
Character.speak_to_player(text) -> None: pass
PLAYER.speak_to_npc(npc:Character, text:str) -> None: pass
NARRATOR.speak(text:str) -> None: pass
```

Start off by create a new town and moving the player to it. You will then wait for the user to input what they would like to do.

Make sure to only advance the game by what is necessary to satisfy the user's request.
""".strip()
   }, {
"role": "assistant", "content": """
iosla = GAME.create_town(name="Iosla")
bg = GAME.make_new_background(id="iosla.town_center", desc="A charming seaside town centered around an ancient gnarled oak tree with massive spreading branches in the town square.")
PLAYER.move_to(town=iosla, background=bg)
""".strip()
   }, {
"role": "user", "content": """
What kind of buildings surround me?
""".strip()
   }, {
"role": "assistant", "content": """
NARRATOR.speak("You look around and see many small houses, with a tavern a little ways down the road.")
""".strip()
   }, {
"role": "user", "content": """
I would like to go into the tavern.
""".strip()
   }
]

# client = OpenAI(base_url="http://192.168.1.200:7776", api_key="")
# response = client.chat.completions.create(messages=STARTING_MESSAGES, model="")
# print(response.choices[0].message.content)

def main():
   endpoint = "http://192.168.1.200:7776/v1"
   headers = {
      "Content-Type": "application/json"
   }
   data = {
      "messages": STARTING_MESSAGES
   }
   response = requests.post(
      f"{endpoint}/chat/completions",
      headers=headers,
      json=data,
      stream=True
   )

   if response.status_code == 200:
      body = response.text.split(":", 1)[-1].strip()
      try:
         data = json.loads(body)
      except Exception as ex:
         print(f"Failed to load json data:\n{body}")
         raise ex from ex
      print(data["choices"][0]["message"]["content"])
   else:
      print(response.text)

main()
