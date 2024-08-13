from common import State
from typing import Dict

intro = """
You are a large language model tasked with helping a human play a video game. You will be playing the role of game master where you will be prompted to make meta-level decisions as well as generate individual bits of content.

Your interactions with the game world will be through an API where you will call python functions to generate content and make decisions.
""".strip()

default_world = """
The game takes place in Iosla, a high fantasy realm full of mystery, dangers, and loot. A wide variety of creatures populate Iosla, both fantastic and degenerate.
""".strip()






state_map: Dict[State,str] = {}


state_map[State.INITIALIZING] = f"""
The player is currently in the INIALIZING state. Please call the create_hub function to generate the world's first hub.
""".strip()

ask_for_function_calls = """
Please call the necessary functions to progress the game state in a fun-but-in-the-guide-rails manner.

$$begin_code_block$$
```python
""".strip()


state_map[State.HUB_IDLE] = f"""
The player is currently in the HUB_IDLE state. The player has been prompted what they would like to do next.

$$begin_player_input$$
%%PLAYER_INPUT%%
$$end_player_input$$

{ask_for_function_calls}
""".strip()


state_map[State.HUB_TALKING] = f"""
The player is currently in the HUB_TALKING state where they are interacting with %%NPC_NAME%%.

%%NPC_NAME%%:
%%NPC_BIO%%

$$begin_conversation$$
%%CONVERSATION%%
$$end_conversation$$

{ask_for_function_calls}
""".strip()


state_map[State.TRAVEL_IDLE] = f"""
The player is currently in the TRAVEL_IDLE state. The player has been prompted what they would like to do next.

$$begin_player_input$$
%%PLAYER_INPUT%%
$$end_player_input$$

{ask_for_function_calls}
""".strip()
