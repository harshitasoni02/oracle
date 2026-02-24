"""
Custom JWT Authentication for Shizuha Oracle

This authentication class validates JWT tokens issued by Shizuha ID
without requiring the user to exist in the local database.
"""

import logging
from rest_framework import authentication, exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


class FederatedUser:
    """
    A lightweight user object for federated authentication.
    Used when the user exists in Shizuha ID but not in the local database.
    """
    def __init__(self, user_id, email=None, username=None, first_name=None, last_name=None, enabled_services=None):
        self.id = user_id
        self.pk = user_id
        self.email = email or f"user_{user_id}@shizuha.id"
        self.username = username or f"user_{user_id}"
        self.first_name = first_name or ""
        self.last_name = last_name or ""
        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False
        self.is_staff = False
        self.is_superuser = False
        # None = unrestricted (staff/superuser), [] = no services, [...] = specific services
        self.enabled_services = enabled_services

    def __str__(self):
        return f"FederatedUser({self.id})"

    def save(self, *args, **kwargs):
        pass  # No-op for federated users

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username


class ShizuhaJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication that works with Shizuha ID tokens.

    If the user doesn't exist locally, creates a FederatedUser object
    from the token claims instead of failing with 401.
    """

    def get_user(self, validated_token):
        """
        Get the user from the validated token.
        If user doesn't exist locally, return a FederatedUser.
        """
        try:
            user_id = validated_token.get('user_id')
            if user_id is None:
                raise InvalidToken('Token contained no recognizable user identification')

            # Extract enabled_services from token
            enabled_services = validated_token.get('enabled_services')
            if validated_token.get('is_staff') or validated_token.get('is_superuser'):
                enabled_services = None

            # Try to get the user from the local database first
            try:
                user = User.objects.get(pk=user_id)
                return user
            except User.DoesNotExist:
                # User doesn't exist locally - create a federated user from token claims
                logger.debug(f"User {user_id} not found locally, using federated user")

                # Extract additional claims if available
                email = validated_token.get('email')
                username = validated_token.get('username')
                first_name = validated_token.get('first_name')
                last_name = validated_token.get('last_name')

                return FederatedUser(
                    user_id=user_id,
                    email=email,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    enabled_services=enabled_services
                )

        except KeyError:
            raise InvalidToken('Token contained no recognizable user identification')


class ShizuhaIDAuthentication(authentication.BaseAuthentication):
    """
    Alternative authentication that validates tokens against Shizuha ID service.
    """

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if not auth_header.startswith('Bearer '):
            return None

        token = auth_header.split(' ')[1]

        try:
            # Validate the token locally first (fast path)
            validated_token = AccessToken(token)
            user_id = validated_token.get('user_id')

            if user_id is None:
                raise exceptions.AuthenticationFailed('Invalid token')

            # Extract enabled_services from token
            enabled_services = validated_token.get('enabled_services')
            if validated_token.get('is_staff') or validated_token.get('is_superuser'):
                enabled_services = None

            # Try local user first
            try:
                user = User.objects.get(pk=user_id)
                return (user, validated_token)
            except User.DoesNotExist:
                # Create federated user
                email = validated_token.get('email')
                username = validated_token.get('username')
                first_name = validated_token.get('first_name')
                last_name = validated_token.get('last_name')

                federated_user = FederatedUser(
                    user_id=user_id,
                    email=email,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    enabled_services=enabled_services
                )
                return (federated_user, validated_token)

        except TokenError as e:
            raise exceptions.AuthenticationFailed(f'Invalid token: {str(e)}')

    def authenticate_header(self, request):
        return 'Bearer realm="api"'
