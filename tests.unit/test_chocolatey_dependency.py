# @file test_chocolatey_dependency.py
# Unit test suite for the ChocolateyDependency class.
#
##
# Copyright (c) Microsoft Corporation
#
# SPDX-License-Identifier: BSD-2-Clause-Patent
##
"""Unit test suite for the ChocolateyDependency class."""

import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from edk2toolext.environment import environment_descriptor_files as EDF
from edk2toolext.environment.extdeptypes.chocolatey_dependency import (
    ChocolateyDependency,
)
from edk2toollib.utility_functions import RemoveTree

# Test directory will be created during setUp
test_dir = None

# Template for a Chocolatey ext_dep descriptor
choco_json_template = """{
  "scope": "global",
  "type": "chocolatey",
  "name": "test-package",
  "source": "https://community.chocolatey.org/api/v2/",
  "version": "%s",
  "flags": []
}"""

good_version = "1.2.3"
bad_version = "bad.version.string"
missing_version = "999.999.999"


def prep_workspace() -> None:
    """Prepare the test workspace."""
    global test_dir
    test_dir = tempfile.mkdtemp()
    logging.debug(f"Test directory created: {test_dir}")


def clean_workspace() -> None:
    """Clean up the test workspace."""
    if test_dir is not None and Path(test_dir).exists():
        RemoveTree(test_dir)
        logging.debug(f"Test directory cleaned: {test_dir}")


class TestChocolateyDependency(unittest.TestCase):
    """Unit test for the ChocolateyDependency class."""

    def setUp(self) -> None:
        """Set up the test environment."""
        prep_workspace()

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the test environment."""
        logger = logging.getLogger("")
        logger.addHandler(logging.NullHandler())
        unittest.installHandler()

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up the test environment."""
        clean_workspace()

    def tearDown(self) -> None:
        """Clean up after each test."""
        if test_dir is not None and Path(test_dir).exists():
            for item in Path(test_dir).iterdir():
                if item.is_dir():
                    RemoveTree(str(item))
                else:
                    item.unlink()

    @patch(
        "edk2toolext.environment.extdeptypes.chocolatey_dependency."
        "LocateChocolatey"
    )
    def test_can_get_choco_path(self, mock_locate: MagicMock) -> None:
        """Test ChocolateyDependency class can get the path to choco."""
        choco_exe = "C:\\ProgramData\\chocolatey\\bin\\choco.exe"
        mock_locate.return_value = choco_exe
        cmd = ChocolateyDependency.GetChocoCmd()
        self.assertIsNotNone(cmd)
        self.assertTrue(len(cmd) > 0)
        mock_locate.assert_called_once()

    @patch(
        "edk2toolext.environment.extdeptypes.chocolatey_dependency."
        "LocateChocolatey"
    )
    def test_missing_chocolatey(self, mock_locate: MagicMock) -> None:
        """Test ChocolateyDependency class can handle missing chocolatey."""
        mock_locate.side_effect = FileNotFoundError("Chocolatey not found")
        cmd = ChocolateyDependency.GetChocoCmd()
        self.assertIsNone(cmd)

    @patch.dict(os.environ, {"CHOCO_PATH": "C:\\CustomChoco"})
    @patch(
        "edk2toolext.environment.extdeptypes.chocolatey_dependency."
        "LocateChocolatey"
    )
    def test_choco_env_var(self, mock_locate: MagicMock) -> None:
        """Test ChocolateyDependency class can handle an env var."""
        mock_locate.return_value = "C:\\CustomChoco\\choco.exe"
        cmd = ChocolateyDependency.GetChocoCmd()
        self.assertIsNotNone(cmd)
        # Verify it was called with the custom path
        mock_locate.assert_called_once_with("C:\\CustomChoco")

    @patch.dict(os.environ, {"CHOCO_PATH": "C:\\Custom Path\\Choco"})
    @patch(
        "edk2toolext.environment.extdeptypes.chocolatey_dependency."
        "LocateChocolatey"
    )
    def test_choco_env_var_with_space(self, mock_locate: MagicMock) -> None:
        """Test ChocolateyDependency class can handle a space in path."""
        mock_locate.return_value = "C:\\Custom Path\\Choco\\choco.exe"
        cmd = ChocolateyDependency.GetChocoCmd()
        self.assertIsNotNone(cmd)
        # Should be quoted due to space
        self.assertIn('"', cmd[0])

    def test_descriptor_parsing(self) -> None:
        """Test that the descriptor is parsed correctly."""
        ext_dep_file_path = Path(test_dir) / "choco_ext_dep.json"
        with open(ext_dep_file_path, "w+") as ext_dep_file:
            ext_dep_file.write(choco_json_template % good_version)

        ext_dep_descriptor = EDF.ExternDepDescriptor(
            str(ext_dep_file_path)
        ).descriptor_contents
        ext_dep = ChocolateyDependency(ext_dep_descriptor)

        self.assertEqual(ext_dep.name, "test-package")
        self.assertEqual(ext_dep.package, "test-package")
        self.assertEqual(ext_dep.version, good_version)
        self.assertEqual(
            ext_dep.source, "https://community.chocolatey.org/api/v2/"
        )

    def test_descriptor_with_different_package_name(self) -> None:
        """Test descriptor with package field different from name."""
        descriptor_dict = {
            "scope": "global",
            "type": "chocolatey",
            "name": "my-tool",
            "package": "actual-package-name",
            "source": "https://community.chocolatey.org/api/v2/",
            "version": "1.0.0",
            "flags": [],
            "descriptor_file": str(Path(test_dir) / "test.json"),
        }

        ext_dep = ChocolateyDependency(descriptor_dict)
        self.assertEqual(ext_dep.name, "my-tool")
        self.assertEqual(ext_dep.package, "actual-package-name")

    @patch(
        "edk2toolext.environment.extdeptypes.chocolatey_dependency."
        "LocateChocolatey"
    )
    @patch(
        "edk2toolext.environment.extdeptypes.chocolatey_dependency.RunCmd"
    )
    def test_fetch_from_cache_success(
        self, mock_run: MagicMock, mock_locate: MagicMock
    ) -> None:
        """Test fetching from Chocolatey cache successfully."""
        mock_locate.return_value = "C:\\ProgramData\\chocolatey\\bin\\choco.exe"

        # Create a mock cache directory structure
        cache_dir = Path(test_dir) / "choco_cache"
        package_cache = cache_dir / "test-package"
        package_cache.mkdir(parents=True, exist_ok=True)

        # Create a fake .nuspec file
        nuspec_file = package_cache / "test-package.nuspec"
        nuspec_file.write_text("<?xml version='1.0'?><package></package>")

        ext_dep_file_path = Path(test_dir) / "choco_ext_dep.json"
        with open(ext_dep_file_path, "w+") as ext_dep_file:
            ext_dep_file.write(choco_json_template % good_version)

        ext_dep_descriptor = EDF.ExternDepDescriptor(ext_dep_file_path).descriptor_contents
        ext_dep = ChocolateyDependency(ext_dep_descriptor)

        # Set the cache path manually for testing
        ext_dep.chocolatey_cache_path = str(cache_dir)

        # Test the cache fetch method directly
        result = ext_dep._fetch_from_chocolatey_cache("test-package")
        self.assertTrue(result)

    def test_string_representation(self) -> None:
        """Test the string representation of ChocolateyDependency."""
        ext_dep_file_path = Path(test_dir) / "choco_ext_dep.json"
        with open(ext_dep_file_path, "w+") as ext_dep_file:
            ext_dep_file.write(choco_json_template % good_version)

        ext_dep_descriptor = EDF.ExternDepDescriptor(ext_dep_file_path).descriptor_contents
        ext_dep = ChocolateyDependency(ext_dep_descriptor)

        str_repr = str(ext_dep)
        self.assertIn("ChocolateyDependency", str_repr)
        self.assertIn("test-package", str_repr)
        self.assertIn(good_version, str_repr)

    @patch(
        "edk2toolext.environment.extdeptypes.chocolatey_dependency."
        "LocateChocolatey"
    )
    @patch(
        "edk2toolext.environment.extdeptypes.chocolatey_dependency.RunCmd"
    )
    def test_install_command_construction(
        self, mock_run: MagicMock, mock_locate: MagicMock
    ) -> None:
        """Test that the install command is constructed correctly."""
        choco_exe = "C:\\ProgramData\\chocolatey\\bin\\choco.exe"
        mock_locate.return_value = choco_exe
        mock_run.return_value = 0

        ext_dep_file_path = Path(test_dir) / "choco_ext_dep.json"
        with open(ext_dep_file_path, "w+") as ext_dep_file:
            ext_dep_file.write(choco_json_template % good_version)

        ext_dep_descriptor = EDF.ExternDepDescriptor(
            str(ext_dep_file_path)
        ).descriptor_contents
        ext_dep = ChocolateyDependency(ext_dep_descriptor)

        ext_dep._attempt_chocolatey_install()

        # Verify RunCmd was called
        self.assertTrue(mock_run.called)
        call_args = mock_run.call_args

        # The command should contain key elements
        cmd_str = " ".join(str(arg) for arg in call_args[0])
        self.assertIn("install", cmd_str)
        self.assertIn("test-package", cmd_str)
        self.assertIn(good_version, cmd_str)
        self.assertIn("--yes", cmd_str)
        self.assertNotIn("--install-directory", cmd_str)

    def test_get_temp_dir(self) -> None:
        """Test that get_temp_dir returns expected path."""
        ext_dep_file_path = Path(test_dir) / "choco_ext_dep.json"
        with open(ext_dep_file_path, "w+") as ext_dep_file:
            ext_dep_file.write(choco_json_template % good_version)

        ext_dep_descriptor = EDF.ExternDepDescriptor(
            str(ext_dep_file_path)
        ).descriptor_contents
        ext_dep = ChocolateyDependency(ext_dep_descriptor)

        temp_dir = ext_dep.get_temp_dir()
        self.assertTrue(temp_dir.endswith("_temp"))
        self.assertIn("test-package_extdep", temp_dir)

    def test_clean_removes_temp_dir(self) -> None:
        """Test that clean() removes the temporary directory."""
        ext_dep_file_path = Path(test_dir) / "choco_ext_dep.json"
        with open(ext_dep_file_path, "w+") as ext_dep_file:
            ext_dep_file.write(choco_json_template % good_version)

        ext_dep_descriptor = EDF.ExternDepDescriptor(
            str(ext_dep_file_path)
        ).descriptor_contents
        ext_dep = ChocolateyDependency(ext_dep_descriptor)

        temp_dir = ext_dep.get_temp_dir()
        Path(temp_dir).mkdir(parents=True, exist_ok=True)
        self.assertTrue(Path(temp_dir).is_dir())

        ext_dep.clean()
        self.assertFalse(Path(temp_dir).is_dir())


if __name__ == "__main__":
    unittest.main()
