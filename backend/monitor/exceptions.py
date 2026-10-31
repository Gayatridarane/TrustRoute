import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    """DRF handler that never leaks stack traces for unexpected errors."""
    response = exception_handler(exc, context)
    if response is not None:
        return response
    logger.exception("Unhandled error in API view", exc_info=exc)
    return Response({"detail": "An unexpected server error occurred."}, status=500)
