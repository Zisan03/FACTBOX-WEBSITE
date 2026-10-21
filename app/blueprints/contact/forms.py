"""Contact form specification.

Implements server-side validation, length constraints, CSRF protection,
and honeypot anti-spam protection (PRD FR-05).
"""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField
from wtforms.validators import DataRequired, Regexp, Length, Optional


class ContactEnquiryForm(FlaskForm):
    """Public contact enquiry form with server-side validation and honeypot."""

    full_name = StringField(
        "Full Name",
        validators=[
            DataRequired(message="Please provide your full name."),
            Length(max=150, message="Full name cannot exceed 150 characters."),
        ],
    )
    organization = StringField(
        "Organization",
        validators=[
            Optional(),
            Length(max=150, message="Organization cannot exceed 150 characters."),
        ],
    )
    email = StringField(
        "Email Address",
        validators=[
            DataRequired(message="Please provide your email address."),
            Regexp(
                r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
                message="Please provide a valid email address.",
            ),
            Length(max=255, message="Email address cannot exceed 255 characters."),
        ],
    )
    phone = StringField(
        "Phone Number",
        validators=[
            Optional(),
            Length(max=50, message="Phone number cannot exceed 50 characters."),
        ],
    )
    subject = StringField(
        "Subject",
        validators=[
            DataRequired(message="Please provide a subject for your enquiry."),
            Length(max=200, message="Subject cannot exceed 200 characters."),
        ],
    )
    message = TextAreaField(
        "Message",
        validators=[
            DataRequired(message="Please provide your message."),
            Length(min=10, max=5000, message="Message must be between 10 and 5,000 characters."),
        ],
    )
    # Honeypot field (hidden from legitimate users, filled by spam bots)
    company_website = StringField(
        "Website",
        validators=[
            Optional(),
            Length(max=100),
        ],
    )
