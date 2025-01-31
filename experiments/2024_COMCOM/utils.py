from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import IPython

if TYPE_CHECKING:
    import os


def get_notebook_path_or_cwd() -> pathlib.Path:
    """Return the absolute path to directory containing the notebook.

    The path is got from user_ns["__session__"]. If there is any error reading
    from that variable, falls back to pathlib.Path.cwd().
    """
    # Try to get IPython and return None if not found.
    ipython = IPython.get_ipython()
    if not ipython:
        return pathlib.Path.cwd()
    # Try to get the __session__ variable from the user namespace.
    user_ns = ipython.user_ns
    if not isinstance(ipython.user_ns, dict):
        return pathlib.Path.cwd()
    if "__session__" in user_ns:
        return pathlib.Path(user_ns["__session__"]).resolve().parent
    return pathlib.Path.cwd()


def add_gz_extension_if_exists(filepath: str | os.PathLike) -> pathlib.Path:
    """Check if filepath.gz exists and return that. Otherwise return filepath.

    If none of filepath.gz and filepath exist, throws a FileNotFoundError.
    The result is converted to an absolute pathlib.Path object.
    """
    abs_path = pathlib.Path(filepath).resolve()
    gz_path = abs_path.parent / (abs_path.name + ".gz")
    if gz_path.is_file():
        return gz_path
    if abs_path.is_file():
        return abs_path
    msg = f"Could not find {abs_path} or {gz_path}"
    raise FileNotFoundError(msg)
