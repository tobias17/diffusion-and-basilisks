# Diffusion and Basilisks

A realtime-generated video game designed to be played on a tinybox through an SSH.

Right now this repo is in the initial development phase.

The basic structure of how this game operates are being fleshed out, but here is the current jist:
- The game state is modified by an append-only list of Events
- Game state is interpreted from this list of Events

Most components are designed around being testable at various levels.
- Functions with very rigid inputs and outputs are unit tested
- Functions that have subjective inputs and outputs are injection tested with detailed and source controlled outputs
- Functions subject to LLM interactions have prompt testing where inputs are fed to the LLM multiple times and the results saved off
