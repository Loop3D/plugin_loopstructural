#! python3

"""Usage from the repo root folder:

... code-block:: bash
# for whole tests
python -m unittest tests.unit.test_interpolation_algorithms
# for specific test
python -m unittest tests.unit.test_interpolation_algorithms.TestInterpolationAlgorithms.test_algorithm_names
"""

# standard library
from qgis.testing import unittest

# project
from loopstructural.processing.algorithms.interpolation.interpolation_algorithm import (
    LoopStructuralInterpolationAlgorithm,
)
from loopstructural.processing.algorithms.interpolation.interpolation_evaluation_algorithm import (
    LoopStructuralInterpolationEvaluationAlgorithm,
)

# ############################################################################
# ########## Classes #############
# ################################


class TestInterpolationAlgorithms(unittest.TestCase):
    """Test interpolation algorithms"""

    def test_interpolation_algorithm_exists(self):
        """Test that LoopStructuralInterpolationAlgorithm can be instantiated."""
        algo = LoopStructuralInterpolationAlgorithm()
        self.assertIsNotNone(algo)

    def test_evaluation_algorithm_exists(self):
        """Test that LoopStructuralInterpolationEvaluationAlgorithm can be instantiated."""
        algo = LoopStructuralInterpolationEvaluationAlgorithm()
        self.assertIsNotNone(algo)

    def test_algorithm_names(self):
        """Test algorithm names are correct."""
        interp_algo = LoopStructuralInterpolationAlgorithm()
        eval_algo = LoopStructuralInterpolationEvaluationAlgorithm()

        self.assertEqual(interp_algo.name(), "loop: interpolation")
        self.assertEqual(eval_algo.name(), "loop: interpolation_evaluation")

    def test_algorithm_display_names(self):
        """Test algorithm display names."""
        interp_algo = LoopStructuralInterpolationAlgorithm()
        eval_algo = LoopStructuralInterpolationEvaluationAlgorithm()

        self.assertEqual(interp_algo.displayName(), "Loop3d: Interpolation")
        self.assertEqual(eval_algo.displayName(), "Loop3d: Interpolation Evaluation")

    def test_algorithm_groups(self):
        """Test algorithm groups."""
        interp_algo = LoopStructuralInterpolationAlgorithm()
        eval_algo = LoopStructuralInterpolationEvaluationAlgorithm()

        self.assertEqual(interp_algo.group(), "Loop3d")
        self.assertEqual(interp_algo.groupId(), "loop3d")
        self.assertEqual(eval_algo.group(), "Loop3d")
        self.assertEqual(eval_algo.groupId(), "loop3d")

    def test_interpolation_algorithm_parameters(self):
        """Test that interpolation algorithm has expected parameters."""
        algo = LoopStructuralInterpolationAlgorithm()
        algo.initAlgorithm()

        # Check that key parameters are defined
        param_names = [p.name() for p in algo.parameterDefinitions()]

        self.assertIn("VALUE", param_names)
        self.assertIn("VALUE_FIELD", param_names)
        self.assertIn("GRADIENT", param_names)
        self.assertIn("STRIKE_FIELD", param_names)
        self.assertIn("DIP_FIELD", param_names)
        self.assertIn("EXTENT", param_names)
        self.assertIn("PIXEL_SIZE", param_names)
        self.assertIn("OUTPUT", param_names)

    def test_evaluation_algorithm_parameters(self):
        """Test that evaluation algorithm has expected parameters."""
        algo = LoopStructuralInterpolationEvaluationAlgorithm()
        algo.initAlgorithm()

        # Check that key parameters are defined
        param_names = [p.name() for p in algo.parameterDefinitions()]

        self.assertIn("INTERPOLATOR_FILE", param_names)
        self.assertIn("EVALUATION_TYPE", param_names)
        self.assertIn("EXTENT", param_names)
        self.assertIn("PIXEL_SIZE", param_names)
        self.assertIn("OUTPUT", param_names)

    def test_create_instance(self):
        """Test that createInstance returns a new instance."""
        interp_algo = LoopStructuralInterpolationAlgorithm()
        eval_algo = LoopStructuralInterpolationEvaluationAlgorithm()

        new_interp = interp_algo.createInstance()
        new_eval = eval_algo.createInstance()

        self.assertIsInstance(new_interp, LoopStructuralInterpolationAlgorithm)
        self.assertIsInstance(new_eval, LoopStructuralInterpolationEvaluationAlgorithm)
        self.assertIsNot(new_interp, interp_algo)
        self.assertIsNot(new_eval, eval_algo)


# ############################################################################
# ####### Stand-alone run ########
# ################################
if __name__ == "__main__":
    unittest.main()
