# @file chocolatey_dependency.py
# Implements ExternalDependency for Chocolatey packages.
#
##
# Copyright (c) Microsoft Corporation
#
# SPDX-License-Identifier: BSD-2-Clause-Patent
##
"""An ExternalDependency subclass for downloading from Chocolatey."""

import logging
import os
import shutil
from io import StringIO
from pathlib import Path

from edk2toollib.utility_functions import RemoveTree, RunCmd

from edk2toolext.bin.chocolatey import LocateChocolatey
from edk2toolext.environment.external_dependency import ExternalDependency


class ChocolateyDependency(ExternalDependency):
    """An ExternalDependency subclass for downloading from Chocolatey.

    Attributes:
        source (str): Source of the chocolatey dependency (feed URL).
        version (str): Version of the chocolatey package.
        package (str): Package name (defaults to name if not specified).

    !!! tip
        The attributes are what must be described in the ext_dep yaml file!
    """

    TypeString = "chocolatey"

    # Env variable name for path to folder containing choco.exe
    CHOCO_ENV_VAR_NAME = "CHOCO_PATH"

    def __init__(self, descriptor: dict) -> None:
        """Inits a chocolatey dependency based off the provided descriptor."""
        super().__init__(descriptor)
        self.package = descriptor.get("package", self.name)
        self.chocolatey_cache_path = None

    @classmethod
    def GetChocoCmd(cls: "ChocolateyDependency") -> list[str]:
        """Resolves the full path of choco.exe for execution.

        !!! note
            Strings returned might not be pathlike given they may be quoted
            for use on the command line.

        Returns:
            (list): ["choco.exe"] or ["/PATH/TO/choco.exe"]
            (None): If chocolatey was not found

        Raises:
            (FileNotFoundError): If choco.exe cannot be located
        """
        cmd = []

        choco_path_env = os.getenv(cls.CHOCO_ENV_VAR_NAME)
        try:
            if choco_path_env is not None:
                choco_path = LocateChocolatey(choco_path_env)
            else:
                choco_path = LocateChocolatey()
        except FileNotFoundError as e:
            logging.error("Unable to find Chocolatey!")
            logging.error(str(e))
            return None

        # Make sure quoted string if it has spaces
        if " " in choco_path.strip():
            choco_path = '"' + choco_path + '"'

        cmd += [choco_path]

        return cmd

    def _fetch_from_chocolatey_cache(self, package_name: str) -> bool:
        """Attempts to fetch the package from Chocolatey's local cache.

        Args:
            package_name (str): Name of the package to fetch

        Returns:
            (bool): True if successfully fetched from cache, False otherwise
        """
        result = False

        # Get Chocolatey's lib directory (where packages are cached)
        if self.chocolatey_cache_path is None:
            # Chocolatey typically installs to C:\ProgramData\chocolatey\lib
            program_data = os.environ.get("ProgramData", "C:\\ProgramData")
            default_choco_lib = (
                Path(program_data) / "chocolatey" / "lib"
            )

            if default_choco_lib.is_dir():
                self.chocolatey_cache_path = str(default_choco_lib)
            else:
                # Try to get it from choco config
                cmd = ChocolateyDependency.GetChocoCmd()
                if cmd is None:
                    return False

                cmd += ["config", "get", "cacheLocation"]
                return_buffer = StringIO()
                cmd_str = " ".join(cmd[1:])
                ret = RunCmd(cmd[0], cmd_str, outstream=return_buffer)
                if ret == 0:
                    return_buffer.seek(0)
                    return_string = return_buffer.read()
                    # Parse the cache location from output
                    for line in return_string.split("\n"):
                        if "cacheLocation" in line and "|" in line:
                            parts = line.split("|")
                            if len(parts) >= 2:
                                cache_loc = Path(parts[1].strip())
                                if cache_loc.is_dir():
                                    self.chocolatey_cache_path = str(
                                        cache_loc
                                    )
                                    break

        if self.chocolatey_cache_path is None:
            logging.info("The Chocolatey cache was not found.")
            return False

        # Check if the package is in the cache
        cache_search_path = (
            Path(self.chocolatey_cache_path) / package_name.lower()
        )

        if cache_search_path.is_dir():
            nuspec_file = cache_search_path / f"{package_name}.nuspec"

            if nuspec_file.is_file():
                logging.info(
                    f"Found {package_name} in Chocolatey cache at "
                    f"{cache_search_path}"
                )
                shutil.copytree(
                    cache_search_path, self.contents_dir, dirs_exist_ok=True
                )
                result = True
            else:
                logging.debug(
                    f"Package found in cache but nuspec missing: {nuspec_file}"
                )

        if not result:
            logging.info(
                f"Package {package_name} not found in the Chocolatey cache."
            )

        return result

    def __str__(self) -> str:
        """Return a string representation."""
        return f"ChocolateyDependency: {self.package}@{self.version}"

    def _attempt_chocolatey_install(self) -> None:
        """Attempt to install the package using Chocolatey.

        Installs to Chocolatey's default location
        (C:\\ProgramData\\chocolatey\\lib).
        The package will be copied from there to the target location.

        Note: Chocolatey has an `--install-directory` option, but it is only
        available in the commercial version of Chocolatey. This method uses
        the open source Chocolatey.

        Raises:
            (RuntimeError): If the installation fails
        """
        package_name = self.package

        cmd = ChocolateyDependency.GetChocoCmd()
        if cmd is None:
            raise RuntimeError("Chocolatey command could not be constructed")

        cmd += ["install", package_name]
        cmd += ["--version", self.version]

        default_source = "https://community.chocolatey.org/api/v2/"
        if self.source and self.source != default_source:
            cmd += ["--source", self.source]

        # Non-interactive and accept all licenses
        cmd += ["--yes", "--no-progress", "--force"]

        # Limit output for cleaner logs
        cmd += ["--limit-output"]

        logging.info(
            f"Installing Chocolatey package: {package_name} version "
            f"{self.version}"
        )
        logging.debug(f"Chocolatey command: {' '.join(cmd)}")

        output_stream = StringIO()
        ret = RunCmd(cmd[0], " ".join(cmd[1:]), outstream=output_stream)

        output_stream.seek(0)
        output = output_stream.read()

        if ret != 0:
            logging.error(f"Chocolatey install failed with return code {ret}")
            logging.error(f"Output: {output}")
            raise RuntimeError(
                f"Failed to install Chocolatey package {package_name} "
                f"version {self.version}"
            )

        logging.info(
            f"Successfully installed {package_name} version {self.version}"
        )

    def fetch(self) -> None:
        """Fetches the dependency using internal state from the init."""
        package_name = self.package

        # Check if it is in the global cache first
        if super().fetch():
            return

        # Try to fetch from Chocolatey's local cache
        if self._fetch_from_chocolatey_cache(package_name):
            self.copy_to_global_cache(self.contents_dir)
            self.update_state_file()
            self.published_path = self.compute_published_path()
            return

        # Not in cache, proceed to attempt installation with Chocolatey
        self._attempt_chocolatey_install()

        if not self._fetch_from_chocolatey_cache(package_name):
            raise RuntimeError(
                f"Package {package_name} was installed but could not be "
                f"found in Chocolatey's lib directory"
            )

        self.copy_to_global_cache(self.contents_dir)

        self.update_state_file()
        self.published_path = self.compute_published_path()

    def get_temp_dir(self) -> str:
        """Returns the temporary directory for Chocolatey package downloads."""
        return self.contents_dir + "_temp"

    def clean(self) -> None:
        """Removes the temporary directory for Chocolatey package download."""
        super(ChocolateyDependency, self).clean()
        temp_dir = Path(self.get_temp_dir())
        if temp_dir.is_dir():
            RemoveTree(str(temp_dir))
