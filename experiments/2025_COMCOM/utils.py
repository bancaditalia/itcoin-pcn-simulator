from __future__ import annotations

import logging
import pathlib
import re
from typing import TYPE_CHECKING

import IPython

if TYPE_CHECKING:
    import os
    from collections.abc import Iterable

MY_DIR = pathlib.Path(__file__).resolve().parent
logger = logging.getLogger(__name__)


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


def _match_single_file(f_path: pathlib.Path, reg_expr: str) -> bool:
    with f_path.open("r") as f:
        for line in f:
            m = re.search(reg_expr, line)
            if m is not None:
                return True
    return False


def _grep_files_with_matches(
    path_iterator: Iterable[pathlib.Path],
    reg_expr: str,
) -> list[pathlib.Path]:
    """Given an iterator over paths and a regex, returns the list of files that
    match the regex.
    """
    return [f for f in path_iterator if _match_single_file(f, reg_expr)]


def search_full_simulations(base_path: pathlib.Path) -> pathlib.Path | None:
    """Looks for full simulations in directories of the following form:
        <base_path>/aaaaaaaaaaaa/seed_XXX/simulation_log.txt
        <base_path>/aaaaaaaaaaaa/seed_YYY/simulation_log.txt

    A match is successful if simulation_log.txt indicates that the simuation
    has been run with waterfall, reverse waterfall and submarine swaps enabled.

    Returns <base_path>/aaaaaaaaaaaa. See the examples for the conditions.

    EXAMPLE 1:
        <base_path>/aaaaaaaaaaaa/seed_XXX/simulation_log.txt
        <base_path>/aaaaaaaaaaaa/seed_YYY/simulation_log.txt

        Returns <base_path>/aaaaaaaaaaaa.

    EXAMPLE 2:
        <base_path>/aaaaaaaaaaaa/seed_XXX/simulation_log.txt
        <base_path>/aaaaaaaaaaaa/seed_YYY/simulation_log.txt
        <base_path>/bbbbbbbbbbbb/seed_ZZZ/simulation_log.txt

        Raises a runtime error: the matching directory after base_path is not
        unique.
    """
    reg_expr = r"--waterfall=1 .*--reverse-waterfall=1 .*--submarine-swaps=1"
    glob_pattern = "*/seed_*/simulation_log.txt"
    experiments = _grep_files_with_matches(base_path.glob(glob_pattern), reg_expr)
    if len(experiments) == 0:
        logger.warning(
            "Could not find any simulation with '%s' in %s/%s",
            reg_expr,
            base_path,
            glob_pattern,
        )
        return None
    directory_set = {e.parent.parent for e in experiments}
    if len(directory_set) > 1:
        msg = f"Too many directories found: {directory_set}"
        raise RuntimeError(msg)
    return next(iter(directory_set))


if __name__ == "__main__":
    bases = {
        "SF": MY_DIR / "results" / "exp-1" / "SF_PCN",
        "SH": MY_DIR / "results" / "exp-1" / "SH_PCN",
    }
    print("These are the directories that have to be used instead of -FULL:")
    print()
    for label, base_path in bases.items():
        print()
        result = search_full_simulations(base_path)
        if result is None:
            print(f"{label}: not found")
        else:
            print(f"{label}: {result.relative_to(MY_DIR)}")
            print(f"{label}: {result.name}")
    print()
    print("DONE: this is implemented in python")
