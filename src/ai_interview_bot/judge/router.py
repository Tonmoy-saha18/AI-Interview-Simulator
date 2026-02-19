"""Judge HTTP endpoints — placeholder for Phase 2.

Will proxy code run/submit requests to the standalone Judge Service.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/judge", tags=["judge"])
