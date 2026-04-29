from sage.symbolic.expression_conversions import ExpressionTreeWalker
from sage.functions.log import exp
from functools import reduce
import operator as pyop
from sage.symbolic.operators import add_vararg, mul_vararg

       
def subs_func(arg, subs_funcs, labels=None, full=True):
    """
    arg: Sage expression / tensor / scalar field-like object
    subs_funcs: list of (old_func, new_func) pairs used with substitute_function
    labels: optional list of names to print
    """
    if labels is None:
        labels = [f"f{i}" for i in range(len(subs_funcs))]

    if hasattr(arg, "expr"):
        arg = arg.expr()

    if hasattr(arg, "apply_map") and hasattr(arg, "display"):
        for i, (old_func, new_func) in enumerate(subs_funcs):
            arg.apply_map(lambda f: f.substitute_function(old_func, new_func))
            print(f"{labels[i]} substituted")
    elif hasattr(arg, "apply_map"):
        return arg.apply_map(lambda f: subs_func(f, subs_funcs, labels=labels, full=full))
    else:
        for i, (old_func, new_func) in enumerate(subs_funcs):
            arg = arg.substitute_function(old_func, new_func)
            print(f"{labels[i]} substituted")

    if full:
        print("Full Substitution : Done")
    return arg

class explore_expression(ExpressionTreeWalker):
    def __init__(self):
        self.exp_args = []
        self.found_zero = False

    def composition(self, ex, operator):
        walked_args = [self(a) for a in ex.operands()]

        if operator is None:
            return ex

        if operator is exp and len(walked_args) == 1:
            arg = walked_args[0]
            self.exp_args.append(arg)
            if arg.is_zero():
                self.found_zero = True
                return 1
            return exp(arg)

        return operator(*walked_args)
    
class check_res_expr(ExpressionTreeWalker):
    def __init__(self):
            self.op_stack = []   # to call parent operators
    def composition(self, ex, operator):
        self.op_stack.append(operator)

        walked_args = [self(a) for a in ex.operands()]

        self.op_stack.pop() # let's check if the exponential is inside a parent function

        if operator is exp:
            parent_op = self.op_stack[-1] if self.op_stack else None
            print("Careful an exp() has been found inside:", parent_op) if parent_op is not None else None
            return 0

        if operator is None:
            return ex

        return operator(*walked_args)

class decomp_exp(ExpressionTreeWalker):
    def __init__(self, target_arg):
        self.target_arg = target_arg

    def composition(self, ex, operator):
        walked_args = [self(a) for a in ex.operands()]

        if operator is exp and len(walked_args) == 1:
            if walked_args[0] == self.target_arg:
                return exp(0) # Keep the factor in front of the exponential term only
            else:
                return 0      # Remove any other exponential terms 

        if operator is None:
            return ex

        try:
            return operator(*walked_args)
        except (ValueError, ZeroDivisionError, RuntimeError):
            return 0

    def arithmetic(self, ex, operator):
        try:
            # map(self, ex.operands()) recursively walks the children
            # reduce applies the operator (add, mul, pow) to combine them
            return reduce(operator, map(self, ex.operands()))
        except (ValueError, ZeroDivisionError, RuntimeError):
            # If we try to calculate 0^(-1), we land here.
            # Return 0 to "pass" and ignore the term.
            return 0
