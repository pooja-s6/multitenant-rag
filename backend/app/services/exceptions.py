class AppError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class Unauthorized(AppError):
    pass


class Forbidden(AppError):
    pass


class NotFound(AppError):
    pass


class Conflict(AppError):
    pass


class BadRequest(AppError):
    pass


class PayloadTooLarge(AppError):
    pass


class IngestionError(AppError):
    pass


class BadGateway(AppError):
    pass
