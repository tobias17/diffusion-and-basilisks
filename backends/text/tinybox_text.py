from . import Text_Backend, Text_Registry

from typing import Dict, Tuple, Set, List, Optional, Union
from dataclasses import dataclass, field
import re, json
from pathlib import Path

variable_pattern = re.compile(r"%%([^%]+)%%")
@dataclass
class Prompt:
   system_message: str
   user_message: str
   assistant_prefix: str
   assistant_suffix: str
   eos_texts: Tuple[str,...]
   eos_tokens: Set[int] = field(default_factory=lambda: set())

   def __sub_text(self, text:str, tokenizer) -> str:
      while True:
         m = variable_pattern.search(text)
         if not m: return text
         value = tokenizer.special_tokens_map.get(key := m.group(1), None)
         assert value is not None, f"Failed to find key '{key}' in special_tokens_map, options were {list(tokenizer.special_tokens_map.keys())}"
         text = text.replace(f"%%{key}%%", value)

   def sub_vars(self, tokenizer) -> 'Prompt':
      self.system_message   = self.__sub_text(self.system_message,   tokenizer)
      self.user_message     = self.__sub_text(self.user_message,     tokenizer)
      self.assistant_prefix = self.__sub_text(self.assistant_prefix, tokenizer)
      self.assistant_suffix = self.__sub_text(self.assistant_suffix, tokenizer)

      for text in self.eos_texts:
         text = self.__sub_text(text, tokenizer)
         token = tokenizer.encode(text, add_special_tokens=False)
         assert len(token) == 1, f"Text '{text}' encoded into tokens {token}, expected exactly 1 token value"
         self.eos_tokens.add(token[0])
      
      return self

@dataclass
class ModelArchitecture:
   config: 'ModelConfig' # type: ignore
   weights_url: str
   weights_subdir: str
   num_weights: int
   prompt: Prompt
   default_system_prompt: str = "You are an helpful assistant."
   index_filename: str = "model.safetensors.index.json"
   chunk_filename: str = "model-{i:05d}-of-{num_weights:05d}.safetensors"
   extra_filenames: List[str] = field(default_factory=lambda: ["tokenizer.json", "tokenizer_config.json"])
   permute_layers: bool = True

def concat_weights(models, device):
   def convert(name):
      disk_tensors = [model[name] for model in models]
      if len(disk_tensors) == 1 or len(disk_tensors[0].shape) == 1:
         return disk_tensors[0].to(device=device)
      axis = 1 if name.endswith(".attention.wo.weight") or name.endswith(".feed_forward.w2.weight") else 0
      lazy_tensors = [data.to(device=device) for data in disk_tensors]
      return lazy_tensors[0].cat(*lazy_tensors[1:], dim=axis)
   return {name: convert(name) for name in {name: None for model in models for name in model}}

def load_item(fn:str):
   from tinygrad.nn.state import safe_load, torch_load
   if fn.endswith('.index.json'):
      with open(fn) as fp: weight_map = json.load(fp)['weight_map']
      parts = {n: load_item(str(Path(fn).parent / Path(n).name)) for n in set(weight_map.values())}
      return {k: parts[n][k] for k, n in weight_map.items()}
   elif fn.endswith(".safetensors"):
      return safe_load(fn)
   else:
      return torch_load(fn)

def build_transformer(arch:ModelArchitecture, device):
   from tinygrad import Context, dtypes
   from tinygrad.helpers import fetch
   from tinygrad.nn.state import load_state_dict, get_state_dict
   from transformers import AutoTokenizer # type: ignore
   from extra.models.llama import Transformer, convert_from_huggingface, fix_bf16 # type: ignore

   # download weights
   def download(filename:str) -> Path:
      return fetch(f"{arch.weights_url}/{filename}", filename, subdir=arch.weights_subdir)
   model_path = download(arch.index_filename)
   for i in range(1, arch.num_weights+1):
      download(arch.chunk_filename.format(i=i, num_weights=arch.num_weights))
   for filename in arch.extra_filenames:
      download(filename)

   # load tokenizer
   tokenizer = AutoTokenizer.from_pretrained(str(model_path.parent))

   # build model
   cfg = arch.config
   model = Transformer(cfg)

   # load weights
   if model_path.is_dir():
      if (model_path / "model.safetensors.index.json").exists(): weights = load_item(str(model_path / "model.safetensors.index.json"))
      elif (model_path / "model.safetensors").exists(): weights = load_item(str(model_path / "model.safetensors"))
      else: weights = concat_weights([load_item(str(model_path / f"consolidated.{i:02d}.pth")) for i in range(arch.num_weights)], device[0] if isinstance(device, tuple) else device)
   else:
      weights = load_item(str(model_path))
   if "model.embed_tokens.weight" in weights:
      assert cfg.n_kv_heads is not None
      weights = convert_from_huggingface(weights, model, cfg.n_heads, cfg.n_kv_heads, permute_layers=arch.permute_layers)
   weights = fix_bf16(weights)

   with Context(BEAM=0):
      # shard
      if isinstance(device, tuple):
         def get_shard_axis(k:str) -> Optional[int]:
            if '.attention.' in k: return -1
            if '.feed_forward.w1.' in k: return 0
            if '.feed_forward.w3.' in k: return 0
            if '.feed_forward.' in k: return -1
            if 'tok_embeddings.weight' in k: return 0
            if 'output.weight' in k: return 0
            return None
         for k,v in get_state_dict(model).items():
            v.replace(v.cast(dtypes.float16).shard(device, axis=get_shard_axis(k)))

      # replace weights in model
      load_state_dict(model, weights, strict=False, consume=True)
   
   return model, tokenizer


class Tinybox_Text(Text_Backend):
   url: str
   device: Union[str,Tuple[str,...]]

   def __init__(self, device_idx, max_tokens:int, beam_value:int):
      from tinygrad import Tensor, Context, Device
      from extra.models.llama import ModelConfig, TokenSampler
      Tensor.no_grad = True

      arch = ModelArchitecture(
         config=ModelConfig(dim=5120, hidden_dim=32768, n_layers=40, n_heads=32, head_dim=128, n_kv_heads=8, norm_eps=1e-5, vocab_size=131072, rope_theta=100000000.0, max_context=32768),
         weights_url="https://huggingface.co/mistralai/Mistral-Small-24B-Instruct-2501/resolve/main",
         weights_subdir="mistral_small_24b_instruct",
         num_weights=10,
         prompt=Prompt("<s>[SYSTEM_PROMPT]{0}[/SYSTEM_PROMPT]", "[INST]{0}[/INST]", "", "</s>", ("</s>",)),
         default_system_prompt="You are an helpful assistant. Keep answers short and direct.",
      )

      self.SAMPLER = TokenSampler(
         temperature=0.95,
         top_k=0,
         top_p=0.0,
         alpha_f=0.0,
         alpha_p=0.0,
      )

      with Context(BEAM=0):
         if isinstance(device_idx, int):
            self.device = f"{Device.DEFAULT}:{device_idx}"
         else:
            assert isinstance(device_idx, (list,tuple))
            self.device = tuple(f"{Device.DEFAULT}:{i}" for i in device_idx)
         self.model, self.tokenizer = build_transformer(arch, self.device)

      self.p = arch.prompt.sub_vars(self.tokenizer)
      assert len(self.p.eos_tokens) > 0

      self.max_tokens = max_tokens
      self.beam_value = beam_value
      self.generate_response([{"role":"system", "content":"This is a test message to warmup the model"}], True)

   def encode_messages(self, messages:List[Dict]) -> List[int]:
      text = ""
      for msg in messages:
         if msg["role"] == "system":
            text += self.p.system_message.format(msg["content"])
         elif msg["role"] == "user":
            text += self.p.user_message.format(msg["content"])
         elif msg["role"] == "assistant":
            text += self.p.assistant_prefix + msg["content"] + self.p.assistant_suffix
         else:
            raise KeyError(f"Got unknown role key '{msg['role']}'")
      return self.tokenizer.encode(text, add_special_tokens=False)

   def generate_response(self, messages:List[Dict[str,str]], warmup:bool=False) -> str:
      from tinygrad import Context

      MAX_NEW_TOKENS = 1 if warmup else self.max_tokens
      count = 0

      tokens = self.encode_messages(messages)
      new_tokens = []

      while True:
         with Context(BEAM=self.beam_value):
            tok = self.model(tokens, self.device, self.SAMPLER)
         tokens.append(tok)
         new_tokens.append(tok)
         count += 1
         if count >= MAX_NEW_TOKENS:
            break
         if tok in self.p.eos_tokens:
            break

      return self.tokenizer.decode(new_tokens)


Text_Registry.add("tinybox", Tinybox_Text)
