from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()

class EmailOrUsernameModelBackend(ModelBackend):
    """
    Custom backend that allows users to log in using either email or username.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        
        try:
            # Check if username matches email or username field
            user = User.objects.filter(email=username).first() or User.objects.filter(username=username).first()
        except User.DoesNotExist:
            return None
        
        # Check the password and return the user if it's valid
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
