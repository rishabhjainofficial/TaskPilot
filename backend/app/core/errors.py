from typing import Any, Optional
from fastapi import HTTPException, status


class AppError(HTTPException):
    def __init__(
        self,
        status_code: int,
        detail: str,
        code: Optional[str] = None,
        extra: Optional[dict[str, Any]] = None,
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.code = code or "ERROR"
        self.extra = extra or {}


class NotFoundError(AppError):
    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource} '{identifier}' not found",
            code="NOT_FOUND",
        )


class PermissionDeniedError(AppError):
    def __init__(self, permission: str):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: missing '{permission}'",
            code="PERMISSION_DENIED",
        )


class UnauthorizedError(AppError):
    def __init__(self, detail: str = "Invalid or expired authentication credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            code="UNAUTHORIZED",
        )


class TenantMismatchError(AppError):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-tenant access prohibited",
            code="TENANT_MISMATCH",
        )
