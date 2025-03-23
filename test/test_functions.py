from functions import parse_function, Function_Call_Data

from typing import List, Dict
import unittest

class Test_Parse_Function(unittest.TestCase):
   def __happy(self, input:str, exp_func_name:str, exp_args:List, exp_kwargs:Dict):
      ctx = f"Input: <|{input}|>"
      out, err = parse_function(input)
      self.assertIsNotNone(out, f"{ctx}, Message: {err}")
      self.assertIsInstance(out, Function_Call_Data, ctx)
      assert out is not None
      
      self.assertEqual(out.name, exp_func_name, ctx)
      self.assertListEqual(out.args, exp_args, ctx)
      self.assertDictEqual(out.kwargs, exp_kwargs, ctx)

   def __sad(self, input:str):
      ctx = f"Input: <|{input}|>"
      out, err = parse_function(input)
      self.assertIsNone(out, ctx)
      self.assertTrue(err, ctx)

   def test_no_params(self):
      self.__happy('add_text()', 'add_text', [], {})
   def test_simple_case(self):
      self.__happy('add_text("Hello,", " sailor!")', 'add_text', ['"Hello,"', '" sailor!"'], {})
   def test_mixed_args(self):
      self.__happy('add_text("Hello,", second=" sailor!")', 'add_text', ['"Hello,"'], {"second": '" sailor!"'})
   def test_kwargs(self):
      self.__happy('add_text(first="Hello,", second=" sailor!")', 'add_text', [], {"first": '"Hello,"', "second": '" sailor!"'})
   def test_out_of_order_kwargs(self):
      self.__happy('add_text(second=" sailor!", first="Hello,")', 'add_text', [], {"first": '"Hello,"', "second": '" sailor!"'})

   def test_no_params_with_prefix(self):
      self.__happy('PREFIX.add_text()', 'PREFIX.add_text', [], {})
   def test_simple_case_with_prefix(self):
      self.__happy('PREFIX.add_text("Hello,", " sailor!")', 'PREFIX.add_text', ['"Hello,"', '" sailor!"'], {})
   
   def test_single_quote_in_double_quote(self):
      self.__happy('create_location("A great sprawling city", "Eldrida\'s Pride")', 'create_location', ['"A great sprawling city"', '"Eldrida\'s Pride"'], {})
   
   def test_example_1(self):
      self.__happy("""speak_npc_to_player("I'm glad to meet you. I am Gilda, the manager of the Whisperwind Village Inn. What brings you here today?")""", "speak_npc_to_player", ['''"I'm glad to meet you. I am Gilda, the manager of the Whisperwind Village Inn. What brings you here today?"''',], {})
   
   def test_mismatched_quotes(self):
      self.__sad('add_text("this is some text", "a mistmatched string)')
   def test_arg_after_kwarg(self):
      self.__sad('add_text(first="Hello,", " sailor!")')

if __name__ == "__main__":
   unittest.main()
