import events as E
from game import Game

from typing import Tuple, Callable
import unittest

class Test_Event_Creation(unittest.TestCase):
   game: Game

   def __accept(self, fnx:Callable[[],Tuple[bool,str]], new_event_count:int):
      start_count = self.game.new_events
      ok, msg = fnx()
      self.assertTrue(ok)
      self.assertEqual(len(msg), 0)
      self.assertEqual(self.game.new_events, start_count + new_event_count)
   
   def __reject(self, fnx:Callable[[],Tuple[bool,str]]):
      start_count = self.game.new_events
      ok, msg = fnx()
      self.assertFalse(ok)
      self.assertGreater(len(msg), 0)
      self.assertEqual(self.game.new_events, start_count)

   def test_create_location(self):
      self.game = Game([])
      self.__accept(lambda: E.create_location(self.game, "loc", "Location 1", "some details", True, True), 1)
      self.__reject(lambda: E.create_location(self.game, "loc", "Location 2", "other details", True, True))

   def test_move_player_to(self):
      self.game = Game([
         E.Create_Location("loc1", "Location 1", "some details", True, True),
         E.Create_Location("loc2", "Location 2", "other details", True, True),
      ])
      self.__accept(lambda: E.move_player_to(self.game, "loc2"), 0)
      self.__accept(lambda: E.move_player_to(self.game, "loc1"), 1)
      self.__accept(lambda: E.move_player_to(self.game, "loc1"), 0)
      self.__accept(lambda: E.move_player_to(self.game, "loc2"), 1)
      self.__accept(lambda: E.move_player_to(self.game, "loc2"), 0)
      self.__reject(lambda: E.move_player_to(self.game, "loc3"))

   def test_create_npc(self):
      self.game = Game([])
      fnx = lambda: E.create_npc(self.game, "npc1", "loc1", "First", "Last", "details")
      self.__reject(fnx)
      self.game.add_event(E.Create_Location("loc1", "Location 1", "some details", True, True))
      self.__accept(fnx, 1)
      self.__reject(fnx)
      self.__accept(lambda: E.create_npc(self.game, "npc2", "loc1", "First", "Last", "details"), 1)

   def test_kill_npc(self):
      self.game = Game([
         E.Create_Npc("npc1", "loc1", "First", "Last", "details"),
      ])
      self.__accept(lambda: E.kill_npc(self.game, "npc1"), 1)
      self.__accept(lambda: E.kill_npc(self.game, "npc1"), 0)
      self.__reject(lambda: E.kill_npc(self.game, "npc2"))



if __name__ == "__main__":
   unittest.main()
