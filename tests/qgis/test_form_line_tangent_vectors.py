"""Pytest tests for the `_form_line_tangent_vectors` helper.

Like AllSampler, this only operates on a plain pandas DataFrame, but it
lives in model_manager.py, which imports LoopStructural/QGIS at module
level, so this test can only run where those are installed (hence
tests/qgis/ rather than tests/unit/).
"""

import numpy as np
import pandas as pd

from loopstructural.main.model_manager import _form_line_tangent_vectors


def _line_df(points, feature_id=0):
    return pd.DataFrame(
        {
            'X': [p[0] for p in points],
            'Y': [p[1] for p in points],
            'Z': [p[2] for p in points],
            'feature_id': [feature_id] * len(points),
        }
    )


class TestFormLineTangentVectors:
    def test_straight_line_gives_constant_unit_tangent(self):
        df = _line_df([(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)])

        tangents = _form_line_tangent_vectors(df)

        expected = np.tile([1.0, 0.0, 0.0], (4, 1))
        np.testing.assert_allclose(tangents, expected, atol=1e-12)

    def test_interior_point_uses_central_difference(self):
        # An L-shaped bend: the interior point's tangent should be the
        # (normalised) average direction of the two adjacent segments,
        # not either segment alone.
        df = _line_df([(0, 0, 0), (1, 0, 0), (1, 1, 0)])

        tangents = _form_line_tangent_vectors(df)

        raw = np.array([1.0, 1.0, 0.0])
        expected_interior = raw / np.linalg.norm(raw)
        np.testing.assert_allclose(tangents[0], [1.0, 0.0, 0.0], atol=1e-12)
        np.testing.assert_allclose(tangents[1], expected_interior, atol=1e-12)
        np.testing.assert_allclose(tangents[2], [0.0, 1.0, 0.0], atol=1e-12)

    def test_single_point_line_is_nan(self):
        df = _line_df([(0, 0, 0)])

        tangents = _form_line_tangent_vectors(df)

        assert np.all(np.isnan(tangents))

    def test_multiple_lines_are_independent(self):
        df = pd.concat(
            [
                _line_df([(0, 0, 0), (1, 0, 0)], feature_id=0),
                _line_df([(5, 5, 0), (5, 6, 0)], feature_id=1),
            ],
            ignore_index=True,
        )

        tangents = _form_line_tangent_vectors(df)

        np.testing.assert_allclose(tangents[0:2], np.tile([1.0, 0.0, 0.0], (2, 1)), atol=1e-12)
        np.testing.assert_allclose(tangents[2:4], np.tile([0.0, 1.0, 0.0], (2, 1)), atol=1e-12)

    def test_coincident_points_give_nan_tangent(self):
        df = _line_df([(0, 0, 0), (0, 0, 0)])

        tangents = _form_line_tangent_vectors(df)

        assert np.all(np.isnan(tangents))
