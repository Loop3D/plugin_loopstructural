"""The status of a step of the modelling dock."""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class Status(str, Enum):
    """The result of the check of a step."""

    DONE = 'done'
    PROBLEM = 'problem'
    NOT_STARTED = 'not_started'


@dataclass(frozen=True)
class StepCheck:
    """The result of the check of one step.

    Parameters
    ----------
    problems : tuple of str
        Things that are wrong, for example a result that is out of date.
    todo : tuple of str
        Things that the user did not do yet.
    """

    problems: Tuple[str, ...] = ()
    todo: Tuple[str, ...] = ()

    @property
    def status(self) -> Status:
        if self.problems:
            return Status.PROBLEM
        if self.todo:
            return Status.NOT_STARTED
        return Status.DONE

    @property
    def messages(self) -> Tuple[str, ...]:
        """All the reasons why the step is not done, the problems first."""
        return self.problems + self.todo

    @property
    def summary(self) -> str:
        """The most important message, for the footer of the dock."""
        messages = self.messages
        if not messages:
            return ''
        if len(messages) == 1:
            return messages[0]
        return f"{messages[0]} (+{len(messages) - 1} more)"
