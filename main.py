from common import State, Event
from prompts import Template, intro, state_map
from functions import Function_Map, Function, Parameter
import events as E

from typing import List, Optional, Type, TypeVar, Tuple
from openai import OpenAI

T = TypeVar('T')



########################
###  Game State Obj  ###
########################

class Game:
   events: List[Event]
   def __init__(self):
      self.events = []

   def get_current_state(self) -> State:
      for event in reversed(self.events):
         state = event.implication()
         if state is not None:
            return state
      return State.INITIALIZING
   
   def get_current_location(self) -> E.Create_Location_Event:
      for event in reversed(self.events):
         if isinstance(event, E.Create_Location_Event):
            return event
      raise RuntimeError(f"get_current_location failed to find Create_Location_Event in the event list")


   def create_location(self, hub_description:str, hub_name:str) -> Tuple[bool,Optional[str]]:
      self.events.append(E.Create_Location_Event(hub_name, hub_description))
      return True, None

   def create_npc(self, name:str, character_background:str, physical_description:str) -> Tuple[bool,Optional[str]]:
      current_location = self.get_current_location()
      for event in reversed(self.events):
         if isinstance(event, E.Create_Character_Event) and event.location_name == current_location and event.character_name == name:
            return False, f"Location '{current_location}' already has a character with the name '{name}'"
      self.events.append(E.Create_Character_Event(name, self.get_current_location().name, character_background, physical_description))
      return True, None

   def talk_to_npc(self, name:str) -> Tuple[bool,Optional[str]]:
      location_names = []
      current_location = self.get_current_location()
      for event in reversed(self.events):
         if isinstance(event, E.Create_Character_Event) and event.location_name == current_location:
            if name == event.character_name:
               self.events.append(E.Start_Conversation_Event(name))
               return True, None
            location_names.append(event.character_name)
      return False, f"Failed to find character named '{name}', the current location ({current_location}) has characters with the following names: {location_names}"



#########################
### Func Registration ###
#########################

Function_Map.register(
   Function(
      Game.create_location, "create_location", "Create a new Hub with the description and name, make sure the name is some thing catchy that can be put on a sign",
      Parameter("hub_description",str), Parameter("hub_name",str)
   ),
   State.INITIALIZING
)

Function_Map.register(
   Function(
      Game.create_npc, "create_npc", "Creates a new NPC that the player could interact with",
      Parameter("name",str), Parameter("character_background",str), Parameter("physical_description",str)
   ),
   State.LOCATION_IDLE, State.LOCATION_TALK
)



########################
###  Main Game Loop  ###
########################

client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
def make_completion(prompt:str):
   global client

   completion = client.chat.completions.create(
      model="lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF",
      messages=[
         { "role":"system", "content":prompt },
      ],
      temperature=0.7,
      max_tokens=128,
      stop=["$$end_"],
   )

   resp = completion.choices[0].message.content
   assert resp is not None
   return resp

def game_loop(game:Game):
   while True:
      current_state = game.get_current_state()

      if current_state == State.INITIALIZING:
         template = Template(intro, Function_Map.render(current_state), state_map[current_state])
         prompt = template.render()
         print(prompt)
         resp = make_completion(prompt)
         events = process_functions(resp, Function_Map.get(current_state))
         assert len(events) == 1, f"len(events)={len(events)}"
         print(events[0].render())
         game.add_events(*events, StateTransitionEvent(from_state=current_state, to_state=State.HUB_IDLE))
      elif current_state == State.HUB_IDLE:
         template = Template(intro, Function_Map.render(current_state), state_map[current_state])
         template["PLAYER_INPUT"] = input("What would you like to do?\n").strip()
         prompt = template.render()
         print(prompt)
         resp = make_completion(prompt)
         events = process_functions(resp, Function_Map.get(current_state))
         print(events)
      else:
         raise ValueError(f"game_loop() does not support {current_state} state yet")



def main():
   game = Game()
   game_loop(game)

if __name__ == "__main__":
   main()
