"""Compatibility facade for the trusted remediation domain.

New code should import from :mod:`app.services.remediation`; this module
keeps the established public import path stable for existing callers.
"""

from app.services.remediation import (
    PatchValidationResult,
    RemediationGenerationResult,
    RemediationService,
    validate_unified_patch,
)

__all__ = [
    "PatchValidationResult",
    "RemediationGenerationResult",
    "RemediationService",
    "validate_unified_patch",
]
