
# State

The game at any point in time will be in 1 of many possible global states. The current state dictates what kind of prompt the LLM is provided, along with the possible actions it can take. Some of those actions prompt a state transition to switch the current global state.

## Hub States

The game world is comprised of "hubs" where the player can peacefully interact with other characters. The term hub is an abstract one, and the LLM is prompted to create a more suitable name given the world background. For a fantasy world, "town" would be the most appropriate name for a hub. The LLM is provided context based on the current hub, so switching hubs will exclude it from previous hub specific details, but returning to a previously visited hub will re-inject that context.

#### Idle in Hub

The player is prompted for what they would like to do, allowing them to probe various information about their surroundings. Their exact location (e.g. "in a tavern") is implied from the context window.

This state provides a lot of state transition options since they can do anything within the hub or request to leave it.

#### Talk to Hub Character




