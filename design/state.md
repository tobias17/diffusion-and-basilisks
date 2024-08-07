
# State

The game at any point in time will be in 1 of many possible global states. The current state dictates what kind of prompt the LLM is provided, along with the possible actions it can take. Some of those actions prompt a state transition to switch the current global state.


## Hub States

The game world is comprised of "hubs" where the player can peacefully interact with other characters. The term hub is an abstract one, and the LLM is prompted to create a more suitable name given the world background. For a fantasy world, "town" would be the most appropriate name for a hub. The LLM is provided context based on the current hub, so switching hubs will exclude it from previous hub specific details, but returning to a previously visited hub will re-inject that context.

#### Idle in Hub

The player is prompted for what they would like to do, allowing them to probe various information about their surroundings. Their exact location (e.g. "in a tavern") is implied from the context window.

This state provides a lot of state transition options since they can do anything within the hub or request to leave it.

#### Talk to Hub Character

A new character is created or an existing one is assumed for the player to talk with. In this, the player is able to talk directly to the character (which the LLM is playing the role of) and can request various things. While the LLM can roleplay as the character and say anything they want back, the LLM is limited in the actions they can perform on the character's behalf. These might be things like "sell an item" or "give a quest" that will cause in-game actions to be performed.


## Travel States

The player can be put into various travel states. These could be the player trying to travel from one hub to another, or a player leaving a hub to take on a quest (with the intention of returning to the hub).

#### Talk to Travel Character

A new character (or characters) are created and the player is able to talk with one of them. They can interact with the character, similar to the talk state in the hub, but in the travel version there is an option to transition into combat depending on how the interaction goes.

#### Combat

The player is put into a combat state which has turn based actions and rolls associated.

#### Travel Event

This is a seperate state where, when the player is traveling, they can encounter an event. While it is similar to the Talk to Travel Character state, the user is requested to act in isolation without another character responding back to them.
