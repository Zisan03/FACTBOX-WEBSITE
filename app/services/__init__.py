"""Application services layer.

Encapsulates external service integrations and boundary adapters:
- media: Cloudinary asset management with validation and cleanup
- video: YouTube video identifier extraction and secure embed generation
- email: Internal notification dispatch and retry adapter with safe error codes
"""
