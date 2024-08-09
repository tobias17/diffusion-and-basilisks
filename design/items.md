
# Items

The game has an explicit item mechanism. The LLM is able to give items to the user and take them away.

The channel for adding or removing items from the player's inventory follows a strict API getting called. Besides the simple `add()` and `remove()` there is a `use_item(consume=True)`.

Certain actions will be gated behind the usage of items. The `use_item()` has a consume option to destroy the item, but this is not required. For example, the usage of a torch to light thing up an area would not consume the torch, but inserting a coin into a machine would. Besides enabling better state handling, it also guiderails the LLM into following the rules more. If they try to use an API on a non-existant item, the game engine could repeat the prompt with the LLM's previous answer followed by an error message and query to retry.
