from . import Image_Backend, Image_Registry

from typing import Tuple
from PIL import Image
import re


MODEL_NAME, MODEL_URL = "juggernaut_xl.safetensors", "https://huggingface.co/RunDiffusion/Juggernaut-XL/resolve/main/juggernautXL_version2.safetensors?download=true"


def remap_lora_weight_name(name:str) -> str:
   name = re.sub(r'_', '.', name)
   name = re.sub(r'lora\.unet\.', 'model.diffusion_model.', name)
   name = re.sub(r'put\.blocks', 'put_blocks', name)
   name = re.sub(r'\.middle\.block\.', '.middle_block.', name)
   name = re.sub(r'\.to\.', '.to_', name)
   name = re.sub(r'\.transformer\.blocks\.', '.transformer_blocks.', name)
   name = re.sub(r'\.proj\.in\.', '.proj_in.', name)
   name = re.sub(r'\.proj\.out\.', '.proj_out.', name)
   return name

def load_lora_onto_(model) -> None:
   from tinygrad.helpers import fetch
   from tinygrad.nn.state import get_state_dict, safe_load

   model_state_dict = get_state_dict(model)
   lora_state_dict  = safe_load(str(fetch("https://huggingface.co/nerijs/pixel-art-xl/resolve/main/pixel-art-xl.safetensors?download=true", "pixel-art-xl.safetensors")))

   remapped_state_dict = {}
   for k, w in lora_state_dict.items():
      remapped_state_dict[remap_lora_weight_name(k)] = w

   seen_names = set()
   for mapped_name, w in remapped_state_dict.items():
      if mapped_name.endswith(".alpha"):
         continue
      base_name = re.sub(r'\.lora\.(down|up)', '', mapped_name)
      if base_name in seen_names:
         continue
      seen_names.add(base_name)

      model_weight = model_state_dict.get(base_name, None)
      if model_weight is None:
         print(f"PANIC: missing model weight for lora application: {base_name}")
         continue

      try:
         def move(x): return x.to(model_weight.device).cast(model_weight.dtype)
         up_weight   = move(remapped_state_dict[re.sub(r'\.lora\.(down|up)',   '.lora.up',   mapped_name)])
         down_weight = move(remapped_state_dict[re.sub(r'\.lora\.(down|up)',   '.lora.down', mapped_name)])
         alpha       = move(remapped_state_dict[re.sub(r'\.lora\.(down|up).+', '.alpha',     mapped_name)])

         lora_contribution = (up_weight @ down_weight) * (alpha / down_weight.shape[0])
         model_weight.replace((model_weight + lora_contribution).realize())
      except KeyError as ex:
         print(f"Failed when running mapped_name: {mapped_name}")
         print(f"Failed when running base_name:   {base_name}")
         raise ex from ex


class Tinybox_Image(Image_Backend):
   url: str

   def __init__(self, device_idx, guidance_scale:float, img_width:int, img_height:int, num_steps:int):
      from tinygrad import Device, Context
      from tinygrad.helpers import fetch
      from tinygrad.nn.state import get_parameters, load_state_dict, safe_load
      from examples.sdxl import SDXL, configs, DPMPP2MSampler # type: ignore

      if isinstance(device_idx, int):
         device = f"{Device.default}:{device_idx}"
      else:
         raise ValueError("Multi-tensor SDXL is not supported yet")

      self.model = SDXL(configs["SDXL_Base"])
      default_weight_url = MODEL_URL
      weights = str(fetch(default_weight_url, MODEL_NAME))

      with Context(BEAM=0):
         assert isinstance(device, str), f"Multi device image generation not yet supported"
         for w in get_parameters(self.model):
            w.to_(device)

      load_state_dict(self.model, safe_load(weights), strict=False)
      load_lora_onto_(self.model)

      self.sampler    = DPMPP2MSampler(guidance_scale)
      self.img_width  = img_width
      self.img_height = img_height
      self.num_steps  = num_steps

      self.generate_image("a horse size cat eating a bagel", "/tmp/generated.png", warmup_decoder=True)

   def generate_image(self, prompt:str, filepath:str, warmup_decoder:bool=False) -> None:
      from tinygrad import Tensor, TinyJit, dtypes
      from tinygrad.helpers import tqdm

      @TinyJit
      def make_noise_image(shape:Tuple[int,...]) -> Tensor:
         return Tensor.randn(shape).realize()

      @TinyJit
      def decode_step(model, z:Tensor) -> Tensor:
         return model.decode(z).realize()
      
      N = 1
      C = 4
      F = 8

      c, uc = self.model.create_conditioning([prompt], self.img_width, self.img_height)
      for v in c .values(): v.realize()
      for v in uc.values(): v.realize()

      shape = (N, C, self.img_height // F, self.img_width // F)
      if warmup_decoder:
         for _ in range(2):
            make_noise_image(shape)
      randn = make_noise_image(shape)

      z = self.sampler(self.model.denoise, randn, c, uc, self.num_steps)
      if warmup_decoder:
         print("Warming up decoder")
         for i in tqdm(range(3), disable=(not warmup_decoder)):
            decode_step(self.model, (z * (i+2)).realize())
      x = decode_step(self.model, z.realize())
      x = (x + 1.0) / 2.0
      x = x.reshape(3,self.img_height,self.img_width).permute(1,2,0).clip(0,1).mul(255).cast(dtypes.uint8)

      Image.fromarray(x.numpy()).save(filepath)


Image_Registry.add("tinybox", Tinybox_Image)
