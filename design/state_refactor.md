## Overview

Right now, there is way too much being thrown at the model for it to handle. It does not really understand what it needs to do, and is easy for it to make a mistake.

The testing of "recovery" have gone abysmal. I have yet to see a model recover from a bad initial response with a loop count of 3 (meaning it has 2 attempts at fixing it's mistake).

Most of the initial failures come from the model trying to do too many things at a time, many of which it doesn't need to do (e.g. trying to create a town that already exists).

#### Narrow the Scope of Actions
- The model did not understand what "hub" meant and "location" was way too broad for it
- Stick to "town" and deal with expanding later

#### More but Focused States
- States are very broad right now, allowing for many options to be taken
- Ideally should only have a few options in each state, but easy for state transition

#### Introduce MicroEvents (?)
- Right now the model needs to both declare intent AND fill out the details
   - How the details are filled out are dependant on prompting
   - Not realistic to add tons of details for every possible actions, bloats context
- Make actions purely drive intent
   - Once intent is relayed, THEN give larger context to describe instructions
   - Instead of `create_npc(name, backstory, description)`, call `created_npc()` and then provide parameters prompt
