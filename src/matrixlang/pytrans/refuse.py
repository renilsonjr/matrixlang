"""What the translator will not do, and how it says so.

A refusal is the point of this package, not its failure mode. MatrixLang is
missing most of Python on purpose, so a translator that tried to cover
everything would have to invent semantics -- and a program that runs and
means something slightly different is the one outcome worth engineering
against. Every refusal therefore carries a position and, where MatrixLang
has an idiom, the thing to write instead.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Refusal:
    reason: str
    line: int
    column: int
    idiom: str | None = None


@dataclass(frozen=True)
class Refusals:
    items: list[Refusal]


@dataclass(frozen=True)
class Translated:
    source: str


class _Unsupported(Exception):
    """One construct the translator will not touch.

    Carries a fully-formed Refusal rather than a bare message. Unlike
    values.CyclicValue and its siblings -- which are position-less because
    values.py has no positions to give -- the Python AST node this comes
    from knows exactly where it is, so there is nothing to reconstruct
    higher up. Raised deep in the walk, caught once per statement so the
    walk can continue and collect the rest.
    """

    def __init__(self, refusal: Refusal) -> None:
        super().__init__(refusal.reason)
        self.refusal = refusal
