"""
Pytest tests for ColumnMatcher functionality.
Tests column matching with keywords in field names.
"""

import pytest

from loopstructural.main.helpers import ColumnMatcher


class TestColumnMatcher:
    """Test suite for ColumnMatcher class."""

    @pytest.fixture
    def simple_columns(self):
        """Fixture providing simple column names."""
        return [
            'hamersley_geology',
            'geology_type',
            'unit_geology',
            'rock_type',
            'unitname',
            'formation',
        ]

    @pytest.fixture
    def complex_columns(self):
        """Fixture providing complex prefixed column names."""
        return [
            'hamersley_geology',
            'hamersley_dip',
            'hamersley_dipdir',
            'hamersley_age_min',
            'hamersley_age_max',
            'station_id',
        ]

    def test_keyword_in_column_name(self, simple_columns):
        """Test that 'geology' matches columns containing 'geology' as a word."""
        matcher = ColumnMatcher(simple_columns)
        match, score = matcher.find_match('geology', threshold=0.6, return_score=True)

        assert match is not None, "Should find a match for 'geology'"
        assert 'geology' in match.lower(), f"Match '{match}' should contain 'geology'"
        assert score >= 0.6, f"Score {score} should be >= 0.6"

    def test_geology_matches_hamersley_geology(self, simple_columns):
        """Test specific case: 'geology' should match 'hamersley_geology'."""
        matcher = ColumnMatcher(simple_columns)
        match = matcher.find_match('geology', threshold=0.6)

        # Should match one of the geology columns
        assert match in ['hamersley_geology', 'geology_type', 'unit_geology']

    def test_unitname_alias_matching(self, simple_columns):
        """Test that UNITNAME matches via geological aliases."""
        matcher = ColumnMatcher(simple_columns)
        match, score = matcher.find_match('UNITNAME', threshold=0.6, return_score=True)

        assert match == 'unitname', f"UNITNAME should match 'unitname', got '{match}'"
        assert score >= 0.9, f"Exact match should have high score, got {score}"

    def test_get_suggestions_returns_multiple(self, simple_columns):
        """Test that get_suggestions returns multiple ranked matches."""
        matcher = ColumnMatcher(simple_columns)
        suggestions = matcher.get_suggestions('geology', top_n=3)

        assert len(suggestions) <= 3, "Should return at most 3 suggestions"
        assert all(
            isinstance(item, tuple) for item in suggestions
        ), "Each suggestion should be a tuple"
        assert all(len(item) == 2 for item in suggestions), "Each tuple should have (column, score)"

        # Check scores are in descending order
        scores = [score for _, score in suggestions]
        assert scores == sorted(scores, reverse=True), "Suggestions should be sorted by score"

    def test_complex_prefixed_columns(self, complex_columns):
        """Test matching with complex prefixed column names."""
        matcher = ColumnMatcher(complex_columns)

        test_cases = [
            ('geology', 'hamersley_geology'),
            ('DIP', 'hamersley_dip'),
            ('DIPDIR', 'hamersley_dipdir'),
        ]

        for target, expected in test_cases:
            match = matcher.find_match(target, threshold=0.6)
            assert match == expected, f"'{target}' should match '{expected}', got '{match}'"

    def test_batch_matching(self, complex_columns):
        """Test find_best_matches for multiple targets at once."""
        matcher = ColumnMatcher(complex_columns)
        targets = ['geology', 'DIP', 'DIPDIR', 'MIN_AGE', 'MAX_AGE']

        results = matcher.find_best_matches(targets, threshold=0.6)

        assert isinstance(results, dict), "Results should be a dictionary"
        assert len(results) == len(targets), "Should return results for all targets"

        # Check specific matches
        assert results['geology'][0] == 'hamersley_geology'
        assert results['DIP'][0] == 'hamersley_dip'
        assert results['DIPDIR'][0] == 'hamersley_dipdir'
        assert results['MIN_AGE'][0] == 'hamersley_age_min'
        assert results['MAX_AGE'][0] == 'hamersley_age_max'

    def test_no_match_below_threshold(self, simple_columns):
        """Test that no match is returned when score is below threshold."""
        matcher = ColumnMatcher(simple_columns)
        match = matcher.find_match('completely_unrelated_field', threshold=0.8)

        # With high threshold, unlikely fields shouldn't match
        # This might return None or a low-scoring match depending on threshold
        if match:
            _, score = matcher.find_match(
                'completely_unrelated_field', threshold=0.8, return_score=True
            )
            assert score >= 0.8, "If match exists, score should meet threshold"

    def test_case_insensitive_matching(self, simple_columns):
        """Test that matching is case-insensitive by default."""
        matcher = ColumnMatcher(simple_columns)

        match1 = matcher.find_match('UNITNAME')
        match2 = matcher.find_match('unitname')
        match3 = matcher.find_match('UnitName')

        # All should match the same column
        assert match1 == match2 == match3, "Case variations should match the same column"

    def test_geological_field_aliases(self):
        """Test that common geological field aliases work correctly."""
        columns = ['dip_angle', 'azimuth', 'formation_name', 'x_coord', 'y_coord', 'elevation']
        matcher = ColumnMatcher(columns)

        test_cases = [
            ('DIP', 'dip_angle'),
            ('DIPDIR', 'azimuth'),
            ('UNITNAME', 'formation_name'),
            ('X', 'x_coord'),
            ('Y', 'y_coord'),
            ('Z', 'elevation'),
        ]

        for target, expected in test_cases:
            match = matcher.find_match(target, threshold=0.6)
            assert match == expected, f"Alias '{target}' should match '{expected}', got '{match}'"

    def test_empty_columns_list(self):
        """Test that matcher handles empty column list gracefully."""
        matcher = ColumnMatcher([])
        match = matcher.find_match('geology')

        assert match is None, "Should return None when no columns available"

    def test_single_column(self):
        """Test matcher with a single column."""
        matcher = ColumnMatcher(['geology'])
        match = matcher.find_match('geology')

        assert match == 'geology', "Should match the only available column"

    @pytest.mark.parametrize("separator", ['_', '-', ' '])
    def test_different_separators(self, separator):
        """Test that matching works with different word separators."""
        column_name = f'hamersley{separator}geology'
        matcher = ColumnMatcher([column_name])
        match = matcher.find_match('geology', threshold=0.6)

        assert match == column_name, f"Should match with separator '{separator}'"

    def test_word_order_independence(self):
        """Test that word order doesn't prevent matching."""
        columns = ['geology_hamersley', 'hamersley_geology']
        matcher = ColumnMatcher(columns)

        # Both should be viable matches for 'geology'
        match = matcher.find_match('geology', threshold=0.6)
        assert match in columns, "Should match one of the geology columns regardless of word order"

    def test_return_score_flag(self, simple_columns):
        """Test that return_score parameter works correctly."""
        matcher = ColumnMatcher(simple_columns)

        # Without return_score
        result = matcher.find_match('geology', return_score=False)
        assert isinstance(
            result, (str, type(None))
        ), "Without return_score should return string or None"

        # With return_score
        result = matcher.find_match('geology', return_score=True)
        assert isinstance(result, tuple), "With return_score should return tuple"
        assert len(result) == 2, "Tuple should have (match, score)"
        column, score = result
        assert isinstance(score, float), "Score should be a float"
        assert 0 <= score <= 1, "Score should be between 0 and 1"


class TestColumnMatcherEdgeCases:
    """Test edge cases and special scenarios."""

    def test_special_characters_in_column_names(self):
        """Test columns with special characters."""
        columns = ['geology(type)', 'dip [degrees]', 'unit-name', 'id#']
        matcher = ColumnMatcher(columns)

        # Should still match despite special characters
        match = matcher.find_match('geology')
        assert match is not None, "Should handle special characters in column names"

    def test_numeric_suffixes(self):
        """Test columns with numeric suffixes."""
        columns = ['geology1', 'geology2', 'geology_v3', 'dip_2023']
        matcher = ColumnMatcher(columns)

        match = matcher.find_match('geology')
        assert match in columns[:3], "Should match geology columns with numeric suffixes"

    def test_very_long_column_names(self):
        """Test performance with very long column names."""
        long_name = 'very_long_column_name_with_many_words_including_geology_information'
        matcher = ColumnMatcher([long_name])

        match = matcher.find_match('geology', threshold=0.5)
        assert match == long_name, "Should match even with very long column names"

    def test_similar_column_names(self):
        """Test disambiguation when multiple similar columns exist."""
        columns = ['dip', 'dip_angle', 'dip_direction', 'apparent_dip']
        matcher = ColumnMatcher(columns)

        match = matcher.find_match('DIP', threshold=0.6)
        # Should prefer exact or closest match
        assert match in ['dip', 'dip_angle'], f"Should prefer closest match, got '{match}'"


class TestColumnMatcherIntegration:
    """Integration tests simulating real-world usage."""

    def test_realistic_geology_dataset(self):
        """Test with realistic geological field names."""
        columns = [
            'objectid',
            'shape',
            'unit_name',
            'map_symbol',
            'dip_amount',
            'dip_azimuth',
            'strike_direction',
            'min_age_ma',
            'max_age_ma',
            'rock_group',
            'x_coordinate',
            'y_coordinate',
            'elevation_m',
        ]

        matcher = ColumnMatcher(columns)

        expected_matches = {
            'UNITNAME': 'unit_name',
            'DIP': 'dip_amount',
            'DIPDIR': 'dip_azimuth',
            'STRIKE': 'strike_direction',
            'MIN_AGE': 'min_age_ma',
            'MAX_AGE': 'max_age_ma',
            'GROUP': 'rock_group',
            'X': 'x_coordinate',
            'Y': 'y_coordinate',
            'Z': 'elevation_m',
        }

        for target, expected in expected_matches.items():
            match = matcher.find_match(target, threshold=0.6)
            assert match == expected, f"Field '{target}' should match '{expected}', got '{match}'"

    def test_mixed_naming_conventions(self):
        """Test with mixed camelCase, snake_case, and other conventions."""
        columns = ['UnitName', 'dip_angle', 'DipDirection', 'age-min', 'AGE MAX', 'rockGroup']

        matcher = ColumnMatcher(columns)

        # Should handle different conventions
        assert matcher.find_match('UNITNAME') is not None
        assert matcher.find_match('DIP') is not None
        assert matcher.find_match('DIPDIR') is not None
        assert matcher.find_match('MIN_AGE') is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
