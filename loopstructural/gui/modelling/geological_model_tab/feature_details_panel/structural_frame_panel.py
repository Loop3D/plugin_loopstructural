from ._base import BaseFeatureDetailsPanel


class StructuralFrameFeatureDetailsPanel(BaseFeatureDetailsPanel):
    def __init__(self, parent=None, *, feature=None, model_manager=None, data_manager=None):
        super().__init__(
            parent, feature=feature, model_manager=model_manager, data_manager=data_manager
        )
