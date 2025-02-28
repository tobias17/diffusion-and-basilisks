from common import Event
from typing import List, Dict, Optional, Type, Callable, Tuple, Any
from dataclasses import dataclass
import re



#######################
### Data Structures ###
#######################

@dataclass
class Parameter:
   name: str
   dtype: Type
   default: Optional[str] = None
   def render(self) -> str:
      return f"{self.name}:{self.dtype.__name__}" + (f"={self.default}" if self.default is not None else "")

class Function:
   call: Callable
   name: str
   params: List[Parameter]
   def __init__(self, call:Callable, name:str, *params:Parameter):
      self.call = call
      self.name = name
      self.params = list(params)
   def render(self) -> str:
      return f"{self.name}({', '.join(p.render() for p in self.params)})"
   def system(self, event:Event) -> Optional[str]:
      items = []
      for p in self.params:
         value = getattr(event, p.name)
         if value is None:
            raise RuntimeError(f"Could not extract attribute '{p.name}' out of {event}")
         items.append(f"{p.name}=" + (f'"{value}"' if p.dtype is str else str(value)))
      return f"{self.name}({', '.join(items)})"

class Function_Map:
   funcs: List[Function] = []

   @staticmethod
   def get(function_name:str) -> Tuple[Optional[Function],str]:
      funcs = [f for f in Function_Map.funcs if f.name == function_name]
      if len(funcs) == 0:
         return None, f"Failed to find a function with name '{function_name}'"
      if len(funcs) > 1:
         return None, f"PANIC: found {len(funcs)} functions with name '{function_name}'"
      return funcs[0], ""

   @staticmethod
   def api_definition() -> str:
      return "\n".join(f.render() for f in Function_Map.funcs)

@dataclass
class Function_Call_Data:
   name: str
   args: List[str]
   kwargs: Dict[str,str]



#######################
### Usage Functions ###
#######################

empty_pattern = re.compile(r'^([a-zA-Z0-9_\.]+)$')
func_pattern  = re.compile(r'^([a-zA-Z0-9_\.]+)\((.*)\)$')

def parse_function(line:str, allow_empty:bool=False) -> Tuple[Optional[Function_Call_Data],str]:
   if "\t" in line: return None, "Function calling blocks cannont contain the \\t character"
   if "\r" in line: return None, "Function calling blocks cannont contain the \\r character"
   special_map = {
      ",": "\t",
      "=": "\r",
   }

   if allow_empty:
      match = empty_pattern.match(line)
      if match:
         return Function_Call_Data(match.group(1), [], {}), ""
   match = func_pattern.match(line)
   if not match:
      return None, "Got bad input, could not parse a function from this"
   func_name   = match.group(1)
   orig_params = match.group(2)
   if len(orig_params) == 0:
      return Function_Call_Data(func_name, [], {}), ""

   cleaned_params = ""
   quote_char = None
   for char in orig_params:
      if quote_char:
         if char == quote_char:
            quote_char = None
      else:
         if char in ("'", '"'):
            quote_char = char
         elif char in special_map:
            cleaned_params += special_map[char]
            continue
      cleaned_params += char
   if quote_char:
      return None, "Got uneven number of quote characters"

   args:   List = []
   kwargs: Dict = {}
   chunks = cleaned_params.split(special_map[","])
   for chunk in chunks:
      pieces = chunk.split(special_map["="])
      if len(pieces) == 1:
         if len(kwargs) > 0:
            return None, "Found position argument after keyword argument"
         args.append(pieces[0].strip())
      elif len(pieces) == 2:
         kwargs[pieces[0].strip()] = pieces[1].strip()
      else:
         return None, "Found too many '=' characters in a single parameter"

   return Function_Call_Data(func_name, args, kwargs), ""


def cast_value(value:str, param:Parameter) -> Tuple[Any,str]:
   if param.dtype is str:
      for quote in ('"', "'"):
         if value.startswith(quote) and value.endswith(quote) and len(value) >= 2:
            return value[1:-1], ""
      return None, f"Paramater '{param.name}' expected string value but failed to find quote characters"
   elif param.dtype is int:
      try:
         return int(value), ""
      except Exception:
         return None, f"Error converting parameter '{param.name}' to an integer"
   elif param.dtype is bool:
      mapping = { "true":True, "false":False }
      x = mapping.get(value.lower(), None)
      if x is None:
         return None, f"Error converting parameter '{param.name}' to an integer"
      return x, ""
   else:
      raise RuntimeError(f"Got Parameter.dtype of '{param.dtype.__name__}' which is not get supported by cast_value()")


def match_function(func_name:str, args:List, kwargs:Dict, functions:List[Function]) -> Tuple[Optional[Callable],str]:
   cleaned_args:   List = []
   cleaned_kwargs: Dict = {}
   for function in functions:
      if func_name == function.name:
         arg_idx = 0
         for param in function.params:
            if arg_idx < len(args):
               value, err = cast_value(args[arg_idx], param)
               if value is None:
                  return None, err
               cleaned_args.append(value)
               arg_idx += 1
            else:
               if param.name in kwargs:
                  value, err = cast_value(kwargs[param.name], param)
                  if value is None:
                     return None, err
                  cleaned_kwargs[param.name] = value
               else:
                  return None, f"Unknown keyword argument '{param.name}' to function '{func_name}'"
         
         if arg_idx < len(args):
            return None, f"Found {len(args)} positional arguments but function '{func_name}' expected only {len(function.params)}"
         for name in kwargs.keys():
            if name not in cleaned_kwargs:
               return None, f"Unexpected keyword argument '{name}' for function '{func_name}'"
         
         return (lambda s: function.call(s, *cleaned_args, **cleaned_kwargs)), ""
   
   return None, f"Could not find function named '{func_name}'"
