from common import logger, Screen_Config
from game import Game, Game_Processor
import events as E
from user import (
   Rect, Game_Window, Screen_Buffer, Image_Screen_Buffer, Input_Data, interpret_bytes, Special_Keys,
   Main_Menu, Events_Display, Locations_Display, Characters_Display, Inventory_Display, Quests_Display
)

from typing import List, Tuple, Optional
import traceback, select, threading, os, sys, time


class User_Controller(Game_Processor):
   POLL_INTERVAL_SEC = 0.01
   rect: Rect = Rect(0, 0, Screen_Config.WIDTH, Screen_Config.HEIGHT)

   game: Game
   kill_event: threading.Event
   main_menu: Main_Menu

   game_windows: List[Game_Window]
   has_updated: List[bool]
   window_index: int = 0

   pause_screen: Screen_Buffer
   pause_rect: Rect
   pause_index: int = 0
   is_paused: bool = False

   done_processing: bool = False

   def __init__(self, kill_event:threading.Event, saves:List[str]):
      self.kill_event = kill_event
      self.main_menu = Main_Menu(Screen_Buffer(Screen_Config.WIDTH, Screen_Config.HEIGHT), saves)

      self.game_windows = [
         Events_Display(Image_Screen_Buffer(Screen_Config.WIDTH, Screen_Config.HEIGHT), kill_event, self.__user_input_complete),
         Locations_Display(Image_Screen_Buffer(Screen_Config.WIDTH, Screen_Config.HEIGHT)),
         Characters_Display(Image_Screen_Buffer(Screen_Config.WIDTH, Screen_Config.HEIGHT)),
         Inventory_Display(Screen_Buffer(Screen_Config.WIDTH, Screen_Config.HEIGHT)),
         Quests_Display(Screen_Buffer(Screen_Config.WIDTH, Screen_Config.HEIGHT)),
      ]
      self.has_updated = [False]*len(self.game_windows)

      # Prepare the pause screen
      pause_width  = 9 + max(len(window.NAME) for window in self.game_windows)
      pause_height = 3 + 2*len(self.game_windows)
      pause_x1 = (self.rect.w - pause_width) // 2
      pause_y1 = (self.rect.h - pause_height) // 2
      self.pause_screen = Screen_Buffer(pause_width, pause_height, pause_x1, pause_y1, can_clear=False)
      self.pause_rect = Rect(0, 0, pause_width, pause_height)
      for i, window in enumerate(self.game_windows):
         self.pause_screen.put_text_in(self.pause_rect, 6, 2 + 2*i, window.NAME)
      self.pause_screen.put_text_in(self.pause_rect, 4, 2, ">")
      self.pause_screen.move_cursor(3, 2)

      self.fd = sys.stdin.fileno()
      threading.Thread(target=self.run).start()

   def wait_for_save_selection(self) -> Tuple[str,bool]:
      self.main_menu.screen_buffer.draw(only_dirty=False)
      while True:
         if self.kill_event.is_set():
            return "", False
         if self.main_menu.selected_save is not None:
            return self.main_menu.selected_save, self.main_menu.making_new_game
         time.sleep(0.01)

   def process_game(self, game:Game, other_proc:Game_Processor) -> Optional[Game]:
      self.done_processing = False

      self.game_windows[self.window_index].accept_input()
      self.peek_game(game)
      self.game = game.reset_event_count()

      other_proc.peek_game(self.game)
      last_peek_count = self.game.new_events

      while not self.kill_event.is_set():
         new_events = (self.game.new_events > last_peek_count) # compute this first to avoid race condition
         if self.done_processing:
            return self.game
         elif new_events:
            other_proc.peek_game(self.game.copy())
            last_peek_count = self.game.new_events
         time.sleep(0.01)

      return None

   def peek_game(self, game:Game) -> None:
      self.game = game
      self.game_windows[self.window_index].visualize_game(game)
      self.game_windows[self.window_index].screen_buffer.draw()
      for i in range(len(self.game_windows)):
         self.has_updated[i] = (i == self.window_index)

   def __user_input_complete(self, data:Input_Data) -> None:
      go_again = data.text.endswith("&")
      if go_again:
         data.text = data.text[:-1]

      if data.event is E.Player_Request_Action:
         self.game.add_event(E.Player_Request_Action(data.text))
      elif data.event is E.Speak_Player_to_Npc:
         self.game.add_event(E.Speak_Player_to_Npc(data.data['npc_id'], data.text))
      else:
         raise RuntimeError(f"{self.__class__.__name__} does not support processing user input from event type {data.event.__name__}")

      self.game_windows[self.window_index].clear_input(accept_input=go_again)
      self.peek_game(self.game)
      if not go_again:
         self.done_processing = True

   def __read_bytes(self) -> bytes:
      if os.name == 'nt':
         import msvcrt
         data = bytes()
         while not self.kill_event.is_set():
            while msvcrt.kbhit():
               data += msvcrt.getch()
            if len(data) > 0:
               return data
            time.sleep(self.POLL_INTERVAL_SEC)
      else:
         while not self.kill_event.is_set():
            if select.select([sys.stdin], [], [], self.POLL_INTERVAL_SEC)[0]:
               return os.read(self.fd, 16)
      return bytes()

   def run(self) -> None:
      try:
         # Events and Input
         window = self.game_windows[self.window_index]
         window.write_to_buffer()

         # Start our main read and process loop
         while not self.kill_event.is_set():
            seq = self.__read_bytes()
            if len(seq) == 0:
               continue # normally means our kill_event got set
            inp = interpret_bytes(seq)
            if inp is None:
               continue # normally means it's a special key we do not handle

            if isinstance(inp, Special_Keys) and inp == Special_Keys.CTRL_C:
               logger.info("Detected ctrl+c, setting kill event")
               self.kill_event.set()

            if self.main_menu.selected_save is None:
               self.main_menu.process_input(inp)
            else:
               if not hasattr(self, "game"):
                  time.sleep(0.01)
                  continue

               if isinstance(inp, Special_Keys):
                  if inp == Special_Keys.CTRL_R:
                     logger.info("Redrawing entire screen buffer")
                     self.game_windows[self.window_index].screen_buffer.draw(only_dirty=False)
                     continue
                  elif inp == Special_Keys.ESCAPE:
                     self.is_paused = not self.is_paused
                     self.game_windows[self.window_index].screen_buffer.draw(only_dirty=False)
                     if self.is_paused:
                        self.pause_screen.draw(only_dirty=False)
                     continue
                  elif self.is_paused:
                     if inp in (Special_Keys.DOWN, Special_Keys.UP):
                        self.pause_screen.put_text_in(self.pause_rect, 4, 2 + 2*self.pause_index, " ")
                        amnt = 1 if inp == Special_Keys.DOWN else -1
                        self.pause_index += amnt
                        if self.pause_index < 0:
                           self.pause_index += len(self.game_windows)
                        elif self.pause_index >= len(self.game_windows):
                           self.pause_index -= len(self.game_windows)
                        self.pause_screen.put_text_in(self.pause_rect, 4, 2 + 2*self.pause_index, ">")
                        self.pause_screen.move_cursor(3, 2 + 2*self.pause_index)
                        self.pause_screen.draw(only_dirty=True)
                     elif inp == Special_Keys.ENTER:
                        self.window_index = self.pause_index
                        self.is_paused = False
                        if not self.has_updated[self.window_index]:
                           self.game_windows[self.window_index].visualize_game(self.game)
                           self.has_updated[self.window_index] = True
                        self.game_windows[self.window_index].screen_buffer.draw(only_dirty=False)
                     continue

               if not self.is_paused:
                  self.game_windows[self.window_index].process_input(inp)

      except Exception as ex:
         logger.error(f"Screen Hanlder ran into error in run")
         for line in traceback.format_exc().split("\n"):
            logger.error(line)
         self.kill_event.set()
         raise ex from ex
