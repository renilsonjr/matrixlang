"""A local server for Operator. Not part of the `matrixlang` package.

Deliberately outside `src/matrixlang/`: the language does not depend on
this, and `pip install matrixlang` does not ship it. Run it from a clone:

    python -m server

Standard library only — `http.server` plus Server-Sent Events. The two
flows this needs are a POST for chat and a one-directional stream of
execution events, and SSE is the boring HTTP answer to the second. A
websocket framework would buy bidirectional messaging that nothing here
sends.
"""
