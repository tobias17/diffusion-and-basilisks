from common import State

from typing import List


class HubDescription: pass
def list_hubs() -> List[HubDescription]:
   return []

def create_hub(hub_name:str, hub_description) -> None:
   pass


class NpcDescription: pass
def list_npcs() -> List[NpcDescription]:
   return []

def create_npc(character_name:str, character_description:str, physical_description:str) -> None:
   pass

def talk_to_npc(character_name:str) -> None:
   pass


class ItemDescription: pass
def list_player_items() -> List[ItemDescription]:
   return []

def give_player_item(item_name:str, item_description:str, physical_description:str) -> None:
   pass

def player_use_item(item_name:str, action_description:str, consume_amount:int=0) -> None:
   pass




def main():
   pass

if __name__ == "__main__":
   main()
