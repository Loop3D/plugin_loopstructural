"""Allow one background task at a time that uses the model, across the viewer widgets.

The isosurfaces, the update of the out-of-date objects and the tasks of
`ViewerActionsWidget` all evaluate (and can solve) the same model. Two of them
at the same time can solve one feature twice on two threads.
"""

from ..messages import push_info


def try_start(model_manager, title) -> bool:
    """Claim the model for the task `title`. Return False if another task has it."""
    if model_manager is None:
        return True
    running = getattr(model_manager, '_viewer_task', None)
    if running is not None:
        push_info(title, f"Wait for the task '{running}' to finish.")
        return False
    model_manager._viewer_task = title
    return True


def finish(model_manager):
    """Release the model after a task finished or failed."""
    if model_manager is not None:
        model_manager._viewer_task = None
