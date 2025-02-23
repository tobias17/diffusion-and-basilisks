import requests, json # type: ignore
from io import BytesIO
from PIL import Image
import base64

def main():
   endpoint = "http://192.168.1.200:7776/v1"
   headers = {
      "Content-Type": "application/json"
   }
   data = {
      "prompt": "a horse size cat eating a bagel"
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
