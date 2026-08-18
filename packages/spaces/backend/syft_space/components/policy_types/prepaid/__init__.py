"""Shared base classes for prepaid-balance payment policies.

Xendit and Stripe (and any future prepaid-balance gateway) share an
identical charge flow: reserve in pre_hook, cancel on empty response
in post_hook (per-request); floor-check + settle-by-count (per-document).
The only per-provider differences are declarative — NAME, CONFIG_CLS,
required wallet type. Concrete provider files now hold only those
declarations; all behavior lives in this package.
"""
