import ast
import inspect
import textwrap
import types
from ctypes import c_int, py_object, pythonapi

import dill

# Set the argument types for ctypes
_PyFrame_LocalsToFast = pythonapi.PyFrame_LocalsToFast
_PyFrame_LocalsToFast.argtypes = [py_object, c_int]


_PyCell_Set = pythonapi.PyCell_Set
_PyCell_Set.argtypes = [py_object, py_object]


# Global registration set
REGISTERED_FUNCTIONS = {}


def register_auto_yield(func=None, *, allow_override=False):
    """
    Register functions that need to be transformed

    Args:
        func: The function to be registered (when used as @register_auto_yield)
        allow_override: Allow override parameter to be recorded in auto_yield_info
    """

    def decorator(f):
        auto_yield_info = {
            "name": f.__name__,
            "module": f.__module__,
            "qualname": f.__qualname__,
            "allow_override": allow_override,
        }
        before_transformed_key = None
        for key in REGISTERED_FUNCTIONS:
            if (
                auto_yield_info["name"] == REGISTERED_FUNCTIONS[key]["name"]
                and auto_yield_info["module"] == REGISTERED_FUNCTIONS[key]["module"]
                and REGISTERED_FUNCTIONS[key]["qualname"].endswith(
                    auto_yield_info["qualname"]
                )
            ):
                before_transformed_key = key
                break
        if before_transformed_key:
            del REGISTERED_FUNCTIONS[before_transformed_key]
        REGISTERED_FUNCTIONS[f.__qualname__] = auto_yield_info
        return f

    # Support both @register_auto_yield and @register_auto_yield(allow_override=...)
    if func is None:
        # Used as @register_auto_yield(allow_override=...)
        return decorator
    else:
        # Used as @register_auto_yield
        return decorator(func)


class StrictAutoYieldTransformer(ast.NodeTransformer):
    def __init__(self):
        super().__init__()
        self.parent_stack = []  # For potential future use
        self.class_stack = []  # To record current class context

    def generic_visit(self, node):
        self.parent_stack.append(node)
        new_node = super().generic_visit(node)
        self.parent_stack.pop()
        return new_node

    def visit_ClassDef(self, node):
        # Push the class name onto the stack when entering a class definition
        self.class_stack.append(node.name)
        node = self.generic_visit(node)
        self.class_stack.pop()
        return node

    def visit_Call(self, node):
        # First, process child nodes
        node = self.generic_visit(node)

        # Determine the function name and whether it is a self-call
        func_node = node.func
        func_name = None
        is_self_call = False
        is_super_call = False

        if isinstance(func_node, ast.Name):
            func_name = func_node.id
        elif isinstance(func_node, ast.Attribute):
            func_name = func_node.attr
            # Check if it's a self-call, e.g. self.foo()
            if isinstance(func_node.value, ast.Name) and func_node.value.id == "self":
                is_self_call = True
            # Check for super() call (treat as non-self for matching purposes)
            elif isinstance(func_node.value, ast.Call):
                is_self_call = False
                if (
                    isinstance(func_node.value.func, ast.Name)
                    and func_node.value.func.id == "super"
                ):
                    is_super_call = True
        else:
            # For other types, return the node unmodified
            return node

        if not is_self_call and func_name == "super":
            # super() calls are not rewritten
            return node

        candidate_keys = []
        if is_self_call:
            # If it's a self call, we expect the qualified name to include the current class name.
            if not self.class_stack:
                # No class context available: cannot resolve a self call.
                return node
            current_class = self.class_stack[-1]
            # For example, if current_class is "Foo" and func_name is "foo",
            # we expect a key that ends with "Foo.foo"
            suffix = f"{current_class}.{func_name}"
            for key in REGISTERED_FUNCTIONS:
                if key.endswith(suffix):
                    candidate_keys.append(key)
        elif is_super_call:
            # For super calls, look for keys that end with ".<func_name>"
            suffix = f".{func_name}"
            for key in REGISTERED_FUNCTIONS:
                if key.endswith(suffix):
                    candidate_keys.append(key)
        else:
            # For non-self calls, look for keys that end with "<func_name>"
            suffix = f"{func_name}"
            for key in REGISTERED_FUNCTIONS:
                if key.split(".")[-1] == suffix:
                    candidate_keys.append(key)

        if len(candidate_keys) == 1:
            # Exactly one candidate is found; rewrite the call to yield from.
            new_node = ast.YieldFrom(value=node)
            new_node = ast.copy_location(new_node, node)
            return new_node
        elif len(candidate_keys) > 1:
            # Multiple candidates found, check for allow_override logic
            # Start from the second candidate and check if the previous one allows override
            for i in range(1, len(candidate_keys)):
                prev_key = candidate_keys[i - 1]
                prev_func_info = REGISTERED_FUNCTIONS.get(prev_key, {})
                prev_allow_override = prev_func_info.get("allow_override", False)

                # If the previous function doesn't allow override, this is an error
                if not prev_allow_override:
                    raise ValueError(
                        f"Function '{prev_key}' does not allow override, but '{candidate_keys[i]}' is trying to override it for function call '{func_name}'"
                    )

            # If we get here, all override checks passed, use the last candidate
            new_node = ast.YieldFrom(value=node)
            new_node = ast.copy_location(new_node, node)
            return new_node
        else:
            # No match found; return the call unmodified.
            return node


class LineAndColumnAdjuster(ast.NodeTransformer):
    def __init__(self, line_offset, col_offset):
        self.line_offset = line_offset
        self.col_offset = col_offset

    def generic_visit(self, node):
        if hasattr(node, "lineno"):
            node.lineno += self.line_offset
        if hasattr(node, "col_offset"):
            node.col_offset += self.col_offset
        if hasattr(node, "end_lineno"):
            node.end_lineno += self.line_offset
        if hasattr(node, "end_col_offset"):
            node.end_col_offset += self.col_offset
        return super().generic_visit(node)


class ClassAttributeAdder(ast.NodeTransformer):
    def __init__(self, attr_name, value):
        self.attr_name = attr_name
        self.value = value
        super().__init__()

    def visit_ClassDef(self, node):
        name = ast.Name(id=self.attr_name, ctx=ast.Store())
        ast.copy_location(name, node)
        value = ast.Constant(value=self.value)
        ast.copy_location(value, node)
        assign_node = ast.Assign(targets=[name], value=value)
        ast.copy_location(assign_node, node)
        node.body.insert(0, assign_node)
        return node


def auto_yield_class(cls=None, *, debug=False):
    def decorator(cls):
        # 1. Get the source code and parse its AST
        src = dill.source.getsource(cls)
        if debug:
            print("Original Source Code:")
            print(src)
        filename = inspect.getfile(cls)
        src = textwrap.dedent(src)
        tree = ast.parse(src)

        # 2 Rewrite the AST
        tree = ClassAttributeAdder("__transformed__", True).visit(tree)
        new_tree = StrictAutoYieldTransformer().visit(tree)

        _, lnum = dill.source.getsourcelines(cls)
        indent = None
        for line in src.splitlines()[1:]:
            stripped = line.lstrip()
            if stripped:
                indent = len(line) - len(stripped)
                break
        if indent is None:
            indent = 0
        line_offset = lnum
        new_tree = LineAndColumnAdjuster(line_offset, indent).visit(new_tree)
        ast.fix_missing_locations(new_tree)

        # 3. Get the caller frame where the class is defined
        caller = None
        for frame_info in inspect.stack():
            if frame_info.filename == filename:
                caller = frame_info.frame
                break
        if caller is None:
            caller = inspect.currentframe().f_back

        # 4. Compile the AST and execute it
        code = compile(new_tree, filename=filename, mode="exec")
        if debug:
            source_code = ast.unparse(new_tree)
            print("Modified Source Code:")
            print(source_code)
        exec(code, caller.f_globals, caller.f_locals)

        # 5. Refresh local variables and return the transformed class
        _PyFrame_LocalsToFast(py_object(caller), c_int(0))
        new_cls = caller.f_locals[cls.__name__]
        return new_cls

    # If used directly as a decorator, then cls is not None
    if cls is None:
        return decorator
    else:
        return decorator(cls)


def update_class_cells(new_cls):
    """
    Iterate over all callable attributes of new_cls,
    and if their closure contains a free variable
    named "__class__", update it to new_cls.
    """
    for attr_name in dir(new_cls):
        _attr = getattr(new_cls, attr_name)
        if callable(_attr) and hasattr(_attr, "__code__"):
            freevars = _attr.__code__.co_freevars
            if "__class__" in freevars:
                idx = freevars.index("__class__")
                if _attr.__closure__:
                    cell = _attr.__closure__[idx]
                    _PyCell_Set(cell, new_cls)


class AutoYieldBase:
    def __init_subclass__(cls, debug=False, **kwargs):
        if hasattr(cls, "__transformed__"):
            return
        new_cls = auto_yield_class(cls, debug=debug)
        for name, attr in new_cls.__dict__.items():
            if name not in (
                "__module__",
                "__qualname__",
                "__dict__",
                "__weakref__",
                "__transformed__",
            ):
                setattr(cls, name, attr)
        update_class_cells(cls)


class AutoYieldMeta(type):
    def __new__(mcls, name, bases, namespace, debug=False, **kwargs):
        if "__transformed__" in namespace:
            cls = super().__new__(mcls, name, bases, namespace)
            return cls
        # First, create the class object using the default method
        cls = super().__new__(mcls, name, bases, namespace)
        # Obtain the new class object using auto_yield_class and return it directly
        new_cls = auto_yield_class(cls, debug=debug)
        classcell = namespace.get("__classcell__")
        if classcell is not None:
            classcell.cell_contents = new_cls
        return new_cls


def transform_method(func, debug=False):
    try:
        src = dill.source.getsource(func)
    except Exception:
        return func  # If source code cannot be obtained, do not transform
    if debug:
        print("Original method source for", func.__name__)
        print(src)
    src = textwrap.dedent(src)
    try:
        tree = ast.parse(src)
    except Exception as e:
        if debug:
            print(f"AST parse error for {func.__name__}: {e}")
        return func

    # Get the starting line number and indentation information of the function
    try:
        _, lnum = dill.source.getsourcelines(func)
    except Exception:
        lnum = 0
    indent = None
    for line in src.splitlines()[1:]:
        stripped = line.lstrip()
        if stripped:
            indent = len(line) - len(stripped)
            break
    if indent is None:
        indent = 0

    # Apply AST transformer and line number adjustment
    tree = StrictAutoYieldTransformer().visit(tree)
    tree = LineAndColumnAdjuster(lnum, indent).visit(tree)
    ast.fix_missing_locations(tree)

    if debug:
        try:
            mod_src = ast.unparse(tree)
        except Exception:
            mod_src = "<could not unparse>"
        print("Modified method source for", func.__name__)
        print(mod_src)

    filename = inspect.getfile(func)
    code = compile(tree, filename=filename, mode="exec")
    temp_ns = {}
    exec(code, func.__globals__, temp_ns)
    new_func = temp_ns.get(func.__name__)
    if new_func is None:
        return func
    # Retain original defaults, closure, etc.
    new_func = types.FunctionType(
        new_func.__code__,
        func.__globals__,
        name=func.__name__,
        argdefs=func.__defaults__,
        closure=func.__closure__,
    )
    new_func.__dict__.update(func.__dict__)
    return new_func


class AutoYieldMethodMeta(type):
    def __new__(mcls, name, bases, namespace, debug=False, **kwargs):
        # To avoid __init_subclass__ parameter issues, if not in namespace, inject a simple __init_subclass__ that accepts all keyword arguments
        if "__init_subclass__" not in namespace:

            def __init_subclass__(cls, **kw):
                # Simply accept all extra parameters without any processing
                pass

            namespace["__init_subclass__"] = __init_subclass__

        new_namespace = dict(namespace)
        # Iterate over each callable object in the namespace and transform registered functions
        for key, value in namespace.items():
            if (
                callable(value)
                and hasattr(value, "__code__")
                and not key.startswith("__")
            ):
                try:
                    src = dill.source.getsource(value)
                except Exception:
                    continue
                # If the source code contains the function name to be transformed, transform it
                if any(
                    f"{reg['name']}(" in src for reg in REGISTERED_FUNCTIONS.values()
                ):
                    transformed = transform_method(value, debug=debug)
                    new_namespace[key] = transformed
        cls = super().__new__(mcls, name, bases, new_namespace)
        # If __classcell__ exists, update it
        classcell = new_namespace.get("__classcell__")
        if classcell is not None:
            try:
                _PyCell_Set(classcell, cls)
            except Exception:
                pass
        return cls

    def __init__(cls, name, bases, namespace, debug=False, **kwargs):
        super().__init__(name, bases, namespace)
        update_class_cells(cls)


class AutoYieldMethodBase(metaclass=AutoYieldMethodMeta):
    def __init_subclass__(cls, **kwargs):
        # Accept all extra keyword arguments here
        super().__init_subclass__(**kwargs)
