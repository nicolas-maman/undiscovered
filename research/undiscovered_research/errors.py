"""Reasons a run cannot go ahead, as opposed to bugs.

The main analysis stops on any of them with the message. A robustness
check that hits one is reported as not run, with the message, and the
other checks go on.
"""


class CannotRun(Exception):
    """A run that cannot go ahead with the data or packages at hand."""


class IncompleteData(CannotRun):
    """Some topics are missing, or were collected by an older version or for another sample."""


class NotEnoughData(CannotRun):
    """No pairs, or no positive or no negative pairs, under these settings."""


class MissingPackages(CannotRun):
    """Optional packages (pretrained embeddings) are not installed."""
