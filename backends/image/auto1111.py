from common import logger

from . import Image_Backend, Image_Registry

import requests, base64 # type: ignore
from io import BytesIO
from PIL import Image


class Automatic1111(Image_Backend):
   url: str

   def __init__(self, url:str):
      self.url = url

   def generate_image(self, prompt:str, filepath:str) -> None:
      payload = {
         "width": 768,
         "height": 1024,
         "cfg_scale": 7.0,
         "steps": 20,
         "sampler_index": "Euler a",
         "prompt": f"high fantasy, portrait, {prompt}, pixel art <lora:pixelbuildings128-v1:1>"
      }
      response = requests.post(
         f"{self.url}/sdapi/v1/txt2img",
         headers={"Content-Type":"application/json"},
         json=payload,
      )

      if response.status_code == 200:
         data = response.json()
         
         img_b64 = data['images'][0]
         if ',' in img_b64:
            img_b64 = img_b64.split(',')[1]

         img_bytes = base64.b64decode(img_b64)
         img = Image.open(BytesIO(img_bytes))
         img.save(filepath)
      else:
         for line in response.text.split("\n"):
            logger.error(line)
         raise RuntimeError("Got back non-200 code from image API")

Image_Registry.add("auto1111", Automatic1111)
