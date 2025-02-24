import requests, json # type: ignore
from io import BytesIO
from PIL import Image
import base64

# PROMPT_PREFIX = "high fantasy aesthetic, colorful, minimalist, clean lines, simple structure, "
# PROMPT_PREFIX = "colorful, minimalist, simple structure, flat shading, missing details, dark background, bright subject"
PROMPT_PREFIX = "high fantasy, portrait, "
PROMPT_SUFFIX = " pixel art, clothed"

PROMPT_BODY = "A charming seaside town centered around an ancient gnarled oak tree with massive spreading branches in the town square."
# PROMPT_BODY = "A burly man with a thick beard and a friendly smile."
# PROMPT_BODY = "A lively tavern filled with the sound of rowdy patrons and the scent of roasting meats. The air is thick with smoke and the clatter of tankards."

def main():
   endpoint = "http://192.168.1.200:7776/v1"
   headers = {
      "Content-Type": "application/json"
   }
   data = {
      "prompt": PROMPT_PREFIX + PROMPT_BODY + PROMPT_SUFFIX
   }
   response = requests.post(
      f"{endpoint}/txt2img",
      headers=headers,
      json=data,
      stream=True
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
      image.show()
   else:
      print(response.text)

main()
