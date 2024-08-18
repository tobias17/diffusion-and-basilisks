from common import State
from typing import Dict, List
import re

class Template:
   PATTERN = re.compile(r'%%([a-zA-Z_]+)%%')
   chunks: List[str]
   mapping: Dict[str,str]

   def __init__(self, *chunks:str):
      self.chunks = list(chunks)
      self.mapping = {}
   
   def __getitem__(self, key:str) -> str:
      return self.mapping[key]

   def __setitem__(self, key:str, value:str) -> None:
      self.mapping[key] = value
   
   def render(self) -> str:
      text = "\n\n".join(self.chunks)
      matches = Template.PATTERN.findall(text)
      for match in matches:
         value = self.mapping.get(match, None)
         if value is None:
            raise ValueError(f"Failed to find key '{match}' in mapping, existing keys are {list(self.mapping.keys())}")
         text = text.replace(f"%%{match}%%", value)
      return text




default_world = """
The game takes place in Iosla, a high fantasy realm full of mystery, dangers, and loot. A wide variety of creatures populate Iosla, both fantastic and degenerate.
""".strip()

intro = f'''
You are a large language model tasked with helping a human play a video game. You will be playing the role of game master where you will be prompted to make meta-level decisions as well as generate individual bits of content.

{default_world}

Your interactions with the game world will be through an API where you will call python functions to generate content and make decisions. The following is an example of how you might follow this API.

begin_example

$$begin_api$$
def create_apple(color:str, physical_description:str) -> None: # Creates a new apple with the given color and physical description
$$end_api$$

$$begin_calling$$
create_apple("red", "a Red Delicious apple, deep maroon skin, stem poking out of top, a slight glare of lighting")
$$end_calling$$

end_example
'''.strip()

api_description = """
The following is the real API that you will have access to.
$$begin_api$$
%%API_DESCRIPTION%%
$$end_api$$
""".strip()



need_more_function_calls = """
%%AI_RESPONSE%%
$$end_calling$$

%%SYSTEM_RESPONSE%%
$$begin_calling$$
""".strip()



state_prompts: Dict[State,str] = {}


state_prompts[State.INITIALIZING] = f"""
The player is currently in the INIALIZING state. Call the `create_location` function to generate a location and then call `move_to_location` to get there.
$$begin_calling$$
""".strip()

ask_for_function_calls = """
Please call the necessary functions to progress the game state in a fun-but-in-the-guide-rails manner.
$$begin_calling$$
""".strip()


state_prompts[State.LOCATION_IDLE] = f"""
The player is currently in the LOCATION_IDLE state. The player has been prompted what they would like to do next.
$$begin_player_input$$
%%PLAYER_INPUT%%
$$end_player_input$$

{ask_for_function_calls}
""".strip()


state_prompts[State.LOCATION_TALK] = f"""
The player is currently in the LOCATION_TALK state where they are interacting with:
%%NPC_NAME%%
%%NPC_DESCRIPTION%%

$$begin_conversation$$
%%CONVERSATION%%
$$end_conversation$$

{ask_for_function_calls}
""".strip()


state_prompts[State.TRAVELING] = f"""
The player is currently in the TRAVELING state.

Use the `describe_travel` function to give the player a description of their environment as they are in this traveling state.

If you want to have the player arrive at their destination, use the `move_to_location` function to put them at the right location.
If instead you want to spawn an event or an interesting area, use the `create_location` function first and then `move_to_location` to kick it off.

{ask_for_function_calls}
""".strip()

