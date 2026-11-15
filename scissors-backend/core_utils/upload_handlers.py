"""Store large request bodies in private, randomly named temporary files."""

import tempfile

from django.conf import settings
from django.core.files.uploadedfile import TemporaryUploadedFile, UploadedFile
from django.core.files.uploadhandler import FileUploadHandler, TemporaryFileUploadHandler


class ScissorsTemporaryUploadedFile(TemporaryUploadedFile):
    def __init__(self, name, content_type, size, charset, content_type_extra=None):
        file = tempfile.NamedTemporaryFile(
            prefix='scissors-', suffix='.upload', dir=settings.FILE_UPLOAD_TEMP_DIR,
        )
        UploadedFile.__init__(self, file, name, content_type, size, charset, content_type_extra)


class ScissorsTemporaryFileUploadHandler(TemporaryFileUploadHandler):
    def new_file(self, *args, **kwargs):
        # Preserve the submitted name only as metadata; never use it for a disk path.
        FileUploadHandler.new_file(self, *args, **kwargs)
        self.file = ScissorsTemporaryUploadedFile(
            self.file_name, self.content_type, 0, self.charset, self.content_type_extra,
        )
