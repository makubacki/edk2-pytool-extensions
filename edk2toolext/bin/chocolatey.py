# @file chocolatey.py
# Support for locating and interacting with Chocolatey
##
# Copyright (c) Microsoft Corporation
#
# SPDX-License-Identifier: BSD-2-Clause-Patent
##
"""This module contains support functions for interacting with Chocolatey."""

import logging
import os
import shutil
from pathlib import Path


def LocateChocolatey(custom_path: str = None) -> str:
    """Locates the Chocolatey executable on the system.

    Searches for choco.exe in the following order:
    1. Custom path if provided
    2. CHOCO_PATH environment variable
    3. System PATH

    Args:
        custom_path (str): Optional custom path to choco.exe directory

    Returns:
        (str): The path to the choco.exe executable

    Raises:
        (FileNotFoundError): If choco.exe cannot be located
    """
    CHOCO_EXE = "choco.exe"

    # Check custom path first (if provided)
    if custom_path is not None:
        candidate = Path(custom_path) / CHOCO_EXE
        if candidate.is_file():
            logging.debug(f"Found Chocolatey at custom path: {candidate}")
            return str(candidate)
        else:
            logging.warning(
                f"Custom path provided but {candidate} does not exist"
            )

    # Check the CHOCO_PATH environment variable
    choco_path_str = os.getenv("CHOCO_PATH")
    if choco_path_str is not None:
        candidate = Path(choco_path_str) / CHOCO_EXE
        if candidate.is_file():
            logging.debug(f"Found Chocolatey via CHOCO_PATH: {candidate}")
            return str(candidate)
        else:
            logging.warning(
                f"CHOCO_PATH set to {choco_path_str} but "
                f"{candidate} does not exist"
            )

    # Check system PATH
    choco_in_path = shutil.which(CHOCO_EXE)
    if choco_in_path is not None:
        logging.debug(f"Found Chocolatey in system PATH: {choco_in_path}")
        return choco_in_path

    raise FileNotFoundError(
        "Could not locate choco.exe. Please ensure Chocolatey is "
        "installed and in your PATH, or set the CHOCO_PATH environment "
        "variable to the directory containing choco.exe. "
        "Visit https://chocolatey.org/install for installation instructions."
    )


def GetChocolateyVersion() -> str:
    """Gets the version of the installed Chocolatey.

    Returns:
        (str): Version string of installed Chocolatey

    Raises:
        (FileNotFoundError): If Chocolatey cannot be located
        (RuntimeError): If version cannot be determined
    """
    from edk2toollib.utility_functions import RunCmd
    from io import StringIO

    try:
        choco_path = LocateChocolatey()
    except FileNotFoundError as e:
        raise e

    # Quote the path if it contains spaces
    if " " in choco_path:
        choco_path = f'"{choco_path}"'

    # Run choco --version
    output_stream = StringIO()
    ret = RunCmd(choco_path, "--version", outstream=output_stream)

    if ret != 0:
        raise RuntimeError("Failed to get Chocolatey version")

    output_stream.seek(0)
    version = output_stream.read().strip()

    return version
