from __future__ import annotations

import pathlib

import IPython


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
