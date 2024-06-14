########################################################################################################################
#                         Copyright (c) 2019-2021 Banca d'Italia - All Rights Reserved                                 #
#                                                                                                                      #
# This file is part of the "itCoin" project.                                                                           #
# Unauthorized copying of this file, via any medium, is strictly prohibited.                                           #
# The content of this and related source files is proprietary and confidential.                                        #
#                                                                                                                      #
# Written by ART (Applied Research Team) - email: appliedresearchteam@bancaditalia.it - web: https://www.bankit.art    #
########################################################################################################################
import logging
from pathlib import Path

"""Exit codes"""
EXIT_SUCCESS = 0
EXIT_FAILURE = 1


def configure_logging(verbose: bool) -> None:
    """Configure logging.

    Args:
    ----
        verbose: if True, set the logging level to DEBUG, otherwise to INFO.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(asctime)s][%(levelname)s][%(filename)s:%(lineno)-3s] %(message)s",
    )


def check_path_is_directory(
    dirpath: Path,
    exception_class: type[Exception] = ValueError,
) -> None:
    """Check if the directory exists and is a directory.

    Args:
    ----
        dirpath: The path to the output directory.
        exception_class: The exception class to be raised if validation fails.
    """
    if not dirpath.is_dir():
        msg = f"path {dirpath} does not exist or is not a directory. Please create it"
        raise exception_class(msg)


def count_file_in_dir(
    dirpath: Path,
    pattern: str,
    exception_class: type[Exception] = ValueError,
) -> int:
    """Check if the filename exists in the directory.

    Args:
    ----
        dirpath: The path to the output directory.
        pattern: Filename pattern to search for within the directory.
        exception_class: The exception class to be raised if validation fails.
    """
    files = dirpath.glob(pattern)
    count = sum(1 for file in files if file.is_file())
    if count == 0:
        msg = (
            f"path {dirpath} does not contain any file following the pattern {pattern}"
        )
        raise exception_class(msg)
    return count
