"""Application error types rendered through the shared API error contract:

    {"error": {"code": "...", "message": "...", "request_id": "..."}}
"""


class AppError(Exception):
    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None):
        if message is not None:
            self.message = message
        super().__init__(self.message)


class UnauthorizedError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"
    message = "Authentication required or invalid credentials."


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"
    message = "You do not have access to this resource."


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    message = "Resource was not found."


class PaperNotFoundError(NotFoundError):
    code = "PAPER_NOT_FOUND"
    message = "Paper was not found."


class DocumentNotFoundError(NotFoundError):
    code = "DOCUMENT_NOT_FOUND"
    message = "Document was not found."


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"
    message = "The request conflicts with existing data."


class EmailAlreadyRegisteredError(ConflictError):
    code = "EMAIL_ALREADY_REGISTERED"
    message = "This email is already registered."


class RequestValidationAppError(AppError):
    status_code = 400
    code = "VALIDATION_ERROR"
    message = "Invalid request."


class DocumentProcessingFailedError(AppError):
    status_code = 500
    code = "DOCUMENT_PROCESSING_FAILED"
    message = "Document processing failed."


class RAGUnavailableError(AppError):
    status_code = 503
    code = "RAG_UNAVAILABLE"
    message = "The RAG service is currently unavailable."


class KnowledgeGraphUnavailableError(AppError):
    status_code = 503
    code = "KNOWLEDGE_GRAPH_UNAVAILABLE"
    message = "The knowledge graph service is not available yet."
