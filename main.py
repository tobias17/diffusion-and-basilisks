from enum import Enum
from typing import List

class State(Enum):
   HUB_IDLE = "HubIdle"
   HUB_TALKING = "HubTalking"
   TRAVEL_IDLE = "TravelIdle"
   TRAVEL_TALK = "TravelTalk"
   TRAVEL_COMBAT = "TravelCombat"
   TRAVEL_EVENT = "TravelEvent"

class HubDescription: pass
def list_hubs() -> List[HubDescription]:
   return []

def create_hub(hub_name:str, hub_description) -> None:
   pass

def create_npc(hub_name:str, character_name:str, character_description:str, physical_description:str) -> None:
   pass

def main():
   pass

if __name__ == "__main__":
   main()
