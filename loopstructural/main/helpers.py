"""
Helper utilities for the LoopStructural plugin.

Includes utilities for intelligent column name matching and other common tasks.
"""

import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple, Union, overload

from qgis.gui import QgsMapLayerComboBox


class ColumnMatcher:
    """
    Intelligent column name matcher that finds the best matching column from a list.

    This class uses multiple matching strategies:
    1. Exact match (case-insensitive)
    2. Common aliases/synonyms
    3. Fuzzy string matching
    4. Pattern-based matching

    Examples
    --------
    >>> matcher = ColumnMatcher(['unitname', 'dip_angle', 'dip_direction', 'age_min'])
    >>> matcher.find_match('DIP')
    'dip_angle'
    >>> matcher.find_match('DIPDIR')
    'dip_direction'
    >>> matcher.find_match('UNITNAME')
    'unitname'

    >>> # Batch matching
    >>> results = matcher.find_matches(['DIP', 'DIPDIR', 'UNIT'])
    >>> print(results)
    {'DIP': 'dip_angle', 'DIPDIR': 'dip_direction', 'UNIT': 'unitname'}
    """

    # Common field aliases and synonyms
    FIELD_ALIASES = {
        'UNITNAME': [
            'unit_name',
            'unit',
            'unitname',
            'formation',
            'lithology',
            'rock_type',
            'geology',
            'strat_name',
            'code',
            'unitcode',
        ],
        'DIP': ['dip', 'dip_angle', 'dip_value', 'inclination', 'plunge'],
        'DIPDIR': [
            'dip_dir',
            'dip_direction',
            'dipdir',
            'dipdirection',
            'azimuth',
            'dip_azimuth',
            'strike_dir',
        ],
        'STRIKE': ['strike', 'strike_angle', 'strike_direction', 'trend'],
        'MIN_AGE': ['min_age', 'minage', 'age_min', 'younger', 'min_age_ma', 'age_low'],
        'MAX_AGE': ['max_age', 'maxage', 'age_max', 'older', 'max_age_ma', 'age_high'],
        'GROUP': ['group', 'group_name', 'groupname', 'series', 'supergroup'],
        'X': ['x', 'easting', 'longitude', 'lon', 'long', 'x_coord'],
        'Y': ['y', 'northing', 'latitude', 'lat', 'y_coord'],
        'Z': ['z', 'elevation', 'altitude', 'height', 'elev', 'z_coord'],
        'ID': ['id', 'objectid', 'fid', 'gid', 'uid', 'feature_id', 'object_id'],
    }

    def __init__(self, available_columns: List[str], case_sensitive: bool = False):
        """
        Initialize the column matcher.

        Parameters
        ----------
        available_columns : List[str]
            List of available column names to match against.
        case_sensitive : bool, optional
            Whether to use case-sensitive matching, by default False.
        """
        self.available_columns = available_columns
        self.case_sensitive = case_sensitive

        # Normalize columns for matching if case-insensitive
        if not case_sensitive:
            self._normalized_columns = {col.lower(): col for col in available_columns if col}
        else:
            self._normalized_columns = {col: col for col in available_columns if col}

    @overload
    def find_match(
        self, target: str, threshold: float = 0.6, return_score: bool = False
    ) -> Optional[str]: ...

    @overload
    def find_match(
        self, target: str, threshold: float, return_score: bool = True
    ) -> Tuple[Optional[str], float]: ...

    def find_match(
        self, target: str, threshold: float = 0.6, return_score: bool = False
    ) -> Union[Optional[str], Tuple[Optional[str], float]]:
        """
        Find the best matching column name for a target field.

        Parameters
        ----------
        target : str
            The target field name to find a match for (e.g., 'DIP', 'UNITNAME').
        threshold : float, optional
            Minimum similarity score (0-1) required for a match, by default 0.6.
        return_score : bool, optional
            If True, return (match, score) tuple instead of just match, by default False.

        Returns
        -------
        str or None or Tuple[str, float]
            The best matching column name, or None if no good match found.
            If return_score=True, returns (column_name, score) or (None, 0.0).
        """
        if not self.available_columns:
            return (None, 0.0) if return_score else None

        # Normalize target
        search_target = target if self.case_sensitive else target.lower()

        # Strategy 1: Exact match
        if search_target in self._normalized_columns:
            match = self._normalized_columns[search_target]
            return (match, 1.0) if return_score else match

        # Strategy 2: Check aliases
        match, score = self._match_via_aliases(target)
        if match and score >= threshold:
            return (match, score) if return_score else match

        # Strategy 3: Fuzzy matching
        match, score = self._fuzzy_match(target, threshold)
        if match:
            return (match, score) if return_score else match

        return (None, 0.0) if return_score else None

    def find_matches(self, targets: List[str], threshold: float = 0.6) -> Dict[str, Optional[str]]:
        """
        Find matches for multiple target fields at once.

        Parameters
        ----------
        targets : List[str]
            List of target field names to find matches for.
        threshold : float, optional
            Minimum similarity score required for a match, by default 0.6.

        Returns
        -------
        Dict[str, Optional[str]]
            Dictionary mapping each target to its best match (or None).
        """
        return {
            target: self.find_match(target, threshold, return_score=False) for target in targets
        }

    def find_best_matches(
        self, targets: List[str], threshold: float = 0.6
    ) -> Dict[str, Tuple[Optional[str], float]]:
        """
        Find matches with confidence scores for multiple targets.

        Parameters
        ----------
        targets : List[str]
            List of target field names to find matches for.
        threshold : float, optional
            Minimum similarity score required for a match, by default 0.6.

        Returns
        -------
        Dict[str, Tuple[Optional[str], float]]
            Dictionary mapping each target to (best_match, score).
        """
        return {target: self.find_match(target, threshold, return_score=True) for target in targets}

    def _match_via_aliases(self, target: str) -> Tuple[Optional[str], float]:
        """
        Try to match using predefined aliases.

        Parameters
        ----------
        target : str
            Target field name.

        Returns
        -------
        Tuple[Optional[str], float]
            (matched_column, confidence_score) or (None, 0.0).
        """
        target_upper = target.upper()

        # Check if target is a known field type
        if target_upper in self.FIELD_ALIASES:
            aliases = self.FIELD_ALIASES[target_upper]

            # Try exact alias match
            for alias in aliases:
                search_alias = alias if self.case_sensitive else alias.lower()
                if search_alias in self._normalized_columns:
                    return self._normalized_columns[search_alias], 0.95

            # Try fuzzy match within aliases
            best_match = None
            best_score = 0.0

            for alias in aliases:
                for col_norm, col_orig in self._normalized_columns.items():
                    score = self._similarity(alias.lower(), col_norm)
                    if score > best_score:
                        best_score = score
                        best_match = col_orig

            if best_score >= 0.7:
                return best_match, best_score

        return None, 0.0

    def _fuzzy_match(self, target: str, threshold: float) -> Tuple[Optional[str], float]:
        """
        Perform fuzzy string matching.

        Parameters
        ----------
        target : str
            Target field name.
        threshold : float
            Minimum similarity threshold.

        Returns
        -------
        Tuple[Optional[str], float]
            (matched_column, confidence_score) or (None, 0.0).
        """
        search_target = target if self.case_sensitive else target.lower()

        best_match = None
        best_score = 0.0

        for col_norm, col_orig in self._normalized_columns.items():
            score = self._similarity(search_target, col_norm)
            if score > best_score:
                best_score = score
                best_match = col_orig

        if best_score >= threshold:
            return best_match, best_score

        return None, 0.0

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """
        Calculate similarity between two strings.

        Uses multiple metrics and returns the best score:
        - SequenceMatcher ratio (overall similarity)
        - Substring matching (one contains the other)
        - Word-based matching (split by _ or -)
        - Keyword matching (target word found in column)

        Parameters
        ----------
        a : str
            First string (typically the target field to search for).
        b : str
            Second string (typically the column name to match against).

        Returns
        -------
        float
            Similarity score between 0 and 1.
        """
        # Normalize
        a_lower = a.lower()
        b_lower = b.lower()

        # Exact match
        if a_lower == b_lower:
            return 1.0

        # Sequence matcher (overall similarity)
        seq_score = SequenceMatcher(None, a_lower, b_lower).ratio()

        # Substring matching
        if a_lower in b_lower or b_lower in a_lower:
            # Give higher score if one is substring of other
            len_ratio = min(len(a_lower), len(b_lower)) / max(len(a_lower), len(b_lower))
            substring_score = 0.8 * len_ratio
        else:
            substring_score = 0.0

        # Word-based matching (split by common separators)
        a_words = set(re.split(r'[_\-\s]+', a_lower))
        b_words = set(re.split(r'[_\-\s]+', b_lower))

        # Remove empty strings from word sets
        a_words.discard('')
        b_words.discard('')

        if a_words and b_words:
            intersection = a_words & b_words
            union = a_words | b_words
            word_score = len(intersection) / len(union) if union else 0.0

            # Boost score if target is a single word and it's found in column words
            # e.g., searching for "geology" should match "hamersley_geology"
            if len(a_words) == 1 and a_words.issubset(b_words):
                word_score = max(word_score, 0.75)
        else:
            word_score = 0.0

        # Return the best score
        return max(seq_score, substring_score, word_score)

    def get_suggestions(self, target: str, top_n: int = 3) -> List[Tuple[str, float]]:
        """
        Get top N suggestions for a target field.

        Parameters
        ----------
        target : str
            Target field name.
        top_n : int, optional
            Number of suggestions to return, by default 3.

        Returns
        -------
        List[Tuple[str, float]]
            List of (column_name, score) tuples sorted by score descending.
        """
        search_target = target if self.case_sensitive else target.lower()

        scores = []
        for col_norm, col_orig in self._normalized_columns.items():
            score = self._similarity(search_target, col_norm)
            scores.append((col_orig, score))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        return scores[:top_n]


def find_column_match(
    available_columns: List[str], target: str, threshold: float = 0.6, case_sensitive: bool = False
) -> Optional[str]:
    """
    Convenience function to find a single column match.

    This is a simplified interface to ColumnMatcher for one-off matches.

    Parameters
    ----------
    available_columns : List[str]
        List of available column names.
    target : str
        Target field name to match.
    threshold : float, optional
        Minimum similarity threshold, by default 0.6.
    case_sensitive : bool, optional
        Whether to use case-sensitive matching, by default False.

    Returns
    -------
    str or None
        Best matching column name, or None if no match found.

    Examples
    --------
    >>> columns = ['unitname', 'dip_angle', 'dip_direction']
    >>> find_column_match(columns, 'DIP')
    'dip_angle'
    >>> find_column_match(columns, 'DIPDIR')
    'dip_direction'
    """
    matcher = ColumnMatcher(available_columns, case_sensitive)
    return matcher.find_match(target, threshold)


def find_column_matches(
    available_columns: List[str],
    targets: List[str],
    threshold: float = 0.6,
    case_sensitive: bool = False,
) -> Dict[str, Optional[str]]:
    """
    Convenience function to find multiple column matches at once.

    Parameters
    ----------
    available_columns : List[str]
        List of available column names.
    targets : List[str]
        List of target field names to match.
    threshold : float, optional
        Minimum similarity threshold, by default 0.6.
    case_sensitive : bool, optional
        Whether to use case-sensitive matching, by default False.

    Returns
    -------
    Dict[str, Optional[str]]
        Dictionary mapping each target to its best match.

    Examples
    --------
    >>> columns = ['unitname', 'dip_angle', 'dip_direction', 'min_age']
    >>> targets = ['DIP', 'DIPDIR', 'UNITNAME', 'MIN_AGE']
    >>> find_column_matches(columns, targets)
    {'DIP': 'dip_angle', 'DIPDIR': 'dip_direction', 'UNITNAME': 'unitname', 'MIN_AGE': 'min_age'}
    """
    matcher = ColumnMatcher(available_columns, case_sensitive)
    return matcher.find_matches(targets, threshold)


def get_layer_names(combo_box: QgsMapLayerComboBox):
    """
    Get all layers from a QgsMapLayerComboBox.

    Parameters
    ----------
    combo_box : QgsMapLayerComboBox
        The combo box to extract layers from.

    Returns
    -------
    List[QgsMapLayer]
        List of layers in the combo box.
    """
    layers = []
    for i in range(combo_box.count()):
        layer = combo_box.layer(i)
        if layer is not None:
            layers.append(layer.name())
    return layers
