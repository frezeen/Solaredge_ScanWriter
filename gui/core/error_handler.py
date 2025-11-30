"""
Unified error handler for GUI endpoints
Consolidates duplicate error handling logic
"""
from aiohttp import web
from typing import Optional, Tuple
import logging


class UnifiedErrorHandler:
    """Unified error handler for consistent error responses"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

    def handle_api_error(
        self,
        error: Exception,
        context: str,
        default_message: str = "Internal server error"
    ) -> web.Response:
        """
        Handle API errors with consistent logging and response format

        Args:
            error: The exception that occurred
            context: Context string for logging (e.g., "toggling device")
            default_message: Default error message for user

        Returns:
            web.Response with appropriate status code and error message
        """
        error_msg = str(error)
        self.logger.error(f"[GUI] Error {context}: {error}")

        # Determine status code based on error message
        status = self._determine_status_code(error_msg)

        return web.json_response({
            'error': f'{default_message}: {error_msg}'
        }, status=status)

    def handle_validation_error(
        self,
        missing_param: str,
        context: str = ""
    ) -> web.Response:
        """
        Handle validation errors (missing parameters, invalid input)

        Args:
            missing_param: Description of missing/invalid parameter
            context: Optional context for logging

        Returns:
            web.Response with 400 status
        """
        error_msg = f'Missing or invalid parameter: {missing_param}'
        if context:
            self.logger.warning(f"[GUI] Validation error in {context}: {error_msg}")

        return web.json_response({
            'error': error_msg
        }, status=400)

    def handle_not_found_error(
        self,
        resource_type: str,
        resource_id: str,
        context: str = ""
    ) -> web.Response:
        """
        Handle resource not found errors

        Args:
            resource_type: Type of resource (e.g., "device", "endpoint")
            resource_id: ID of the resource
            context: Optional context for logging

        Returns:
            web.Response with 404 status
        """
        error_msg = f'{resource_type.capitalize()} not found: {resource_id}'
        if context:
            self.logger.warning(f"[GUI] Not found in {context}: {error_msg}")

        return web.json_response({
            'error': error_msg
        }, status=404)

    def handle_file_error(
        self,
        file_path: str,
        operation: str,
        error: Exception
    ) -> web.Response:
        """
        Handle file operation errors

        Args:
            file_path: Path to the file
            operation: Operation being performed (e.g., "loading", "saving")
            error: The exception that occurred

        Returns:
            web.Response with appropriate status code
        """
        error_msg = str(error)
        self.logger.error(f"[GUI] Error {operation} {file_path}: {error}")

        # File not found gets 404, other errors get 500
        status = 404 if 'not found' in error_msg.lower() or isinstance(error, FileNotFoundError) else 500

        return web.json_response({
            'error': f'Error {operation} file: {error_msg}'
        }, status=status)

    def create_success_response(
        self,
        message: str,
        data: Optional[dict] = None
    ) -> web.Response:
        """
        Create a consistent success response

        Args:
            message: Success message
            data: Optional additional data to include

        Returns:
            web.Response with success status
        """
        response_data = {
            'success': True,
            'message': message
        }

        if data:
            response_data.update(data)

        return web.json_response(response_data)

    def _determine_status_code(self, error_msg: str) -> int:
        """
        Determine HTTP status code based on error message

        Args:
            error_msg: Error message string

        Returns:
            HTTP status code
        """
        error_lower = error_msg.lower()

        if 'not found' in error_lower:
            return 404
        elif any(keyword in error_lower for keyword in ['missing', 'invalid', 'required']):
            return 400
        else:
            return 500

    def wrap_endpoint(self, handler_func):
        """
        Decorator to wrap endpoint handlers with unified error handling

        Usage:
            @error_handler.wrap_endpoint
            async def my_endpoint(self, request):
                # Your endpoint logic
                return result
        """
        async def wrapper(*args, **kwargs):
            try:
                return await handler_func(*args, **kwargs)
            except Exception as e:
                # Extract context from function name
                context = handler_func.__name__.replace('handle_', '').replace('_', ' ')
                return self.handle_api_error(e, context)

        return wrapper
