"""
Lashon Standard Library Framework

Provides a pluggable standard library system for custom languages.
Language designers can register native functions, types, and modules
that are available in their language's runtime.

Architecture:
    StdLib → contains StdModules → contains StdFunctions/StdConstants
    
    Each StdModule maps to an importable namespace.
    StdFunctions wrap Python callables and include type signatures.

Usage:
    stdlib = StdLib()
    stdlib.register_builtins()     # io, math, string, collections
    
    # Or build custom stdlib:
    mod = StdModule("mylib")
    mod.add_function("greet", lambda name: f"Hello, {name}!", 
                     params=[("name", "string")], returns="string")
    stdlib.add_module(mod)
    
    # Inject into a namespace for execution:
    ns = stdlib.inject({})
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class StdFunction:
    """A standard library function with metadata."""
    name: str
    callable: Callable
    params: List[Tuple[str, str]] = field(default_factory=list)  # [(name, type)]
    returns: str = "any"
    doc: str = ""
    pure: bool = True  # Whether the function has side effects

    def __call__(self, *args, **kwargs):
        return self.callable(*args, **kwargs)


@dataclass
class StdConstant:
    """A standard library constant."""
    name: str
    value: Any
    type: str = "any"
    doc: str = ""


@dataclass
class StdModule:
    """A standard library module — a named collection of functions and constants."""
    name: str
    doc: str = ""
    functions: Dict[str, StdFunction] = field(default_factory=dict)
    constants: Dict[str, StdConstant] = field(default_factory=dict)
    submodules: Dict[str, "StdModule"] = field(default_factory=dict)

    def add_function(
        self,
        name: str,
        fn: Callable,
        params: Optional[List[Tuple[str, str]]] = None,
        returns: str = "any",
        doc: str = "",
        pure: bool = True,
    ) -> StdFunction:
        """Register a function in this module."""
        func = StdFunction(
            name=name,
            callable=fn,
            params=params or [],
            returns=returns,
            doc=doc,
            pure=pure,
        )
        self.functions[name] = func
        return func

    def add_constant(
        self,
        name: str,
        value: Any,
        type: str = "any",
        doc: str = "",
    ) -> StdConstant:
        """Register a constant in this module."""
        const = StdConstant(name=name, value=value, type=type, doc=doc)
        self.constants[name] = const
        return const

    def add_submodule(self, module: "StdModule") -> None:
        """Add a submodule."""
        self.submodules[module.name] = module

    def to_namespace(self) -> Dict[str, Any]:
        """Convert this module to a Python dict namespace."""
        ns: Dict[str, Any] = {}
        for name, func in self.functions.items():
            ns[name] = func.callable
        for name, const in self.constants.items():
            ns[name] = const.value
        for name, sub in self.submodules.items():
            ns[name] = type(name, (), sub.to_namespace())
        return ns

    def list_symbols(self) -> List[str]:
        """List all symbol names in this module."""
        symbols = list(self.functions.keys()) + list(self.constants.keys())
        for sub_name, sub in self.submodules.items():
            symbols.extend(f"{sub_name}.{s}" for s in sub.list_symbols())
        return symbols


class StdLib:
    """Standard library manager for Lashon languages.

    Manages a set of standard modules and provides injection
    into execution namespaces.
    """

    def __init__(self):
        self.modules: Dict[str, StdModule] = {}
        self._builtins: Dict[str, Any] = {}

    def add_module(self, module: StdModule) -> None:
        """Register a standard library module."""
        self.modules[module.name] = module

    def get_module(self, name: str) -> Optional[StdModule]:
        """Get a module by name."""
        return self.modules.get(name)

    def add_builtin(self, name: str, value: Any) -> None:
        """Add a built-in function/value (always in scope)."""
        self._builtins[name] = value

    def register_builtins(self) -> None:
        """Register the default set of standard library modules."""
        self.add_module(self._make_io_module())
        self.add_module(self._make_math_module())
        self.add_module(self._make_string_module())
        self.add_module(self._make_collections_module())
        self.add_module(self._make_system_module())
        self.add_module(self._make_random_module())

        # Built-in functions (always available without import)
        self._builtins.update({
            "print": print,
            "input": input,
            "len": len,
            "range": range,
            "int": int,
            "float": float,
            "str": str,
            "bool": bool,
            "list": list,
            "dict": dict,
            "type": type,
            "abs": abs,
            "min": min,
            "max": max,
            "sum": sum,
            "enumerate": enumerate,
            "zip": zip,
            "map": map,
            "filter": filter,
            "sorted": sorted,
            "reversed": reversed,
            "round": round,
            "isinstance": isinstance,
            "hasattr": hasattr,
            "getattr": getattr,
            "setattr": setattr,
        })

    def inject(self, namespace: Dict[str, Any]) -> Dict[str, Any]:
        """Inject builtins into a namespace."""
        namespace.update(self._builtins)
        return namespace

    def inject_module(self, module_name: str, namespace: Dict[str, Any],
                      symbols: Optional[List[str]] = None) -> Dict[str, Any]:
        """Inject a specific module into a namespace.

        Args:
            module_name: Name of the module to inject
            namespace: Target namespace dict
            symbols: If provided, only inject these symbols from the module
        """
        module = self.modules.get(module_name)
        if not module:
            raise ImportError(f"No standard library module named '{module_name}'")

        mod_ns = module.to_namespace()
        if symbols:
            for sym in symbols:
                if sym not in mod_ns:
                    raise ImportError(
                        f"Cannot import '{sym}' from '{module_name}'"
                    )
                namespace[sym] = mod_ns[sym]
        else:
            # Import as namespace object
            namespace[module_name] = type(module_name, (), mod_ns)

        return namespace

    def list_modules(self) -> List[str]:
        """List all available module names."""
        return list(self.modules.keys())

    def list_builtins(self) -> List[str]:
        """List all builtin names."""
        return list(self._builtins.keys())

    # -------------------------------------------------------------------
    # Standard Modules
    # -------------------------------------------------------------------

    @staticmethod
    def _make_io_module() -> StdModule:
        mod = StdModule(name="io", doc="Input/output operations")

        mod.add_function("print", print,
                         params=[("args", "any")], returns="none",
                         doc="Print values to stdout", pure=False)
        mod.add_function("input", input,
                         params=[("prompt", "string")], returns="string",
                         doc="Read a line from stdin", pure=False)

        def read_file(path: str) -> str:
            with open(path) as f:
                return f.read()

        def write_file(path: str, content: str) -> None:
            with open(path, "w") as f:
                f.write(content)

        mod.add_function("read_file", read_file,
                         params=[("path", "string")], returns="string",
                         doc="Read entire file as string", pure=False)
        mod.add_function("write_file", write_file,
                         params=[("path", "string"), ("content", "string")],
                         returns="none",
                         doc="Write string to file", pure=False)

        return mod

    @staticmethod
    def _make_math_module() -> StdModule:
        mod = StdModule(name="math", doc="Mathematical functions and constants")

        # Constants
        mod.add_constant("PI", math.pi, "float", "Pi (3.14159...)")
        mod.add_constant("E", math.e, "float", "Euler's number (2.71828...)")
        mod.add_constant("TAU", math.tau, "float", "Tau (2 * Pi)")
        mod.add_constant("INF", math.inf, "float", "Positive infinity")

        # Functions
        for name, fn, params, ret, doc in [
            ("sqrt", math.sqrt, [("x", "float")], "float", "Square root"),
            ("pow", math.pow, [("x", "float"), ("y", "float")], "float", "Power"),
            ("log", math.log, [("x", "float")], "float", "Natural logarithm"),
            ("log10", math.log10, [("x", "float")], "float", "Base-10 logarithm"),
            ("sin", math.sin, [("x", "float")], "float", "Sine"),
            ("cos", math.cos, [("x", "float")], "float", "Cosine"),
            ("tan", math.tan, [("x", "float")], "float", "Tangent"),
            ("asin", math.asin, [("x", "float")], "float", "Arcsine"),
            ("acos", math.acos, [("x", "float")], "float", "Arccosine"),
            ("atan", math.atan, [("x", "float")], "float", "Arctangent"),
            ("atan2", math.atan2, [("y", "float"), ("x", "float")], "float", "2-arg arctangent"),
            ("ceil", math.ceil, [("x", "float")], "int", "Ceiling"),
            ("floor", math.floor, [("x", "float")], "int", "Floor"),
            ("abs", abs, [("x", "number")], "number", "Absolute value"),
            ("gcd", math.gcd, [("a", "int"), ("b", "int")], "int", "GCD"),
        ]:
            mod.add_function(name, fn, params, ret, doc)

        return mod

    @staticmethod
    def _make_string_module() -> StdModule:
        mod = StdModule(name="string", doc="String manipulation functions")

        mod.add_function("upper", str.upper, [("s", "string")], "string", "Convert to uppercase")
        mod.add_function("lower", str.lower, [("s", "string")], "string", "Convert to lowercase")
        mod.add_function("strip", str.strip, [("s", "string")], "string", "Strip whitespace")
        mod.add_function("split", str.split, [("s", "string"), ("sep", "string")], "list", "Split string")
        mod.add_function("join", str.join, [("sep", "string"), ("items", "list")], "string", "Join with separator")
        mod.add_function("replace", str.replace,
                         [("s", "string"), ("old", "string"), ("new", "string")],
                         "string", "Replace substring")
        mod.add_function("startswith", str.startswith, [("s", "string"), ("prefix", "string")], "bool", "Check prefix")
        mod.add_function("endswith", str.endswith, [("s", "string"), ("suffix", "string")], "bool", "Check suffix")
        mod.add_function("find", str.find, [("s", "string"), ("sub", "string")], "int", "Find substring index")
        mod.add_function("format", str.format, [("template", "string")], "string", "Format string")
        mod.add_function("chr", chr, [("code", "int")], "string", "Int to character")
        mod.add_function("ord", ord, [("char", "string")], "int", "Character to int")

        return mod

    @staticmethod
    def _make_collections_module() -> StdModule:
        mod = StdModule(name="collections", doc="Collection operations")

        mod.add_function("length", len, [("collection", "any")], "int", "Length of collection")
        mod.add_function("append", list.append, [("lst", "list"), ("item", "any")], "none", "Append to list")
        mod.add_function("pop", list.pop, [("lst", "list")], "any", "Remove and return last item")
        mod.add_function("sort", sorted, [("lst", "list")], "list", "Return sorted copy")
        mod.add_function("reverse", lambda lst: list(reversed(lst)),
                         [("lst", "list")], "list", "Return reversed copy")
        mod.add_function("contains", lambda lst, item: item in lst,
                         [("lst", "list"), ("item", "any")], "bool", "Check membership")
        mod.add_function("index", list.index, [("lst", "list"), ("item", "any")], "int", "Find item index")
        mod.add_function("count", list.count, [("lst", "list"), ("item", "any")], "int", "Count occurrences")
        mod.add_function("flatten", lambda lst: [x for sub in lst for x in (sub if isinstance(sub, list) else [sub])],
                         [("lst", "list")], "list", "Flatten nested list one level")
        mod.add_function("unique", lambda lst: list(dict.fromkeys(lst)),
                         [("lst", "list")], "list", "Remove duplicates preserving order")
        mod.add_function("zip_lists", lambda *lists: list(zip(*lists)),
                         [("lists", "list")], "list", "Zip multiple lists")

        return mod

    @staticmethod
    def _make_system_module() -> StdModule:
        mod = StdModule(name="system", doc="System and environment operations")

        mod.add_function("time", time.time, [], "float", "Current time in seconds", pure=False)
        mod.add_function("sleep", time.sleep, [("seconds", "float")], "none", "Pause execution", pure=False)
        mod.add_function("exit", exit, [("code", "int")], "none", "Exit program", pure=False)

        import os
        mod.add_function("env", os.environ.get, [("key", "string")], "string",
                         "Get environment variable", pure=False)
        mod.add_function("cwd", os.getcwd, [], "string", "Current working directory", pure=False)

        return mod

    @staticmethod
    def _make_random_module() -> StdModule:
        mod = StdModule(name="random", doc="Random number generation")

        mod.add_function("random", random.random, [], "float",
                         "Random float 0.0 - 1.0", pure=False)
        mod.add_function("randint", random.randint,
                         [("a", "int"), ("b", "int")], "int",
                         "Random integer in [a, b]", pure=False)
        mod.add_function("choice", random.choice,
                         [("seq", "list")], "any",
                         "Random element from sequence", pure=False)
        mod.add_function("shuffle", random.shuffle,
                         [("lst", "list")], "none",
                         "Shuffle list in place", pure=False)
        mod.add_function("sample", random.sample,
                         [("seq", "list"), ("k", "int")], "list",
                         "Random k elements without replacement", pure=False)
        mod.add_function("seed", random.seed,
                         [("n", "int")], "none",
                         "Set random seed", pure=False)

        return mod
