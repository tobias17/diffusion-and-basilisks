from functions import parse_function, Function_Call_Data

from typing import List, Dict
import unittest

def parse_function_helper():
   pass
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


# function_pool = [
#    Function((lambda s,a,b: a+b), "add_text", "", Parameter("first",str), Parameter("second",str)),
#    Function((lambda s,a,b: a+b), "add_nums", "", Parameter("a",int), Parameter("b",int))
# ]

# class Test_Match_Function(unittest.TestCase):
   
#    def __happy(self, func_name:str, args:List, kwargs:Dict, expected_output):
#       call, err = match_function(func_name, args, kwargs, function_pool)
#       self.assertIsNotNone(call, err)
#       assert call is not None
#       out = call(None)
#       self.assertEqual(out, expected_output)
   
#    def __sad(self, func_name:str, args:List, kwargs:Dict):
#       call, err = match_function(func_name, args, kwargs, function_pool)
#       self.assertIsNone(call, "Expected output to fail but got non-None value back")
#       self.assertTrue(err, "Got None back but error message was empty")

#    def test_simple_cast(self):
#       self.__happy("add_text", ('"Hello,"', '" sailor!"'), {}, "Hello, sailor!")
#    def test_int_cast(self):
#       self.__happy("add_nums", ("5", "7"), {}, 12)
#    def test_negative_int_cast(self):
#       self.__happy("add_nums", ("-5", "7"), {}, 2)
#    def test_pos_and_kwargs_mix(self):
#       self.__happy("add_nums", ("5"), {"b": "7"}, 12)
   
#    def test_bad_int_cast(self):
#       self.__sad("add_nums", ("5", "7.8"), {})
#    def test_kwarg_before_pos_arg(self):
#       self.__sad("add_nums", ("5"), {"a": "7"})

if __name__ == "__main__":
   unittest.main()
