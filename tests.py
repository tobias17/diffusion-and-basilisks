from main import parse_function
from functions import Function, Parameter

from typing import List, Dict, Optional
import unittest

add_text = Function(lambda a, b: a + b, "add_text", "", Parameter("a",str), Parameter("b",str))

def parse_function_helper():
   pass
class TestParseFunction(unittest.TestCase):

   def __happy(self, input:str, exp_func_name:str, exp_args:List, exp_kwargs:Dict):
      try:
         out, err = parse_function(input)
         self.assertIsNotNone(out, err)
         self.assertIsInstance(out, tuple)
         assert out is not None
         
         self.assertEqual(len(out), 3)
         act_func_name, act_args, act_kwargs = out
         
         self.assertEqual(act_func_name, exp_func_name)

         self.assertEqual(len(act_args), len(exp_args))
         for act_arg, exp_arg in zip(act_args, exp_args):
            self.assertEqual(act_arg, exp_arg)
         
         self.assertEqual(len(act_kwargs), len(exp_kwargs))
         for (act_key,act_val), (exp_key,exp_val) in zip(act_kwargs.items(), exp_kwargs.items()):
            self.assertEqual(act_key, exp_key)
            self.assertEqual(act_val, exp_val)
      except Exception as ex:
         raise ex.__class__(f"{ex}: {input}")

   def __sad(self, input:str):
      try:
         out, err = parse_function(input)
         self.assertIsNone(out, "Got an output when an error was expected")
         self.assertTrue(err, "Got an empty error message when output was None")
      except Exception as ex:
         raise ex.__class__(f"{ex}: {input}")

   def test_simple_case(self):
      self.__happy('add_text("Hello,", " sailor!")', 'add_text', ('"Hello,"', '" sailor!"'), {})
   def test_mixed_args(self):
      self.__happy('add_text("Hello,", second=" sailor!")', 'add_text', ('"Hello,"',), {"second": '" sailor!"'})
   def test_kwargs(self):
      self.__happy('add_text(first="Hello,", second=" sailor!")', 'add_text', tuple(), {"first": '"Hello,"', "second": '" sailor!"'})
   
   def test_mismatched_quotes(self):
      self.__sad('add_text("this is some text", "a mistmatched string)')
   def test_arg_after_kwarg(self):
      self.__sad('add_text(first="Hello,", " sailor!")')

if __name__ == "__main__":
   unittest.main()
