from __future__ import annotations
from common import logger
from game import Game

from dataclasses import dataclass
from threading import Thread, Event
from typing import Optional, List
import time, sys, termios, select

TARGET_FPS = 10.0
FRAME_DELTA = 1.0 / TARGET_FPS
SLEEP_MS = 10.0

SCREEN_WIDTH  = 150
SCREEN_HEIGHT = 50

@dataclass
class Rect:
   x1: int
   y1: int
   w: int
   h: int

   @property
   def x2(self) -> int: return self.x1 + self.w
   @property
   def y2(self) -> int: return self.y1 + self.h

INPUT_HEIGHT = 4

EVENT_SPACE = Rect(2, 1, SCREEN_WIDTH - 4, SCREEN_HEIGHT - INPUT_HEIGHT - 3)
INPUT_SPACE = Rect(2, EVENT_SPACE.y2 + 1, SCREEN_WIDTH - 4, INPUT_HEIGHT)


# Context Manager to configure terminal settings, to be set up by the main thread
class Peek_Terminal_Input:
   def __enter__(self):
      self.fd = sys.stdin.fileno()
      self.old_settings = termios.tcgetattr(self.fd)
      new_settings = termios.tcgetattr(self.fd)
      new_settings[3] = new_settings[3] & ~termios.ICANON  # Turn off canonical mode
      termios.tcsetattr(self.fd, termios.TCSADRAIN, new_settings)
      return self
   def __exit__(self, exc_type, exc_val, exc_tb):
      termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)


def coord(x:int, y:int) -> str:
   return f"\033[{y+1};{x+1}H"


class Screen_Handler:
   kill_event: Event

   __event_lines: List[str]
   __event_page_index: int = 0

   __input_buffer: str
   __accepting_input: bool

   def __init__(self, game:Game):
      self.kill_event = Event()
      self.__input_buffer = ""
      self.update_game(game)

   def update_game(self, game:Game) -> None:
      self.__event_lines = []
      for event in game.events:
         text = event.player(game)
         if text is not None:
            while len(text) > EVENT_SPACE.w:
               self.__event_lines.append(text[:EVENT_SPACE.w])
               text = text[EVENT_SPACE.w:]
            self.__event_lines.append(text)
            self.__event_lines.append("")
      self.__event_lines.pop(-1) # remove last newline

   def __fill_buffer(self) -> None:
      POOL_INTERVAL_SEC = 0.01
      while not self.kill_event.is_set():
         if select.select([sys.stdin], [], [], POOL_INTERVAL_SEC)[0]:
            char = sys.stdin.read(1)
            logger.info(f"Got char: <|{char}|>")

   def run(self) -> None:
      Thread(target=self.__fill_buffer).start()

      e_time = time.time()
      while not self.kill_event.is_set():
         if time.time() < e_time:
            time.sleep(SLEEP_MS / 1000.0)
            continue

         text = "\033[2J" # clear screen
         text += coord(0, 0) + "+" + "-"*(SCREEN_WIDTH-2) + "+"
         for i in range(1, SCREEN_HEIGHT-1):
            text += coord(0, i) + "|" + coord(SCREEN_WIDTH-1, i) + "|"
         text += coord(0, SCREEN_HEIGHT-1) + "+" + "-"*(SCREEN_WIDTH-2) + "+"

         text += coord(0, EVENT_SPACE.y2) + "+" + "-"*(SCREEN_WIDTH-2) + "+"

         end = len(self.__event_lines) - self.__event_page_index * EVENT_SPACE.h
         start = end - EVENT_SPACE.h
         for i in range(start, end):
            if i >= 0:
               text += coord(EVENT_SPACE.x1, EVENT_SPACE.y1+i-start) + self.__event_lines[i]

         text += coord(INPUT_SPACE.x1, INPUT_SPACE.y1) + "> " + self.__input_buffer

         print(text, end="")
         e_time += FRAME_DELTA
