"""Controlling the benchmark from outside: targets, settings, launching.

The package holds everything needed for a measurement to be driven by a UI
rather than by a human at a console. The measurement itself lives a floor below
and knows nothing about this package — it accepts settings and reports on its
progress to whoever it is told to.
"""

from syft_benchmark.control.check import Check, check
from syft_benchmark.control.compose import merge, settings_for
from syft_benchmark.control.schemas import (
    Capabilities,
    Instrument,
    JobView,
    Probe,
    RunRequest,
    TargetSpec,
    TargetView,
)

__all__ = [
    "Capabilities",
    "Check",
    "Instrument",
    "JobView",
    "Probe",
    "RunRequest",
    "TargetSpec",
    "TargetView",
    "check",
    "merge",
    "settings_for",
]
