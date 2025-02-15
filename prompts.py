

API_DEFINITION = """
GAME.create_location(loc_id:str, name:str, desc:str)
PLAYER.move_to(loc_id:Location)
GAME.create_npc(npc_id:str, name:str, desc:str)
NPC.speak_to_player(npc_id:str, text:str)
PLAYER.speak_to_npc(npc_id:str, text:str)
NARRATOR.speak(text:str)
"""


SYSTEM_MESSAGE = """
You are a helpful assistant who will play the role of Dungeon Master in a high fantasy role playing game. You will advance the game state via function calls.

While this looks and functions like python, you only have access to the functions themselves and no higher-level programming functions. The following is the API you will have access to:
```
%%API_DEFINITION%%
```

Start off by create a new town and moving the player to it. You will then wait for the user to input what they would like to do.

Make sure to only advance the game by what is necessary to satisfy the user's request.
""".strip()

STARTING_MESSAGES = [
   {
"role": "system", "content": 
   }, {
"role": "assistant", "content": """
GAME.create_location(id="iosla_town_square", name="Iosla", desc="A charming seaside town centered around an ancient gnarled oak tree with massive spreading branches in the town square.")
PLAYER.move_to(loc_id="iosla_town_square")
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
