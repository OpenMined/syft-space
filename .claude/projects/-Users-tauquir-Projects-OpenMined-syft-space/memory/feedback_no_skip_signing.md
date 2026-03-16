---
name: Never skip commit signing
description: Never disable gpgsign or skip commit signing - provide the command for the user to run manually instead
type: feedback
---

Never skip signing commits (no --no-gpg-sign, no setting commit.gpgsign=false). If commit signing fails, provide the commit command to the user and let them run it manually.

**Why:** User explicitly requested this — commit signing is important to them.

**How to apply:** When a `git commit` fails due to signing issues, output the commit command for the user to copy-paste and run themselves.
