from fastapi import HTTPException, status


def not_ready(feature: str, phase: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"{feature} is implemented in {phase}.",
    )
