"""Per-feature-type detail panels shown in the Geological Model tab.

Split from a single 1000+ line module into one file per panel class, all
sharing `BaseFeatureDetailsPanel` (in `_base.py`). This `__init__` re-exports
everything the rest of the plugin imports from `feature_details_panel`, so
callers keep using `from .feature_details_panel import FaultFeatureDetailsPanel`
etc. unchanged.
"""

from ._base import BaseFeatureDetailsPanel, retrieve_dip_value, retrieve_pitch_value
from .fault_panel import FaultFeatureDetailsPanel
from .folded_panel import FoldedFeatureDetailsPanel
from .foliation_panel import FoliationFeatureDetailsPanel
from .structural_frame_panel import StructuralFrameFeatureDetailsPanel

__all__ = [
    'BaseFeatureDetailsPanel',
    'FaultFeatureDetailsPanel',
    'FoldedFeatureDetailsPanel',
    'FoliationFeatureDetailsPanel',
    'StructuralFrameFeatureDetailsPanel',
    'retrieve_dip_value',
    'retrieve_pitch_value',
]
