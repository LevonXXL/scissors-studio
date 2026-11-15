from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from django.test import SimpleTestCase

from .unified_excel_import import is_unified_workbook
from .excel_import import read_xlsx
from .xlsx_security import validate_xlsx_archive, worksheet_path


class XlsxSecurityTests(SimpleTestCase):
    def test_rejects_zip_bomb_before_reading_xml(self):
        output = BytesIO()
        with ZipFile(output, 'w', compression=ZIP_DEFLATED) as archive:
            archive.writestr('xl/workbook.xml', b'a' * 21_000_000)
        content = output.getvalue()
        self.assertLess(len(content), 5_000_000)
        with ZipFile(BytesIO(content)) as archive:
            with self.assertRaisesRegex(ValueError, 'слишком большой'):
                validate_xlsx_archive(archive, len(content))
        self.assertFalse(is_unified_workbook(content))

    def test_sheet_relationship_cannot_escape_worksheets(self):
        self.assertEqual(worksheet_path('worksheets/sheet1.xml'), 'xl/worksheets/sheet1.xml')
        for target in ('../secret.xml', 'worksheets/../../secret.xml',
                       'worksheets\\sheet1.xml', 'external.xml'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                worksheet_path(target)

    def test_malformed_zip_becomes_validation_error(self):
        with self.assertRaisesRegex(ValueError, 'Повреждённый'):
            read_xlsx(b'PK\x03\x04not-a-zip')
