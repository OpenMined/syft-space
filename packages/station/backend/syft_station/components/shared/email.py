"""The one email type for fields that identify an account.

Emails are persisted and compared verbatim everywhere (ownership guards,
the one-live-request index, balance rows keyed by email), so every email
must be lowercase before it reaches a handler. This type establishes that
at the validation boundary; SyftHub normalizes the same way, so lowering
never conflates two hub accounts.
"""

from typing import Annotated

from pydantic import AfterValidator, EmailStr

NormalizedEmail = Annotated[EmailStr, AfterValidator(str.lower)]
