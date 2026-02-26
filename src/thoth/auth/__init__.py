"""
Authentication package for Thoth multi-user support.

Provides simple token-based authentication for isolating user data
in multi-tenant deployments.
"""

from thoth.auth.dependencies import get_user_context
from thoth.auth.middleware import TokenAuthMiddleware
from thoth.auth.models import User
from thoth.auth.service import AuthService

__all__ = [
    'AuthService',
    'TokenAuthMiddleware',
    'User',
    'get_user_context',
]
