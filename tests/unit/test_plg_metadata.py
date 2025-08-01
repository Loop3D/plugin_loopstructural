#! python3

"""Usage from the repo root folder:

.. code-block:: bash
# for whole tests
python -m unittest tests.unit.test_plg_metadata
# for specific test
python -m unittest tests.unit.test_plg_metadata.TestPluginMetadata.test_version_semver
"""

# standard library
import unittest
from pathlib import Path

# 3rd party
from packaging.version import parse

# project
from loopstructural import __about__

# ############################################################################
# ########## Classes #############
# ################################


class TestPluginMetadata(unittest.TestCase):
    """Test about module"""

    def test_metadata_types(self):
        """Test types."""
        # plugin metadata.txt file
        self.assertIsInstance(__about__.PLG_METADATA_FILE, Path)
        self.assertTrue(__about__.PLG_METADATA_FILE.is_file())

        # plugin dir
        self.assertIsInstance(__about__.DIR_PLUGIN_ROOT, Path)
        self.assertTrue(__about__.DIR_PLUGIN_ROOT.is_dir())

        # metadata as dict
        self.assertIsInstance(__about__.__plugin_md__, dict)

        # general
        self.assertIsInstance(__about__.__author__, str)
        self.assertIsInstance(__about__.__copyright__, str)
        self.assertIsInstance(__about__.__email__, str)
        self.assertIsInstance(__about__.__keywords__, list)
        self.assertIsInstance(__about__.__license__, str)
        self.assertIsInstance(__about__.__summary__, str)
        self.assertIsInstance(__about__.__title__, str)
        self.assertIsInstance(__about__.__title_clean__, str)
        self.assertIsInstance(__about__.__version__, str)
        self.assertIsInstance(__about__.__version_info__, tuple)

        # misc
        self.assertLessEqual(len(__about__.__title_clean__), len(__about__.__title__))

        # QGIS versions
        self.assertIsInstance(__about__.__plugin_md__.get("general").get("qgisminimumversion"), str)

        self.assertIsInstance(__about__.__plugin_md__.get("general").get("qgismaximumversion"), str)

        min_version_parsed = parse(__about__.__plugin_md__.get("general").get("qgisminimumversion"))
        max_version_parsed = parse(__about__.__plugin_md__.get("general").get("qgismaximumversion"))
        self.assertLessEqual(min_version_parsed, max_version_parsed)

    def test_version_semver(self):
        """Test if version comply with semantic versioning."""
        self.assertTrue(parse(__about__.__version__))


# ############################################################################
# ####### Stand-alone run ########
# ################################
if __name__ == "__main__":
    unittest.main()
