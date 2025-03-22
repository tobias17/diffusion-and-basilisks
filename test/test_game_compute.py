import events as E
from game import Game

from typing import Tuple, Callable
import unittest

class Test_Game_Compute(unittest.TestCase):
    def __make_game(self) -> Game:
        return Game([
            E.Create_Location("loc1", "Location 1", "some details", True, True),
            E.Create_Location("loc2", "Location 2", "some details", True, True),
            E.Move_Player_To("loc1"),
            E.Create_Npc("npc1", "loc1", "First1", "Last1", "more details"),
            E.Create_Npc("npc2", "loc2", "First2", "Last2", "other details"),
            E.Start_Quest("quest1", "Quest 1", "bla bla bla"),
            E.Start_Quest("quest2", "Quest 2", "bla bla bla"),
            E.Give_Player_Unique_Item("u1", "Unique 1", "..."),
            E.Give_Player_Unique_Item("u2", "Unique 2", "..."),
            E.Give_Player_Stackable_Items("s1", "Stackable 1", 5, "..."),
            E.Give_Player_Stackable_Items("s2", "Stackable 2", 5, "..."),
            E.Give_Player_Stackable_Items("s3", "Stackable 3", 5, "..."),
        ])

    def test_get_npc_name(self):
        game = self.__make_game()
        self.assertEqual(game.get_npc_name("npc1"), "First1 Last1")
        self.assertEqual(game.get_npc_name("npc2"), "First2 Last2")
        with self.assertRaises(Exception):
            game.get_npc_name("npcX")
    
    def test_get_loc_name(self):
        game = self.__make_game()
        self.assertEqual(game.get_loc_name("loc1"), "Location 1")
        self.assertEqual(game.get_loc_name("loc2"), "Location 2")
        with self.assertRaises(Exception):
            game.get_npc_name("locX")
    
    def test_get_quest_name(self):
        game = self.__make_game()
        self.assertEqual(game.get_quest_name("quest1"), "Quest 1")
        self.assertEqual(game.get_quest_name("quest2"), "Quest 2")
        with self.assertRaises(Exception):
            game.get_npc_name("questX")
    
    def test_get_active_quests(self):
        game = self.__make_game()
        self.assertEqual(len(game.get_active_quests()), 2)
        game.add_event(E.End_Quest("quest1"))
        self.assertEqual(len(game.get_active_quests()), 1)
        game.add_event(E.End_Quest("quest2"))
        self.assertEqual(len(game.get_active_quests()), 0)

    def test_get_item_name(self):
        game = self.__make_game()
        self.assertEqual(game.get_item_name("u1"), "Unique 1")
        self.assertEqual(game.get_item_name("u2"), "Unique 2")
        self.assertEqual(game.get_item_name("s1"), "Stackable 1")
        self.assertEqual(game.get_item_name("s2"), "Stackable 2")
        self.assertEqual(game.get_item_name("s3"), "Stackable 3")

    def test_get_inventory_items(self):
        game = self.__make_game()
        self.assertEqual(len(game.get_inventory_items()), 5)
        game.add_event(E.Remove_Player_Unique_Item("u1", "no no no"))
        self.assertEqual(len(game.get_inventory_items()), 4)
        game.add_event(E.Remove_Player_Stackable_Items("s1", 5, "no no no"))
        self.assertEqual(len(game.get_inventory_items()), 3)
        game.add_event(E.Remove_Player_Stackable_Items("s2", 1, "no"))
        self.assertEqual(len(game.get_inventory_items()), 3)

    def test_get_curr_loc_id(self):
        game = self.__make_game()
        self.assertEqual(game.get_curr_loc_id(), "loc1")
        game.add_event(E.Move_Player_To("loc2"))
        self.assertEqual(game.get_curr_loc_id(), "loc2")
        game.add_event(E.Create_Location("locX", "Location X", "details", True, False))
        self.assertEqual(game.get_curr_loc_id(), "loc2")
        game.add_event(E.Create_Location("locY", "Location Y", "details", True, True))
        self.assertEqual(game.get_curr_loc_id(), "locY")

    def test_player_knows_about(self):
        game = self.__make_game()
        self.assertEqual(game.player_knows_about("loc1"), True)
        self.assertEqual(game.player_knows_about("loc2"), True)
        game.add_event(E.Create_Location("locX", "Location X", "bla bla bla", False, False))
        self.assertEqual(game.player_knows_about("locX"), False)
        game.add_event(E.Move_Player_To("locX"))
        self.assertEqual(game.player_knows_about("locX"), True)
        game.add_event(E.Create_Location("locY", "Location Y", "bla bla bla", False, True))
        self.assertEqual(game.player_knows_about("locY"), True)

    def test_get_npc_infos(self):
        game = self.__make_game()
        infos = game.get_npc_infos()
        for info in infos:
            if info.npc_id == "npc1":
                self.assertEqual(info.npc_name, "First1 Last1")
                self.assertEqual(info.loc_id,   "loc1")
                self.assertEqual(info.loc_name, "Location 1")
            elif info.npc_id == "npc2":
                self.assertEqual(info.npc_name, "First2 Last2")
                self.assertEqual(info.loc_id,   "loc2")
                self.assertEqual(info.loc_name, "Location 2")
            else:
                raise ValueError(f"Got unexpected npc ID '{info.npc_id}' in npc info")

        game.add_event(E.Move_Npc("npc1", "loc2"))
        game.add_event(E.Move_Npc("npc2", "loc1"))
        infos = game.get_npc_infos()
        for info in infos:
            if info.npc_id == "npc1":
                self.assertEqual(info.npc_name, "First1 Last1")
                self.assertEqual(info.loc_id,   "loc2")
                self.assertEqual(info.loc_name, "Location 2")
            elif info.npc_id == "npc2":
                self.assertEqual(info.npc_name, "First2 Last2")
                self.assertEqual(info.loc_id,   "loc1")
                self.assertEqual(info.loc_name, "Location 1")
            else:
                raise ValueError(f"Got unexpected npc ID '{info.npc_id}' in npc info")


if __name__ == "__main__":
   unittest.main()
