"""tasador-core: single source of truth for the Tasador SD domain.

Every component of the suite (training, data agent, API, exports for the
mobile app) imports schema constants, validation and model helpers from
here instead of keeping its own copy. Before this package existed the
sector list lived in three files and the validation ranges disagreed
across clients; this is the fix.
"""

from tasador_core.schema import (
    COLUMNS,
    FEATURES,
    KNOWN_SECTORS,
    NUMERIC_FEATURES,
    RANGES,
    TARGET,
    normalize_sector,
    validate_appraisal_input,
    validate_listing,
)

__all__ = [
    "COLUMNS",
    "FEATURES",
    "KNOWN_SECTORS",
    "NUMERIC_FEATURES",
    "RANGES",
    "TARGET",
    "normalize_sector",
    "validate_appraisal_input",
    "validate_listing",
]
