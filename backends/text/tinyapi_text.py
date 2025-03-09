from common import logger

from . import Text_Backend, Text_Registry

from typing import List, Dict
import requests, json # type: ignore


class Tinyapi_Text(Text_Backend):
   url: str

   def __init__(self, url:str):
      self.url = url

   def generate_response(self, messages:List[Dict[str,str]]) -> str:
      resp = requests.post(
         f"{self.url}/chat/completions",
         headers={"Content-Type":"application/json"},
         json={"messages":messages}
      )

      if resp.status_code == 200:
         body = resp.text.split(":", 1)[-1].strip()
         try:
            data = json.loads(body)
         except Exception as ex:
            logger.error(f"Failed to load json data:\n{body}")
            raise ex from ex
         return data["choices"][0]["message"]["content"] # type: ignore
      else:
         logger.info(f"Got back: {resp.text}")
         raise RuntimeError(f"Endpoint returned non-200 status code {resp.status_code}")

Text_Registry.add("tinyapi", Tinyapi_Text)
