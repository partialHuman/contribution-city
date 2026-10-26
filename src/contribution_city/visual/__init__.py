"""Visual regression and gallery tooling for Contribution City.

Needs the optional dependencies ``resvg-py`` and ``Pillow``::

    pip install "contribution-city[visual]"

Nothing in this package is imported by the normal ``generate`` command.
"""

from __future__ import annotations


class VisualDependencyError(RuntimeError):
    """Raised when the optional visual dependencies are not installed."""


INSTALL_HINT = 'Install the visual extras first: pip install "contribution-city[visual]"'
