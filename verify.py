import argparse, os, json, threading

from backends.ai_backend import AI_Backend

def main():
   parser = argparse.ArgumentParser(prog="Endpoint Verification")
   parser.add_argument('config', type=str, help='Path to config json file')
   parser.add_argument('which', type=str, choices=['image','text','both'])
   args = parser.parse_args()

   config_filepath = os.path.abspath(args.config)
   assert os.path.exists(config_filepath), f"Could not find config file, searched for {config_filepath}"
   with open(config_filepath) as f:
      config_data = json.load(f)
   
   kill_event = threading.Event()

   try:
      ai_backend = AI_Backend(kill_event, config_data["backend"])

      if args.which != "image":
         resp = ai_backend.verify_text_model()
         print(f"Text model response: {resp}")
      
      if args.which != "text":
         img_filepath = "tmp/generated.png"
         ai_backend.verify_image_model(img_filepath)
         print(f"Image model generated: {img_filepath}")
   finally:
      kill_event.set()

if __name__ == "__main__":
   main()
