# Diffusion and Basilisks

A fantasy adventure game with realtime-generated content using AI (LLM + SDXL).

Currently designed to be run on a tinybox, will add mechanisms to run with other hosting soon.

## For Tinybox Users

First set up a server on your tinybox.
```
git clone https://github.com/tobias17/tinyapi.git
tinyapi/run.sh
```
This will take a little while to download the model weights and run a beam search (default BEAM=1).

Don't worry about having an existing tinygrad clone, it will automatically submodule a custom version and set the python path for it.

Once the server is running, playing is simple.
```
https://github.com/tobias17/diffusion-and-basilisks.git
diffusion-and-basilisks/run.sh
```

## For Other Users

We now support alternative backends using OpenAI endpoints and Automatic1111 webui API.

See the [Endpoints Setup Page](docs/endpoints_setup.md) for instructions to set this up.

## Controls

| Input | Description |
| -: | :- |
| & | End your input with & to enter multiple inputs |
| Ctrl+C | Stop the game |
| Ctrl+R | Reload the screen |
| Escape | Brings up the menu items |
| Up/Down Arrows | Scroll the page up/down by 1 |
| Page Up/Down | Scroll the page up/down by 50% |

## Tips

- Make sure to enjoy the game, this part is vital to having a good experience

## Future Plans

- Add combat events so it doesn't feel hollow
- An actual character creator with more starting location variety
- The `user_controller.py` file is a mess and needs to be refactored
- Better "model failed" handling, rejecting last user input is kinda hacky
- The way events are defined currently has a lot of copy-paste, could be compacted more
