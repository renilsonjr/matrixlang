"""`for ... else`, turned into the flag pattern before translation begins.

Python's loop-else runs only when no `break` fired. The way anyone writes
that by hand -- a flag set beside the `break`, tested after the loop --
already translates and runs correctly today, including nested inside
another loop, where `_hoist_declares` lifts the flag out of the loop body
on its own. So there is nothing to teach the translator. This pass writes
the flag, and `_Translator` never learns what a loop-else is.

Python in, Python out, which is what makes it testable with `ast.unparse`
and no translator involved.

Anything this pass declines to rewrite it leaves exactly as it found it,
so the construct keeps the refusal it already had. The descent is
recursive and unguarded; `translate()` is what wraps each statement in a
recursion guard.
"""

import ast

from matrixlang.pytrans.names import free_name

# The reader never wrote this name. Readable rather than mangled, because
# the emitted MatrixLang is what a person reads: `redpill broke == false`
# is a sentence, `redpill _b0 == false` is machine output. free_name keeps
# it off the reader's own names; it is not a MatrixLang keyword.
_FLAG_STEM = "broke"

_BLOCK_FIELDS = ("body", "orelse", "finalbody")

# Task 3 adds ast.While here. Until then a `while ... else` is left
# untouched, which keeps the refusal it already has.
_LOOPS = (ast.For,)


def _suites(statement: ast.stmt):
    """Every statement list this statement carries directly.

    The single place that knows where suites live. `ast.Match` keeps its
    under `cases` and `ast.Try` under `handlers`, neither of which is a
    plain field -- which is exactly the kind of omission that is easy to
    make in one copy of a walk and not another.
    """
    for field in _BLOCK_FIELDS:
        block = getattr(statement, field, None)
        if isinstance(block, list) and all(isinstance(s, ast.stmt) for s in block):
            yield block
    for handler in getattr(statement, "handlers", []):
        yield handler.body
    for case in getattr(statement, "cases", []):
        yield case.body


def rewrite_loop_else(tree: ast.Module, taken: set[str]) -> ast.Module:
    """Replace each loop-else with the flag pattern it means.

    `taken` is the caller's set of names already in use, and the pass's
    running record rather than a snapshot: every flag invented here is
    added to it, so two loop-elses in one program cannot both be `broke`.
    """
    tree.body = _block(tree.body, taken)
    return tree


def _block(statements: list[ast.stmt], taken: set[str]) -> list[ast.stmt]:
    out: list[ast.stmt] = []
    for statement in statements:
        _rewrite_nested_blocks(statement, taken)
        out.extend(_expand(statement, taken))
    return out


def _rewrite_nested_blocks(statement: ast.stmt, taken: set[str]) -> None:
    """Rewrite the suites this statement contains, before touching it.

    Doing this first is what makes nesting work without a rule of its own
    -- see `_expand`.
    """
    for block in _suites(statement):
        block[:] = _block(block, taken)


def _expand(statement: ast.stmt, taken: set[str]) -> list[ast.stmt]:
    """One statement, as the statements it becomes.

    By the time this runs, `_rewrite_nested_blocks` has already removed
    every nested loop's `else` -- so a `break` that used to live in one is
    now in an ordinary `if` at this level, where `_mark` already goes.
    That is why the walk below needs only one rule.
    """
    if not isinstance(statement, _LOOPS) or not statement.orelse:
        return [statement]

    else_body = statement.orelse
    statement.orelse = []
    if not _has_own_break(statement.body):
        # The loop cannot break, so the else always runs. No flag, no
        # guard -- just the else body after the loop.
        return [statement, *else_body]
    flag = free_name(taken, _FLAG_STEM)
    taken.add(flag)
    statement.body = _mark(statement.body, flag)

    start = ast.Assign(
        targets=[ast.Name(id=flag, ctx=ast.Store())],
        value=ast.Constant(value=False),
    )
    # `flag == False`, not `not flag`: MatrixLang has no truthiness, and a
    # bare name as a condition is refused. See the module's plan.
    guard = ast.If(
        test=ast.Compare(
            left=ast.Name(id=flag, ctx=ast.Load()),
            ops=[ast.Eq()],
            comparators=[ast.Constant(value=False)],
        ),
        body=else_body,
        orelse=[],
    )
    return [_at(start, statement), statement, _at(guard, statement)]


def _at(made: ast.stmt, node: ast.stmt) -> ast.stmt:
    return ast.fix_missing_locations(ast.copy_location(made, node))


def _mark(statements: list[ast.stmt], flag: str) -> list[ast.stmt]:
    """Set the flag beside every `break` that belongs to THIS loop.

    One rule: do not descend into a nested loop's body, because those
    breaks are that loop's. Everything else -- `if`, `try`, `with` -- is
    entered, because a `break` there is ours.
    """
    out: list[ast.stmt] = []
    for statement in statements:
        if isinstance(statement, ast.Break):
            out.append(_at(ast.Assign(
                targets=[ast.Name(id=flag, ctx=ast.Store())],
                value=ast.Constant(value=True),
            ), statement))
            out.append(statement)
            continue
        if not isinstance(statement, (ast.For, ast.AsyncFor, ast.While)):
            for block in _suites(statement):
                block[:] = _mark(block, flag)
        out.append(statement)
    return out


def _own_breaks(statements: list[ast.stmt]):
    """Every `break` belonging to THIS loop, in source order.

    One rule: do not descend into a nested loop's body, because those
    breaks are that loop's. Everything else is entered.
    """
    for statement in statements:
        if isinstance(statement, ast.Break):
            yield statement
            continue
        if isinstance(statement, (ast.For, ast.AsyncFor, ast.While)):
            continue
        for block in _suites(statement):
            yield from _own_breaks(block)


def _has_own_break(statements: list[ast.stmt]) -> bool:
    """Whether a `break` belonging to THIS loop can be reached."""
    return next(_own_breaks(statements), None) is not None
