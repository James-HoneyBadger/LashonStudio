"""
ParserCraft Foreign Function Interface (FFI)

Enables custom languages to call native C/Python libraries and expose
their own functions to other languages.

Architecture:
    FFIBridge → manages FFIBinding objects → wraps ctypes or Python callables

Usage:
    ffi = FFIBridge()
    
    # Load a C shared library
    ffi.load_library("libm", "/usr/lib/libm.so.6")
    ffi.bind("sqrt", "libm", arg_types=["double"], return_type="double")
    result = ffi.call("sqrt", 144.0)  # → 12.0
    
    # Register a Python function as FFI-callable
    ffi.register_python("greet", lambda name: f"Hello, {name}!")
    result = ffi.call("greet", "World")  # → "Hello, World!"
    
    # Inject all bindings into an execution namespace
    ns = ffi.inject({})
"""

from __future__ import annotations

import ctypes
import ctypes.util
import importlib
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

# Map string type names to ctypes types
CTYPE_MAP = {
    "void": None,
    "int": ctypes.c_int,
    "int8": ctypes.c_int8,
    "int16": ctypes.c_int16,
    "int32": ctypes.c_int32,
    "int64": ctypes.c_int64,
    "uint": ctypes.c_uint,
    "uint8": ctypes.c_uint8,
    "uint16": ctypes.c_uint16,
    "uint32": ctypes.c_uint32,
    "uint64": ctypes.c_uint64,
    "float": ctypes.c_float,
    "double": ctypes.c_double,
    "char": ctypes.c_char,
    "char_p": ctypes.c_char_p,  # C string
    "wchar_p": ctypes.c_wchar_p,
    "bool": ctypes.c_bool,
    "size_t": ctypes.c_size_t,
    "pointer": ctypes.c_void_p,
}


@dataclass
class FFIBinding:
    """A single FFI function binding."""
    name: str  # Name used in the custom language
    source: str  # "c:<library>" or "python:<module>"
    native_name: str  # Name in the native library
    arg_types: List[str] = field(default_factory=list)
    return_type: str = "void"
    doc: str = ""
    _callable: Optional[Callable] = field(default=None, repr=False)

    def __call__(self, *args: Any) -> Any:
        if self._callable is None:
            raise RuntimeError(f"FFI binding '{self.name}' is not resolved")
        return self._callable(*args)


@dataclass
class FFILibrary:
    """A loaded native library."""
    name: str
    path: str
    handle: Any = field(default=None, repr=False)
    bindings: Dict[str, FFIBinding] = field(default_factory=dict)


class FFIBridge:
    """Foreign Function Interface bridge for ParserCraft languages.

    Manages loading native libraries, binding functions, and
    providing them to custom language runtime namespaces.
    """

    def __init__(self):
        self._libraries: Dict[str, FFILibrary] = {}
        self._bindings: Dict[str, FFIBinding] = {}
        self._python_funcs: Dict[str, Callable] = {}

    def load_library(self, name: str, path: Optional[str] = None) -> FFILibrary:
        """Load a C shared library.

        Args:
            name: Symbolic name for the library
            path: Path to .so/.dylib/.dll file. If None, uses ctypes.util.find_library
        """
        if name in self._libraries:
            return self._libraries[name]

        if path is None:
            path = ctypes.util.find_library(name)
            if path is None:
                raise FileNotFoundError(
                    f"Could not find library '{name}'. "
                    f"Provide explicit path or ensure it's in the system library path."
                )

        try:
            handle = ctypes.CDLL(path)
        except OSError as e:
            raise OSError(f"Failed to load library '{name}' from '{path}': {e}") from e

        lib = FFILibrary(name=name, path=path, handle=handle)
        self._libraries[name] = lib
        return lib

    def bind(
        self,
        name: str,
        library: str,
        native_name: Optional[str] = None,
        arg_types: Optional[List[str]] = None,
        return_type: str = "int",
        doc: str = "",
    ) -> FFIBinding:
        """Bind a C function from a loaded library.

        Args:
            name: Name to use in the custom language
            library: Library name (must be loaded first)
            native_name: C function name (defaults to `name`)
            arg_types: List of C type names (e.g., ["double", "int"])
            return_type: Return type name
            doc: Documentation string
        """
        if library not in self._libraries:
            raise KeyError(f"Library '{library}' not loaded. Call load_library first.")

        lib = self._libraries[library]
        c_name = native_name or name
        arg_types = arg_types or []

        try:
            func = getattr(lib.handle, c_name)
        except AttributeError:
            raise AttributeError(
                f"Function '{c_name}' not found in library '{library}'"
            ) from None

        # Set ctypes type info
        func.argtypes = [CTYPE_MAP[t] for t in arg_types if t in CTYPE_MAP]
        ret = CTYPE_MAP.get(return_type)
        func.restype = ret

        binding = FFIBinding(
            name=name,
            source=f"c:{library}",
            native_name=c_name,
            arg_types=arg_types,
            return_type=return_type,
            doc=doc,
            _callable=func,
        )

        self._bindings[name] = binding
        lib.bindings[name] = binding
        return binding

    def register_python(
        self,
        name: str,
        func: Callable,
        doc: str = "",
    ) -> FFIBinding:
        """Register a Python function as an FFI-callable binding.

        This allows custom language code to call arbitrary Python functions.
        """
        binding = FFIBinding(
            name=name,
            source="python:native",
            native_name=name,
            doc=doc or (func.__doc__ or ""),
            _callable=func,
        )
        self._bindings[name] = binding
        self._python_funcs[name] = func
        return binding

    def import_python_module(
        self,
        module_name: str,
        functions: Optional[List[str]] = None,
        prefix: str = "",
    ) -> List[FFIBinding]:
        """Import functions from a Python module as FFI bindings.

        Args:
            module_name: Dotted Python module name (e.g., "math", "os.path")
            functions: Specific function names to import. If None, imports all callables.
            prefix: Prefix to add to binding names (e.g., "math_")
        """
        try:
            mod = importlib.import_module(module_name)
        except ImportError as e:
            raise ImportError(f"Cannot import Python module '{module_name}': {e}") from e

        bindings = []

        if functions:
            names = functions
        else:
            names = [n for n in dir(mod) if not n.startswith("_") and callable(getattr(mod, n))]

        for name in names:
            attr = getattr(mod, name, None)
            if attr is None or not callable(attr):
                continue

            bound_name = f"{prefix}{name}"
            binding = self.register_python(
                bound_name,
                attr,
                doc=f"From {module_name}.{name}",
            )
            bindings.append(binding)

        return bindings

    def call(self, name: str, *args: Any) -> Any:
        """Call an FFI binding by name."""
        if name not in self._bindings:
            raise NameError(f"No FFI binding named '{name}'")
        return self._bindings[name](*args)

    def inject(self, namespace: Dict[str, Any]) -> Dict[str, Any]:
        """Inject all FFI bindings into a namespace dict."""
        for name, binding in self._bindings.items():
            namespace[name] = binding._callable
        return namespace

    def list_bindings(self) -> List[str]:
        """List all registered binding names."""
        return list(self._bindings.keys())

    def list_libraries(self) -> List[str]:
        """List all loaded library names."""
        return list(self._libraries.keys())

    def get_binding(self, name: str) -> Optional[FFIBinding]:
        """Get a binding by name."""
        return self._bindings.get(name)

    def unload_library(self, name: str) -> None:
        """Unload a library and remove its bindings."""
        if name in self._libraries:
            lib = self._libraries.pop(name)
            for bname in list(lib.bindings.keys()):
                self._bindings.pop(bname, None)

    def describe(self) -> str:
        """Return a human-readable description of all loaded bindings."""
        lines = ["FFI Bindings:"]
        for name, b in self._bindings.items():
            args = ", ".join(b.arg_types) if b.arg_types else ""
            lines.append(f"  {name}({args}) -> {b.return_type}  [{b.source}]")
        return "\n".join(lines)
