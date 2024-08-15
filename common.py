from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from abc import ABC

class State(Enum):
   INITIALIZING  = "INITIALIZING"
   HUB_IDLE      = "HUB_IDLE"
   HUB_TALKING   = "HUB_TALKING"
   TRAVEL_IDLE   = "TRAVEL_IDLE"
   TRAVEL_TALK   = "TRAVEL_TALK"
   TRAVEL_COMBAT = "TRAVEL_COMBAT"
   TRAVEL_EVENT  = "TRAVEL_EVENT"

class Event: pass
