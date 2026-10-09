# API feeds

Each feed gets one page in this folder. A page describes the feed's
fields, their meaning and its refresh behavior, and links to its generated
JSON Schema.

The Pydantic models are the single source of truth. These pages never
redefine the contract: when a page and a model disagree, the model wins and
the page is fixed.

Each feed's JSON Schema is exported to `api/schemas/<feed>.schema.json` and
regenerated, with the TypeScript types, by `scripts/contract.sh`.

- [`games.md`](games.md): the games feed.
- [`game-detail.md`](game-detail.md): the game detail feed.
- [`player.md`](player.md): the player feed.
- [`team.md`](team.md): the team feed.
- [`standings.md`](standings.md): the standings feed.
- [`search.md`](search.md): the search feed.
