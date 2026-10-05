# API feeds

Each feed gets one page in this folder. A page describes the feed's
fields, their meaning and its refresh behavior, and links to its generated
JSON Schema.

The Pydantic models are the single source of truth. These pages never
redefine the contract: when a page and a model disagree, the model wins and
the page is fixed.

The location of the exported JSON Schema is defined when the first feed is
added (pending). There are no feed pages yet.
