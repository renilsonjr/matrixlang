"""Operator — the assistive companion, isolated from the language.

Nothing in `src/matrixlang/` outside this package may import it. The
interpreter and the parser must stay runnable with no SDK installed, no
key configured and no network reachable — asserted in
`tests/test_architecture.py` rather than left as a convention.

The package is named `operator` after the role in the films, which shadows
Python's stdlib module of the same name. Harmless under absolute imports —
`import operator` anywhere still resolves to the standard library, and a
test pins that — but worth knowing before it surprises somebody.
"""
