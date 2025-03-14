from common import logger

from . import Text_Backend, Text_Registry

from typing import List, Dict, Optional
import os
from openai import OpenAI

class OpenAI_Endpoint(Text_Backend):
   SHOULD_PREFILL: bool = False # This will eat tokens with no real benefit for this endpoint if enabled, DONT DO
   client: OpenAI
   model: str
   url: str

   def __init__(self, model:str, url:Optional[str]=None):
      self.url = url
      self.client = OpenAI(base_url=url, api_key=self.__load_api_key())
      self.model = model

   def __load_api_key(self) -> str:
      start = "OPENAI_API_KEY="
      env_filepath = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
      assert os.path.isfile(env_filepath), f"Could not find a .env file, make sure there is one at the root of the repo with your API key"
      with open(env_filepath) as f:
         for line in f.read().split("\n"):
            line = line.replace(" ", "")
            if line.startswith(start):
               return line.replace(start, "", 1)
      raise ValueError(f"Failed to find api key, make sure a line in your .env file starts with {start}")

   def generate_response(self, messages:List[Dict[str,str]], max_tokens:Optional[int]=None) -> str:
      completion = self.client.chat.completions.create(
         model=self.model,
         messages=messages,
      )
      return completion.choices[0].message.content

Text_Registry.add("openai", OpenAI_Endpoint)
