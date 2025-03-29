from functions import parse_function, Function_Call_Data, match_function, Function, Parameter

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


function_library: List[Function] = [
   Function(lambda: None, "basic_func", Parameter("param1", str), Parameter("param2", str)),
   Function(lambda: None, "mixed_dtypes", Parameter("str_param", str), Parameter("int_param", int), Parameter("bool_param", bool)),
   Function(lambda: None, "default_values", Parameter("pos1", str), Parameter("pos2", str), Parameter("kwarg1", str, default="a"), Parameter("kwarg2", str, default="b"))
]

class Test_Function_Matching(unittest.TestCase):
   def test_basic_pos_match(self):
      call, msg = match_function("basic_func", args=['"a"', '"b"'], kwargs={}, functions=function_library)
      self.assertIsNotNone(call, msg)
   def test_basic_kwarg_match(self):
      call, msg = match_function("basic_func", args=[], kwargs={"param1":'"a"', "param2":'"b"'}, functions=function_library)
      self.assertIsNotNone(call, msg)
   def test_basic_pos_and_kwarg_match(self):
      call, msg = match_function("basic_func", args=['"a"'], kwargs={"param2":'"b"'}, functions=function_library)
      self.assertIsNotNone(call, msg)
   def test_basic_flipped_kwarg_match(self):
      call, msg = match_function("basic_func", args=[], kwargs={"param2":'"b"', "param1":'"a"'}, functions=function_library)
      self.assertIsNotNone(call, msg)

   def test_mixed_dtypes_match(self):
      call, msg = match_function("mixed_dtypes", args=['"some text"', "15", "True"], kwargs={}, functions=function_library)
      self.assertIsNotNone(call, msg)
   def test_bad_int_cast(self):
      call, _ = match_function("mixed_dtypes", args=['"some text"', "t15", "True"], kwargs={}, functions=function_library)
      self.assertIsNone(call)
   def test_bad_bool_cast(self):
      call, _ = match_function("mixed_dtypes", args=['"some text"', "15", "maybe"], kwargs={}, functions=function_library)
      self.assertIsNone(call)

   def test_default_all_values_match(self):
      call, msg = match_function("default_values", args=['"a"', '"b"'], kwargs={}, functions=function_library)
      self.assertIsNotNone(call, msg)
   def test_default_some_values_match(self):
      call, msg = match_function("default_values", args=['"a"', '"b"', '"c"'], kwargs={}, functions=function_library)
      self.assertIsNotNone(call, msg)
   def test_default_no_values_match(self):
      call, msg = match_function("default_values", args=['"a"', '"b"', '"c"', '"d"'], kwargs={}, functions=function_library)
      self.assertIsNotNone(call, msg)
   def test_default_later_value_match(self):
      call, msg = match_function("default_values", args=['"a"', '"b"'], kwargs={"kwarg2":'"d"'}, functions=function_library)
      self.assertIsNotNone(call, msg)

   def test_too_many_pos(self):
      call, _ = match_function("basic_func", args=['"a"', '"b"', '"c"'], kwargs={}, functions=function_library)
      self.assertIsNone(call)
   def test_too_unknown_kwargs(self):
      call, _ = match_function("basic_func", args=[], kwargs={"param1":'"a"', "param2":'"b"', "param3":'"c"'}, functions=function_library)
      self.assertIsNone(call)
   def test_pos_kwarg_overlap(self):
      call, msg = match_function("basic_func", args=['"a"', '"b"'], kwargs={"param2":'"b"'}, functions=function_library)
      self.assertIsNone(call)
   def test_function_not_found(self):
      call, _ = match_function("other_func", args=['"a"', '"b"'], kwargs={}, functions=function_library)
      self.assertIsNone(call)


if __name__ == "__main__":
   unittest.main()
