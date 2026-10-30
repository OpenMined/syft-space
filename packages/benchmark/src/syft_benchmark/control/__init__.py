"""Driving the benchmark from outside: the control API, its targets, settings
layers, job queue and schedule.

The measurement itself lives a floor below and knows nothing about this
package: it accepts settings and reports progress to whoever it is told to.
"""
