"""Router v2 pure cascade modules (see the router design spec).

Every module here is pure: no I/O, no clock, no environment, no process
spawning. `overrides` (the named-capability detector) is committed first and
its digest is recorded in the benchmark seal.
"""
