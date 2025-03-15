# Endpoints Setup

This page will go over how to set up non-tinybox endpoints to play the game.

We will be using the `configs/endpoints.json` file as our starting point, feel free to modify it or make multiple copies / versions to experiment with.

## Text Endpoint

This is a simple OpenAI endpoint. While in my testing I used the actual OpenAI API, this API format is a standard for most LLM text endpoints so you can use whatever provider you wish (including various self hosting with apps like LM Studio).

You will need to create a `.env` file in the root of the project and fill in the following:
```
OPENAI_API_KEY=<insert-your-key-here>
```
Where you fill in the API key from your provider.

**REMINDER:** API keys are secrets and should never be shared.

## Image Endpoint

For this we will be using the automatic1111 webui to host an image model locally.
```
git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git
```

Download the following models into these locations within the stable-diffusion-webui repo:
| Save into this folder | Link |
| :- | :- |
| models/Stable-diffusion | https://huggingface.co/RunDiffusion/Juggernaut-XL-v9/resolve/main/Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors |
| models/LoRA | https://huggingface.co/nerijs/pixel-art-xl/resolve/main/pixel-art-xl.safetensors |

Modify the `webui-user.bat` file to add the following
```
set COMMANDLINE_ARGS=--api
```

If your GPU has less than 12 GB of VRAM then I suggest also adding the --medvram flag
```
set COMMANDLINE_ARGS=--api --medvram
```
There is also a `--lowvram` option if this still is not enough, but it is a decent bit slower so only use it if you need it.

Just run the `webui-user.bat` to launch the server. You might need to select the model the first time you do this in the top left of the UI. Once things have been verified you are free to close the webpage, just make sure to keep the terminal open while you want to play the game.

## Verifying the Config

There is a verification script that will test these endpoints to ensure they are correctly configured.
```
python verify.py <config> (text|image|both)
```

The first argument `<config>` is the path to your config JSON file, so something like `configs/endpoints.json`.

The second argument is which endpoint you want to test, or both to test both.

For example, one might call the script like the following:
```
python verify.py configs/endpoints.json both
```
Which would verify the `endpoitns.json` config for both image and text generation.
