from common import logger

from . import Image_Backend, Image_Registry

import requests, json, base64 # type: ignore
from io import BytesIO
from PIL import Image


class Tinyapi_Image(Image_Backend):
   url: str

   def __init__(self, url:str):
      self.url = url

   def generate_image(self, prompt:str, filepath:str) -> None:
      response = requests.post(
         f"{self.url}/txt2img",
         headers={"Content-Type":"application/json"},
         json={"prompt":f"high fantasy, portrait, {prompt}, pixel art"}
      )

      if response.status_code == 200:
         body = response.text.split(":", 1)[-1].strip()
         try:
            data = json.loads(body)
         except Exception as ex:
            print(f"Failed to load json data:\n{body}")
            raise ex from ex
         image_b64 = data["image"]
         image = Image.open(BytesIO(base64.b64decode(image_b64)))
         image.save(filepath)
      else:
         for line in response.text.split("\n"):
            logger.error(line)
         raise RuntimeError("Got back non-200 code from image API")

Image_Registry.add("tinyapi", Tinyapi_Image)
