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


SYSTEM_START    = "<|im_start|>system"
SYSTEM_END      = "<|im_end|>"
ASSISTANT_START = "<|im_start|>assistant"
ASSISTANT_END   = "<|im_end|>"



default_world = """
The game takes place in Iosla, a high fantasy realm full of mystery, dangers, and loot. A wide variety of creatures populate Iosla, both fantastic and degenerate.
""".strip()

intro = f'''
You are a large language model tasked with helping a human play a video game. You will be playing the role of game master where you will be prompted to make meta-level decisions as well as generate individual bits of content.

{default_world}
'''.strip()

overview_prompt = """
The following is an overview of the current game:
<overview>
%%OVERVIEW%%</overview>
""".strip()

api_description = """
The following is the API that you have access to:
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



define_api = f"""
The following is the API you will have access to. You are allowed to call 1 of these at a time.
<api>
%%API%%</api>
""".strip()

ask_for_scratchpad = f"""
Use the following scratchpad to create an action plan. Write atleast 1 line and use more if needed, describing what you intend on doing.
If you want to call a chain of multiple API functions, write out your full plan here.{SYSTEM_END}
{ASSISTANT_START}
<scratchpad>
""".strip()

end_scratchpad = f"""
</scratchpad>{ASSISTANT_END}
{SYSTEM_START}
""".strip()

update_scratchpad = f"""
Please rewrtie an updated scratchpad based on what you just accomplished.
Remove any items completed but keep tasks that need completing.
Leave the scratchpad empty iff you completed all of your tasks.{SYSTEM_END}
{ASSISTANT_START}
<scratchpad>
""".strip()

ask_for_function_call = f"""
Please call the necessary function to progress the game state in a fun-but-in-the-guide-rails manner.
Make sure to ONLY call only a SIGNLE function. Do NOT call multiple functions.{SYSTEM_END}
{ASSISTANT_START}
<calling>
""".strip()

end_function_calling = f"""
</calling>{ASSISTANT_END}
{SYSTEM_START}
""".strip()



mega_prompts: Dict[State,str] = {

#################
# LOCATION_TALK #
#################
State.LOCATION_TALK: f"""
{SYSTEM_START}
{intro}

{overview_prompt}

{quests_prompt}

The player is currently in the LOCATION_TALK state where they are interacting with:
%%NPC_NAME%%
%%NPC_DESCRIPTION%%

The following is the interaction history between the player and %%NPC_NAME%%:
<conversation>
%%CONVERSATION%%</conversation>
""".strip(),

}


