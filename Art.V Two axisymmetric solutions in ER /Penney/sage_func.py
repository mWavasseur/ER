# sage_subs.py
from sage.symbolic.function_factory import function
import multiprocessing as mp
from uuid import uuid4

def _validate_rules(rules):
    if not isinstance(rules, (list, tuple)):
        raise TypeError("rules must be a list/tuple of (func, rhs) pairs.")
    for i, r in enumerate(rules):
        if not (isinstance(r, (list, tuple)) and len(r) == 2):
            raise TypeError(f"Rule #{i} is not a (func, rhs) pair: {r}")

def _apply_map_safe(obj, fn):
    """Handle both styles: apply_map mutating-in-place (returns None) or returning a new object."""
    res = obj.apply_map(fn)
    return obj if res is None else res

def _make_placeholders(rules):
    salt = uuid4().hex[:6]
    names = []
    for f, _ in rules:
        base = getattr(f, "__name__", str(f))
        names.append(f"{base}_TMP_{salt}")
    return [function(n) for n in names]

def _rewrite_simultaneous(expr, rules, do_factor=True):
    _validate_rules(rules)
    if not rules:
        return expr.factor() if do_factor and hasattr(expr, "factor") else expr

    placeholders = _make_placeholders(rules)

    def pass1(node):
        for (f, _), ph in zip(rules, placeholders):
            node = node.substitute_function(f, ph)
        return node

    def pass2(node):
        for ph, (_, rhs) in zip(placeholders, rules):
            node = node.substitute_function(ph, rhs)
        return node

    if hasattr(expr, "apply_map"):
        e = _apply_map_safe(expr, pass1)
        e = _apply_map_safe(e,    pass2)
    else:
        e = pass2(pass1(expr))

    return e.factor() if do_factor and hasattr(e, "factor") else e

def _maybe_parallel_top(expr, rules, processes=None, threshold=6, do_factor=True, trace=False):
    try:
        op  = expr.operator()
        ops = expr.operands() if op is not None else None
    except Exception:
        op, ops = None, None

    if not ops or len(ops) < threshold:
        if trace: print("parallel: no (atomic or small arity)")
        return _rewrite_simultaneous(expr, rules, do_factor=do_factor)

    # Try parallel; if it fails (pickling etc.), fall back to serial.
    try:
        if trace: print(f"parallel: yes (arity={len(ops)})")
        with mp.Pool(processes=processes) as pool:
            new_ops = pool.starmap(_rewrite_simultaneous, [(o, rules, False) for o in ops])
        out = op(*new_ops)
    except Exception as e:
        if trace: print(f"parallel failed ({type(e).__name__}): falling back to serial")
        new_ops = [_rewrite_simultaneous(o, rules, False) for o in ops]
        out = op(*new_ops)

    return out.factor() if do_factor and hasattr(out, "factor") else out

def subs_func(expr, rules, *, processes=None, threshold=6, do_factor=True, verbose=False, trace=False):
    """
    General simultaneous substitution with safe apply_map and optional parallelism.
    - expr: Sage expression or container
    - rules: [(func, rhs), ...]
    - processes: #workers or None
    - threshold: min top-level arity to parallelize
    - do_factor: factor once at the end
    - verbose/trace: progress info
    """
    _validate_rules(rules)

    # Unwrap .expr() if present
    if hasattr(expr, "expr"):
        expr = expr.expr()

    if hasattr(expr, "apply_map") and hasattr(expr, "display"):
        # container: map elementwise, don’t assume return value
        mapped = _apply_map_safe(
            expr,
            lambda f: _maybe_parallel_top(f, rules, processes=processes,
                                          threshold=threshold, do_factor=False, trace=trace)
        )
        out = mapped.factor() if do_factor and hasattr(mapped, "factor") else mapped
    elif hasattr(expr, "apply_map"):
        mapped = _apply_map_safe(
            expr,
            lambda f: _maybe_parallel_top(f, rules, processes=processes,
                                          threshold=threshold, do_factor=False, trace=trace)
        )
        out = mapped.factor() if do_factor and hasattr(mapped, "factor") else mapped
    else:
        out = _maybe_parallel_top(expr, rules, processes=processes,
                                  threshold=threshold, do_factor=do_factor, trace=trace)

    if verbose:
        print("Substitution: done.")
    return out

