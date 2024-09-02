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

Your interactions with the game world will be through an API where you will call python functions to generate content and make decisions.
The following is an example of how you might follow this API:
<api>
def create_apple(color:str, physical_description:str): # Creates a new apple with the given color and physical description
</api>
<calling>
create_apple("red", "a Red Delicious apple, deep maroon skin, stem poking out of top, a slight glare of lighting")
</calling>
'''.strip()

overview_prompt = """
The following is an overview of the current game:
<overview>
%%OVERVIEW%%</overview>
""".strip()

api_description = """
The following is the real API that you will have access to:
<api>
%%API_DESCRIPTION%%</api>
""".strip()

characters_prompt = """
The following is a list of existing characters the player can interact with:
<characters>
%%CHARACTERS%%</characters>
""".strip()

quests_prompt = """
The following are the currently active quests:
<quests>
%%QUESTS%%</quests>
""".strip()



need_more_function_calls = """
%%AI_RESPONSE%%
</calling>

%%SYSTEM_RESPONSE%%
<calling>
#
""".strip()+" "

error_in_function_calls = """
%%AI_RESPONSE%%
</calling>

Error processing call block:
<output>
%%OUTPUT%%
</output>

Please rewrite your last call block to remove these errors.
<calling>
""".strip()



state_prompts: Dict[State,str] = {}


state_prompts[State.INITIALIZING] = f"""
The player is currently in the INIALIZING state. Call the `create_location` function to generate a location.
<calling>
""".strip()

ask_for_function_calls = """
Please call the necessary functions to progress the game state in a fun-but-in-the-guide-rails manner.
Make sure to ONLY call the functions required, based on the player input or system instructions. Do NOT add extra functions.
<calling>
""".strip()


state_prompts[State.LOCATION_IDLE] = f"""
The player is currently in the LOCATION_IDLE state. The player has been prompted what they would like to do next.
<player-input>
%%PLAYER_INPUT%%
</player-input>

{ask_for_function_calls}
""".strip()


state_prompts[State.LOCATION_TALK] = f"""
The player is currently in the LOCATION_TALK state where they are interacting with:
%%NPC_NAME%%
%%NPC_DESCRIPTION%%

The following is the interaction history between the player and %%NPC_NAME%%:
<conversation>
%%CONVERSATION%%</conversation>

While you have access to a library of functions, try and use just `speak_npc_to_player` unless others are absolutely necessary.

{ask_for_function_calls}
""".strip()


state_prompts[State.TRAVELING] = f"""
The player is currently in the TRAVELING state.

Use the `describe_travel` function to give the player a description of their environment as they are in this traveling state.

If you want to have the player arrive at their destination, use the `move_to_location` function to put them at the right location.
If instead you want to spawn an event or an interesting area, use the `create_location` function first and then `move_to_location` to kick it off.

{ask_for_function_calls}
""".strip()



mega_prompts: Dict[State,str] = {

#################
# LOCATION_TALK #
#################
State.LOCATION_TALK: f"""
{intro}

{overview_prompt}

{quests_prompt}

%%FUNCTIONS%%

The player is currently in the LOCATION_TALK state where they are interacting with:
%%NPC_NAME%%
%%NPC_DESCRIPTION%%

The following is the interaction history between the player and %%NPC_NAME%%:
<conversation>
%%CONVERSATION%%</conversation>

While you have access to a library of functions, try and use just `speak_npc_to_player` unless others are absolutely necessary.

{ask_for_function_calls}
#
""".strip()+" ",

}


