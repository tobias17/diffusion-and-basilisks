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



define_api = f"""
The following is the API you will have access to. You are allowed to call 1 of these at a time.
<api>
%%API%%</api>
""".strip()

ask_for_scratchpad = f"""
To start off, you will first use the following scratchpad to create an action plan. This should be 1 or more lines, written in plain English, description your intended action(s).
If you plan on calling multiple API functions before getting a player response write out ALL steps to your plan here.{SYSTEM_END}
{ASSISTANT_START}
<scratchpad>
""".strip()

end_scratchpad = f"""
</scratchpad>{ASSISTANT_END}
{SYSTEM_START}
""".strip()

update_scratchpad = f"""
Please rewrite an updated scratchpad based on what you just accomplished.
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



limiter = "ONLY call functions that accomplish what the player is asking for, NOT more."
instructions: Dict[State,str] = {
   State.TOWN_IDLE: f"Use the following player input to call the appropriate functions to progress the game state. {limiter}\n<player-input>\n%%PLAYER_INPUT%%</player-input>",
   State.TOWN_TALK: f"Use the following converstation history and player input to respond to them and/or call other functions. {limiter}\n<conversation>\n%%CONVERSATION%%</conversation>",
   State.ON_THE_MOVE: f"Use the provied APIs to either construct a fun and unique encounter for the player to interact with, or have them arrive at their target location. Make your decisions based on the following travel goal you wrote yourself before leaving town.\n<travel-goal>\n%%TRAVEL_GOAL%%\n</travel-goal>",
}

def make_intro_prompt(state:State) -> str:
   extra_info = ""
   if state == State.TOWN_IDLE:
      extra_info += """
The following is a list of existing NPC characters the player can interact with:
<characters>
%%CHARACTERS%%</characters>
""".strip() + "\n\n"

   return f"""
{SYSTEM_START}
You are a large language model tasked with helping a human play a video game.
You will be playing the role of game master where you will be prompted to make meta-level decisions as well as generate individual bits of content.
Try your best to be creative. Err on the side of crazy, trying to stay away from things feeling too vanilla or cliche.

The game takes place in Iosla, a high fantasy realm full of mystery, dangers, and loot. A wide variety of creatures populate Iosla, both fantastic and degenerate.

The following is an overview of the current game:
<overview>
%%OVERVIEW%%</overview>

The following are the currently active quests:
<quests>
%%QUESTS%%</quests>

{extra_info}The character is currently in the {state.value} state.
{instructions[state]}
""".strip()
