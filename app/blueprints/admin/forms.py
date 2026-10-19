"""Admin authentication and content forms.

Enforces server-side validation and CSRF protection.
"""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Length, Regexp

EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class AdminLoginForm(FlaskForm):
    """Administrator login form."""
    email = StringField(
        "Email Address",
        validators=[
            DataRequired(message="Email address is required."),
            Regexp(EMAIL_REGEX, message="Please provide a valid email address."),
            Length(max=255),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required."),
        ],
    )
    remember = BooleanField("Keep me signed in", default=False)
