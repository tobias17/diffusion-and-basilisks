from main import process_functions
from functions import Function, Parameter

import unittest

add_text = Function(lambda a, b: a + b, "add_text", "", Parameter("a",str), Parameter("b",str))

class TestProcessing(unittest.TestCase):
   def basic_case(self):
      self.assertEqual(process_functions('add_text("Hello,", " sailor!")'), "Hello, sailor!")

if __name__ == "__main__":
   unittest.main()
