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
If you plan on calling multiple API functions before getting a player response write out ALL steps to your plan here.
Make sure to ONLY include items for you. Do NOT include items for the player to perform. Do NOT include items that rely on player input. Do ONLY what you can this very instant with the information written above.
This scratchpad should be SHORT and SIMPLE!{SYSTEM_END}
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
If you are done with your tasking LEAVE THIS EMPTY. If you are waiting for player input LEAVE THIS EMPTY.
Only write something if there are immediate actions you want to perform that require 0 player input. Otherwise immediately close this tag.{SYSTEM_END}
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

You will interact with the world through a python inspired API. While this looks and will be called like python code, you only have access to the specified API and trying to do anything else like if-statemnts and for-loops WILL raise exceptions.
The following is an example of what the API might look like and how you would call it, utilizing the scratchpad to call 1 function at a time.
<example-api>
def eat_apple(): # eats an apple from the inventory (if available)
def create_apple(color:str, description:str):
	\"\"\"
	Creates an apple of the specified color and physical description.
	
	Parameters:
	-----------
	color : str
		the color of the apple
	description : str
		the physical description of the apple, make sure to include a comma-seperated list of visual elements such that this string can be passed directly to a txt2img AI model
	\"\"\"
</example-api>
<example-scratchpad>
I should make a new apple and then eat it.
</example-scratchpad>
<example-calling>
create_apple("red", "a juicy apple with a deep red skin, a stem sprouting from the top with 2 small leaves")
</example-calling>
<example-scratchpad>
I should eat the apple I just made.
</example-scratchpad>
<example-calling>
eat_apple()
</example-calling>
<example-scratchpad>
</example-scratchpad>

The following is an overview of the current game:
<overview>
%%OVERVIEW%%</overview>

The following are the currently active quests:
<quests>
%%QUESTS%%</quests>

{extra_info}The character is currently in the {state.value} state.
{instructions[state]}
""".strip()
