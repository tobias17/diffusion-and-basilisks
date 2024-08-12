
# Saving and Loading the Game

Goals of the system
1. Able to be stored and loaded in human-readable form.
2. Manual modification to the game state should be simple and smooth.
3. State should be viewable as a sequence based on order.

## Proposal 1

Everything is stored in database style, where you can index a hub to get it's converstations and you are greeted with the full list. To achieve the sequence based view each element would get an ID that is used in the sequence ordering. This feels kinda messy since you are trying to piece together an ordering from a current state.

## Proposal 2

More like a git history, the sequence ordering is the primary driver of state storage. To resolve questions like "what is the full converstation with a character" one would go through the full sequence and collect the answer along the way. This is nice since we have a fully computable "state" given a sequence range. One might be tempted to create a cached state that avoids these lookups, and while that would be nice, it's a lot of effor with lots of potential for bugs for a speed improvement, but this project is not at the point where that tradeoff is anywhere close to worth it.
