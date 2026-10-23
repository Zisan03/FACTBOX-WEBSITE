"""Admin authentication and content management forms.

Enforces server-side validation, length constraints, and CSRF protection.
"""
import re
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from wtforms import (
    StringField,
    PasswordField,
    BooleanField,
    TextAreaField,
    IntegerField,
    SelectField,
    DateField,
)
from wtforms.validators import (
    DataRequired,
    Length,
    Regexp,
    Optional,
    NumberRange,
    ValidationError,
    EqualTo,
)

EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
SLUG_REGEX = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


def slugify(text: str) -> str:
    """Generate a clean, URL-safe slug from text."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


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


class PortfolioCategoryForm(FlaskForm):
    """Form to create or edit portfolio categories."""
    name = StringField(
        "Category Name",
        validators=[
            DataRequired(message="Category name is required."),
            Length(max=100, message="Category name must not exceed 100 characters."),
        ],
    )
    slug = StringField(
        "URL Slug (optional - auto-generated if left blank)",
        validators=[
            Optional(),
            Length(max=100),
            Regexp(SLUG_REGEX, message="Slug must contain only lowercase alphanumeric characters and hyphens."),
        ],
    )
    display_order = IntegerField(
        "Display Order",
        validators=[
            NumberRange(min=0, message="Display order must be 0 or greater."),
        ],
        default=0,
    )
    is_active = BooleanField("Active (Available for projects)", default=True)


class PortfolioProjectForm(FlaskForm):
    """Form to create or edit portfolio projects."""
    title = StringField(
        "Project Title",
        validators=[
            DataRequired(message="Project title is required."),
            Length(max=255, message="Title must not exceed 255 characters."),
        ],
    )
    slug = StringField(
        "URL Slug (optional - auto-generated if left blank)",
        validators=[
            Optional(),
            Length(max=255),
            Regexp(SLUG_REGEX, message="Slug must contain only lowercase alphanumeric characters and hyphens."),
        ],
    )
    category_id = SelectField(
        "Category",
        validators=[DataRequired(message="Please select a category.")],
    )
    summary = TextAreaField(
        "Summary (Brief card overview)",
        validators=[
            DataRequired(message="Project summary is required."),
            Length(max=500, message="Summary must not exceed 500 characters."),
        ],
    )
    description = TextAreaField(
        "Detailed Description (Plain text with paragraph breaks)",
        validators=[
            DataRequired(message="Project description is required."),
        ],
    )
    client_name = StringField(
        "Client / Partner Name (Optional - only if approved for publication)",
        validators=[
            Optional(),
            Length(max=255),
        ],
    )
    project_date = DateField(
        "Project Date (Optional)",
        validators=[Optional()],
    )
    display_order = IntegerField(
        "Display Order",
        validators=[
            NumberRange(min=0, message="Display order must be 0 or greater."),
        ],
        default=0,
    )
    is_featured = BooleanField("Featured Project (Highlighted on Home/Work)", default=False)
    status = SelectField(
        "Publication Status",
        choices=[
            ("draft", "Draft — Internal preview only (hidden from public site)"),
            ("published", "Published — Live on public website"),
        ],
        default="draft",
        validators=[DataRequired()],
    )


class PortfolioImageUploadForm(FlaskForm):
    """Form to upload a new portfolio image to Cloudinary."""
    image_file = FileField(
        "Image File (JPG, PNG, WebP up to 10 MB)",
        validators=[
            FileRequired(message="Please select an image file to upload."),
        ],
    )
    alt_text = StringField(
        "Alternative Text (SEO & Accessibility)",
        validators=[
            DataRequired(message="Alternative text is required for accessibility."),
            Length(max=255),
        ],
    )
    caption = StringField(
        "Caption (Optional displayed description)",
        validators=[
            Optional(),
            Length(max=500),
        ],
    )
    display_order = IntegerField(
        "Display Order",
        validators=[NumberRange(min=0)],
        default=0,
    )


class PortfolioImageEditForm(FlaskForm):
    """Form to update metadata of an existing portfolio image."""
    alt_text = StringField(
        "Alternative Text (SEO & Accessibility)",
        validators=[
            DataRequired(message="Alternative text is required."),
            Length(max=255),
        ],
    )
    caption = StringField(
        "Caption (Optional)",
        validators=[
            Optional(),
            Length(max=500),
        ],
    )
    display_order = IntegerField(
        "Display Order",
        validators=[NumberRange(min=0)],
        default=0,
    )


class PortfolioVideoForm(FlaskForm):
    """Form to add or edit YouTube video embeds."""
    youtube_url = StringField(
        "YouTube Link or Video ID",
        validators=[
            DataRequired(message="YouTube link or video ID is required."),
            Length(max=255),
        ],
    )
    title = StringField(
        "Video Title (Optional display label)",
        validators=[
            Optional(),
            Length(max=255),
        ],
    )
    display_order = IntegerField(
        "Display Order",
        validators=[NumberRange(min=0)],
        default=0,
    )


class ServiceForm(FlaskForm):
    """Form to create or edit consulting services."""
    title = StringField(
        "Service Title",
        validators=[
            DataRequired(message="Service title is required."),
            Length(max=255),
        ],
    )
    slug = StringField(
        "URL Slug (optional - auto-generated if left blank)",
        validators=[
            Optional(),
            Length(max=255),
            Regexp(SLUG_REGEX, message="Slug must contain only lowercase alphanumeric characters and hyphens."),
        ],
    )
    summary = TextAreaField(
        "Summary (Brief card overview)",
        validators=[
            DataRequired(message="Summary is required."),
            Length(max=500),
        ],
    )
    description = TextAreaField(
        "Full Description (Plain text with paragraph breaks)",
        validators=[
            DataRequired(message="Description is required."),
        ],
    )
    icon_key = SelectField(
        "Service Icon",
        choices=[
            ("film", "Audiovisual Production (Camera/Film)"),
            ("search", "Investigative Research (Magnifying Glass)"),
            ("megaphone", "Strategic Communications (Megaphone)"),
            ("briefcase", "Consulting & Advisory (Briefcase)"),
            ("document-text", "Policy & Reporting (Document)"),
            ("lightbulb", "Strategy & Innovation (Lightbulb)"),
        ],
        default="film",
    )
    display_order = IntegerField(
        "Display Order",
        validators=[NumberRange(min=0)],
        default=0,
    )
    is_published = BooleanField("Published (Visible on public Services page)", default=False)


class HomePagePhotoForm(FlaskForm):
    """Form to upload a new home page hero background photo."""
    image_file = FileField(
        "Image File (JPG, PNG, WebP up to 10 MB)",
        validators=[
            FileRequired(message="Please select an image file to upload."),
        ],
    )
    title = StringField(
        "Photo Title / Label (Optional)",
        validators=[
            Optional(),
            Length(max=255),
        ],
    )
    alt_text = StringField(
        "Alternative Text (SEO & Accessibility)",
        validators=[
            DataRequired(message="Alternative text is required for accessibility."),
            Length(max=255),
        ],
    )
    caption = TextAreaField(
        "Caption (Optional)",
        validators=[
            Optional(),
            Length(max=500),
        ],
    )
    display_order = IntegerField(
        "Display Order",
        validators=[NumberRange(min=0, message="Display order must be 0 or greater.")],
        default=0,
    )
    is_active = BooleanField("Active in Hero Slideshow", default=True)


class HomePagePhotoEditForm(FlaskForm):
    """Form to edit metadata of an existing home page photo."""
    title = StringField(
        "Photo Title / Label (Optional)",
        validators=[
            Optional(),
            Length(max=255),
        ],
    )
    alt_text = StringField(
        "Alternative Text (SEO & Accessibility)",
        validators=[
            DataRequired(message="Alternative text is required for accessibility."),
            Length(max=255),
        ],
    )
    caption = TextAreaField(
        "Caption (Optional)",
        validators=[
            Optional(),
            Length(max=500),
        ],
    )
    display_order = IntegerField(
        "Display Order",
        validators=[NumberRange(min=0, message="Display order must be 0 or greater.")],
        default=0,
    )
    is_active = BooleanField("Active in Hero Slideshow", default=True)


# ============================================================================
# Admin Password Management & Recovery Forms
# ============================================================================

class AdminChangePasswordForm(FlaskForm):
    """Form for authenticated administrator to update their password."""
    current_password = PasswordField(
        "Current Password",
        validators=[
            DataRequired(message="Your current password is required."),
        ],
    )
    new_password = PasswordField(
        "New Password",
        validators=[
            DataRequired(message="New password is required."),
            Length(min=8, message="New password must be at least 8 characters long."),
        ],
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[
            DataRequired(message="Please confirm your new password."),
            EqualTo("new_password", message="New passwords must match."),
        ],
    )


class AdminForgotPasswordRequestForm(FlaskForm):
    """Form to initiate a password recovery email."""
    email = StringField(
        "Administrator Email Address",
        validators=[
            DataRequired(message="Email address is required."),
            Regexp(EMAIL_REGEX, message="Please provide a valid email address."),
            Length(max=255),
        ],
    )


class AdminResetPasswordForm(FlaskForm):
    """Form to submit a new password via timed reset token."""
    new_password = PasswordField(
        "New Password",
        validators=[
            DataRequired(message="New password is required."),
            Length(min=8, message="New password must be at least 8 characters long."),
        ],
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[
            DataRequired(message="Please confirm your new password."),
            EqualTo("new_password", message="Passwords must match."),
        ],
    )


# ============================================================================
# Partner & Organization Logo Management Forms
# ============================================================================

class PartnerLogoUploadForm(FlaskForm):
    """Form to upload and register a partner or collaborating organization logo."""
    logo_file = FileField(
        "Logo Image File (PNG, JPG, WebP, GIF)",
        validators=[
            FileRequired(message="A logo image file is required."),
        ],
    )
    name = StringField(
        "Organization / Partner Name",
        validators=[
            DataRequired(message="Organization name is required."),
            Length(max=150, message="Organization name must be 150 characters or less."),
        ],
    )
    website_url = StringField(
        "Organization Website URL (Optional)",
        validators=[
            Optional(),
            Length(max=500),
        ],
    )
    alt_text = StringField(
        "Alternative Text (SEO & Accessibility)",
        validators=[
            DataRequired(message="Alternative text is required for accessibility."),
            Length(max=255),
        ],
    )
    display_order = IntegerField(
        "Display Order",
        validators=[NumberRange(min=0, message="Display order must be 0 or greater.")],
        default=0,
    )
    is_published = BooleanField("Visible on Website Footer", default=True)


class PartnerLogoEditForm(FlaskForm):
    """Form to edit metadata or optionally replace an existing partner logo."""
    logo_file = FileField(
        "Replace Logo Image File (Optional)",
        validators=[
            Optional(),
        ],
    )
    name = StringField(
        "Organization / Partner Name",
        validators=[
            DataRequired(message="Organization name is required."),
            Length(max=150, message="Organization name must be 150 characters or less."),
        ],
    )
    website_url = StringField(
        "Organization Website URL (Optional)",
        validators=[
            Optional(),
            Length(max=500),
        ],
    )
    alt_text = StringField(
        "Alternative Text (SEO & Accessibility)",
        validators=[
            DataRequired(message="Alternative text is required for accessibility."),
            Length(max=255),
        ],
    )
    display_order = IntegerField(
        "Display Order",
        validators=[NumberRange(min=0, message="Display order must be 0 or greater.")],
        default=0,
    )
    is_published = BooleanField("Visible on Website Footer", default=True)


