import os
from pathlib import Path
from stat import S_IMODE
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase, override_settings

from .upload_handlers import ScissorsTemporaryFileUploadHandler


class TemporaryUploadTests(SimpleTestCase):
    def test_temp_name_is_random_and_independent_of_submitted_name(self):
        with TemporaryDirectory() as directory, override_settings(FILE_UPLOAD_TEMP_DIR=directory):
            paths = []
            for submitted_name in ('../../escape.jpg', 'sensitive-name.svg'):
                handler = ScissorsTemporaryFileUploadHandler()
                handler.new_file('image', submitted_name, 'image/jpeg', 4, None)
                path = Path(handler.file.temporary_file_path())
                paths.append(path)
                self.assertEqual(path.parent, Path(directory))
                self.assertRegex(path.name, r'^scissors-[a-z0-9_]+\.upload$')
                self.assertNotIn('escape', path.name)
                self.assertNotIn('sensitive', path.name)
                self.assertEqual(S_IMODE(path.stat().st_mode), 0o600)
                handler.receive_data_chunk(b'data', 0)
                self.assertEqual(handler.file_complete(4).read(), b'data')
                handler.file.close()
                self.assertFalse(path.exists())
            self.assertNotEqual(paths[0].name, paths[1].name)
            self.assertFalse((Path(directory).parent / 'escape.jpg').exists())

    def test_private_upload_directory_is_configurable(self):
        with TemporaryDirectory() as directory, override_settings(FILE_UPLOAD_TEMP_DIR=directory):
            handler = ScissorsTemporaryFileUploadHandler()
            handler.new_file('image', 'photo.png', 'image/png', 1, None)
            self.addCleanup(handler.file.close)
            self.assertEqual(os.path.dirname(handler.file.temporary_file_path()), directory)
