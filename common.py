from enum import Enum

class State(Enum):
   HUB_IDLE = "HubIdle"
   HUB_TALKING = "HubTalking"
   TRAVEL_IDLE = "TravelIdle"
   TRAVEL_TALK = "TravelTalk"
   TRAVEL_COMBAT = "TravelCombat"
   TRAVEL_EVENT = "TravelEvent"
