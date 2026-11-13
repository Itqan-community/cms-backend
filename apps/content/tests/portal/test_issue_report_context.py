from django.core import mail
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import translation
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetTemplateChoice,
    CategoryChoice,
    ContentIssueReport,
    MushafLayout,
    Qiraah,
    Reciter,
    StatusChoice,
)
from apps.content.services.issue_context import format_issue_context
from apps.content.services.issue_report_notifications import IssueReportNotificationService
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class IssueReportContextTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Context Publisher")
        self.staff_user = User.objects.create_user(email="ctx-staff@example.com", password="password123", is_staff=True)
        self.recitation = baker.make(
            Asset,
            publisher=self.publisher,
            category=CategoryChoice.RECITATION,
            reciter=baker.make(Reciter, name="Context Reciter"),
            qiraah=baker.make(Qiraah, name="Context Qiraah"),
            status=StatusChoice.READY,
        )
        self.text = baker.make(
            Asset,
            publisher=self.publisher,
            category=CategoryChoice.TEXT,
            template=AssetTemplateChoice.AYAH,
            status=StatusChoice.READY,
        )
        self.mushaf = baker.make(Asset, publisher=self.publisher, category=CategoryChoice.MUSHAF)
        self.font = baker.make(Asset, publisher=self.publisher, category=CategoryChoice.FONT)
        self.program = baker.make(Asset, publisher=self.publisher, category=CategoryChoice.PROGRAM)

    def _post(self, asset: Asset, context: object = None, *, with_context: bool = True):
        payload: dict = {"asset_id": asset.id, "description": "Something is wrong here."}
        if with_context:
            payload["context"] = context
        return self.client.post("/portal/issue-reports/", payload, format="json")

    def _assert_invalid(self, response, message_part: str) -> None:
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("invalid_issue_context", response.json()["error_name"])
        self.assertIn(message_part, response.json()["message"])

    # --- Create: valid context per category ---

    def test_create_issue_report_where_recitation_has_surah_and_ayah_should_store_context(self):
        # Arrange
        self.authenticate_user(self.staff_user)

        # Act
        response = self._post(self.recitation, {"surah": 2, "ayah": 255})

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        data = response.json()
        self.assertEqual({"surah": 2, "ayah": 255}, data["context"])
        self.assertEqual("Al-Baqarah 2:255", data["context_label"])
        self.assertEqual("recitation", data["asset_category"])
        self.assertEqual({"surah": 2, "ayah": 255}, ContentIssueReport.objects.get(pk=data["id"]).context)

    def test_create_issue_report_where_surah_or_ayah_missing_should_return_400(self):
        # Arrange
        self.authenticate_user(self.staff_user)

        # Act
        surah_only = self._post(self.recitation, {"surah": 114, "ayah": None})
        ayah_only = self._post(self.text, {"ayah": 5})
        omitted = self._post(self.recitation, with_context=False)
        null = self._post(self.text, None)

        # Assert
        for response in (surah_only, ayah_only, omitted, null):
            self._assert_invalid(response, "Choose the surah and ayah.")
        self.assertFalse(ContentIssueReport.objects.exists())

    def test_create_issue_report_where_mushaf_page_missing_should_return_400(self):
        # Arrange
        self.authenticate_user(self.staff_user)

        # Act
        omitted = self._post(self.mushaf, with_context=False)
        empty = self._post(self.mushaf, {})

        # Assert
        self._assert_invalid(omitted, "Enter the page.")
        self._assert_invalid(empty, "Enter the page.")

    def test_create_issue_report_where_font_has_neither_page_nor_glyph_should_return_400(self):
        # Arrange
        self.authenticate_user(self.staff_user)

        # Act
        blank = self._post(self.font, {"page": None, "glyph": "  "})
        omitted = self._post(self.font, with_context=False)

        # Assert
        self._assert_invalid(blank, "Enter the page or the glyph.")
        self._assert_invalid(omitted, "Enter the page or the glyph.")

    def test_create_issue_report_where_missing_location_in_arabic_should_return_arabic_message(self):
        # Arrange
        self.authenticate_user(self.staff_user, language="ar")

        # Act
        response = self._post(self.recitation, with_context=False)

        # Assert
        self._assert_invalid(response, "اختر السورة والآية.")

    def test_create_issue_report_where_text_asset_has_surah_and_ayah_should_store_context(self):
        # Arrange
        self.authenticate_user(self.staff_user)

        # Act
        response = self._post(self.text, {"surah": 1, "ayah": 7})

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        self.assertEqual({"surah": 1, "ayah": 7}, response.json()["context"])

    def test_create_issue_report_where_mushaf_has_page_should_store_context(self):
        # Arrange
        self.authenticate_user(self.staff_user)

        # Act
        response = self._post(self.mushaf, {"page": 12})

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        self.assertEqual({"page": 12}, response.json()["context"])
        self.assertEqual("Page 12", response.json()["context_label"])

    def test_create_issue_report_where_font_has_page_and_glyph_should_store_both(self):
        # Arrange
        self.authenticate_user(self.staff_user)

        # Act
        response = self._post(self.font, {"page": 3, "glyph": "  ﷽ "})

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        self.assertEqual({"page": 3, "glyph": "﷽"}, response.json()["context"])
        self.assertEqual("Page 3 · Glyph “﷽”", response.json()["context_label"])

    def test_create_issue_report_where_font_has_glyph_only_should_store_glyph(self):
        # Arrange
        self.authenticate_user(self.staff_user)

        # Act
        response = self._post(self.font, {"glyph": "lam-alef"})

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        self.assertEqual({"glyph": "lam-alef"}, response.json()["context"])

    def test_create_issue_report_where_program_has_no_context_should_store_null(self):
        # Arrange
        self.authenticate_user(self.staff_user)

        # Act
        omitted = self._post(self.program, with_context=False)
        empty = self._post(self.program, {})
        null = self._post(self.program, None)

        # Assert
        for response in (omitted, empty, null):
            self.assertEqual(201, response.status_code, response.content)
            self.assertIsNone(response.json()["context"])
            self.assertEqual("", response.json()["context_label"])

    # --- Create: invalid context per category ---

    def test_create_issue_report_where_surah_out_of_range_should_return_400(self):
        # Arrange
        self.authenticate_user(self.staff_user)

        # Act
        too_high = self._post(self.recitation, {"surah": 115, "ayah": 1})
        zero = self._post(self.text, {"surah": 0, "ayah": 1})

        # Assert
        self._assert_invalid(too_high, "Surah must be between 1 and 114.")
        self._assert_invalid(zero, "Surah must be between 1 and 114.")
        self.assertFalse(ContentIssueReport.objects.exists())

    def test_create_issue_report_where_ayah_past_surah_end_should_return_400(self):
        # Arrange
        self.authenticate_user(self.staff_user)

        # Act
        past_end = self._post(self.recitation, {"surah": 1, "ayah": 8})
        zero = self._post(self.text, {"surah": 2, "ayah": 0})

        # Assert
        self._assert_invalid(past_end, "between 1 and 7 for surah 1")
        self._assert_invalid(zero, "between 1 and 286 for surah 2")

    def test_create_issue_report_where_wrong_fields_for_category_should_return_400(self):
        # Arrange
        self.authenticate_user(self.staff_user)

        # Act
        page_on_recitation = self._post(self.recitation, {"surah": 1, "ayah": 1, "page": 4})
        surah_on_mushaf = self._post(self.mushaf, {"page": 1, "surah": 2})
        string_number = self._post(self.text, {"surah": "2", "ayah": 1})
        boolean_page = self._post(self.mushaf, {"page": True})

        # Assert
        for response in (page_on_recitation, surah_on_mushaf, string_number, boolean_page):
            self._assert_invalid(response, "does not fit this asset type")

    def test_create_issue_report_where_program_has_context_should_return_400(self):
        # Arrange
        self.authenticate_user(self.staff_user)

        # Act
        response = self._post(self.program, {"page": 1})

        # Assert
        self._assert_invalid(response, "does not take an issue location")

    def test_create_issue_report_where_context_not_object_should_return_400(self):
        # Arrange
        self.authenticate_user(self.staff_user)

        # Act
        response = self._post(self.mushaf, [1, 2])

        # Assert
        self.assertEqual(400, response.status_code)
        self.assertEqual("validation_error", response.json()["error_name"])

    def test_create_issue_report_where_page_not_positive_should_return_400(self):
        # Arrange
        self.authenticate_user(self.staff_user)

        # Act
        zero = self._post(self.mushaf, {"page": 0})
        font_negative = self._post(self.font, {"page": -3})

        # Assert
        self._assert_invalid(zero, "Page must be between 1 and 32767.")
        self._assert_invalid(font_negative, "Page must be between 1 and 32767.")

    def test_create_issue_report_where_page_past_layout_page_count_should_return_400(self):
        # Arrange: a page-template text asset is the only asset that carries a layout today, so
        # exercise the bound through the shared validator directly with a mushaf-shaped asset.
        from apps.content.services.issue_context import validate_issue_context
        from apps.core.ninja_utils.errors import ItqanError

        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)
        asset = Asset(category=CategoryChoice.MUSHAF, mushaf_layout=layout)

        # Act
        within = validate_issue_context(asset, {"page": 604})
        with self.assertRaises(ItqanError) as raised:
            validate_issue_context(asset, {"page": 605})

        # Assert
        self.assertEqual({"page": 604}, within)
        self.assertEqual("invalid_issue_context", raised.exception.error_name)
        self.assertIn("between 1 and 604", str(raised.exception.message))

    def test_create_issue_report_where_glyph_too_long_should_return_400(self):
        # Arrange
        self.authenticate_user(self.staff_user)

        # Act
        response = self._post(self.font, {"glyph": "x" * 33})

        # Assert
        self._assert_invalid(response, "Glyph cannot exceed 32 characters.")

    def test_create_issue_report_where_invalid_context_in_arabic_should_return_arabic_message(self):
        # Arrange
        self.authenticate_user(self.staff_user, language="ar")

        # Act
        response = self._post(self.recitation, {"surah": 200, "ayah": 1})

        # Assert
        self._assert_invalid(response, "يجب أن يكون رقم السورة بين 1 و114.")

    # --- Update ---

    def test_update_issue_report_where_context_given_should_replace_it(self):
        # Arrange
        report = baker.make(
            ContentIssueReport,
            reporter=self.staff_user,
            asset=self.recitation,
            description="An existing issue description.",
            context={"surah": 1, "ayah": 1},
        )
        self.authenticate_user(self.staff_user)

        # Act
        replaced = self.client.patch(
            f"/portal/issue-reports/{report.id}/", {"context": {"surah": 3, "ayah": 7}}, format="json"
        )
        kept = self.client.patch(f"/portal/issue-reports/{report.id}/", {"status": "resolved"}, format="json")
        invalid = self.client.patch(
            f"/portal/issue-reports/{report.id}/", {"context": {"surah": 3, "ayah": 201}}, format="json"
        )
        cleared = self.client.patch(f"/portal/issue-reports/{report.id}/", {"context": None}, format="json")
        incomplete = self.client.patch(f"/portal/issue-reports/{report.id}/", {"context": {"surah": 3}}, format="json")

        # Assert
        self.assertEqual({"surah": 3, "ayah": 7}, replaced.json()["context"])
        self.assertEqual({"surah": 3, "ayah": 7}, kept.json()["context"])
        self._assert_invalid(invalid, "between 1 and 200 for surah 3")
        self._assert_invalid(cleared, "Choose the surah and ayah.")
        self._assert_invalid(incomplete, "Choose the surah and ayah.")
        report.refresh_from_db()
        self.assertEqual({"surah": 3, "ayah": 7}, report.context)

    def test_update_issue_report_where_old_report_has_no_context_should_still_change_other_fields(self):
        # Arrange
        report = baker.make(
            ContentIssueReport,
            reporter=self.staff_user,
            asset=self.mushaf,
            description="An old report from before locations.",
            context=None,
        )
        self.authenticate_user(self.staff_user)

        # Act
        response = self.client.patch(
            f"/portal/issue-reports/{report.id}/",
            {"status": "resolved", "description": "An old report, now resolved."},
            format="json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("resolved", response.json()["status"])
        self.assertIsNone(response.json()["context"])
        self.assertEqual("", response.json()["context_label"])

    # --- List / detail ---

    def test_list_issue_reports_where_mixed_contexts_should_return_context_and_label(self):
        # Arrange
        baker.make(
            ContentIssueReport,
            reporter=self.staff_user,
            asset=self.recitation,
            description="Old report without context.",
            context=None,
        )
        baker.make(
            ContentIssueReport,
            reporter=self.staff_user,
            asset=self.mushaf,
            description="A report on a page.",
            context={"page": 12},
        )
        self.authenticate_user(self.staff_user)

        # Act
        response = self.client.get("/portal/issue-reports/?ordering=created_at")

        # Assert
        self.assertEqual(200, response.status_code)
        results = response.json()["results"]
        self.assertEqual([None, {"page": 12}], [row["context"] for row in results])
        self.assertEqual(["", "Page 12"], [row["context_label"] for row in results])
        self.assertEqual(["recitation", "mushaf"], [row["asset_category"] for row in results])

    def test_get_issue_report_where_context_in_arabic_should_return_arabic_label(self):
        # Arrange
        report = baker.make(
            ContentIssueReport,
            reporter=self.staff_user,
            asset=self.text,
            description="A report on an ayah.",
            context={"surah": 2, "ayah": 255},
        )
        self.authenticate_user(self.staff_user, language="ar")

        # Act
        response = self.client.get(f"/portal/issue-reports/{report.id}/")

        # Assert
        self.assertEqual(200, response.status_code)
        self.assertEqual("البقرة 2:255", response.json()["context_label"])

    def test_list_issue_reports_where_more_rows_should_not_add_queries(self):
        # Arrange
        def make_reports(count: int) -> None:
            for index in range(count):
                baker.make(
                    ContentIssueReport,
                    reporter=self.staff_user,
                    asset=self.font,
                    description="A report on a glyph.",
                    context={"page": index + 1, "glyph": "ب"},
                )

        make_reports(2)
        self.authenticate_user(self.staff_user)

        # Act
        with CaptureQueriesContext(connection) as few:
            first = self.client.get("/portal/issue-reports/")
        make_reports(10)
        with CaptureQueriesContext(connection) as many:
            second = self.client.get("/portal/issue-reports/")

        # Assert
        self.assertEqual(200, first.status_code)
        self.assertEqual(12, second.json()["count"])
        self.assertEqual(len(few), len(many))

    def test_create_issue_report_where_context_given_should_not_add_queries(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self._post(self.program, with_context=False)  # warm up the auth/session queries

        # Act
        with CaptureQueriesContext(connection) as without_context:
            self._post(self.program, with_context=False)
        with CaptureQueriesContext(connection) as with_context:
            self._post(self.mushaf, {"page": 5})

        # Assert
        self.assertEqual(len(without_context), len(with_context))

    # --- Formatting / email ---

    def test_format_issue_context_where_unknown_shape_should_not_fail(self):
        # Arrange / Act / Assert: older or unexpected rows still render.
        self.assertEqual("", format_issue_context(None))
        self.assertEqual("", format_issue_context({"surah": 999}))
        with translation.override("ar"):
            self.assertEqual("صفحة 7 · الحرف «ب»", format_issue_context({"page": 7, "glyph": "ب"}))

    def test_notify_status_changed_where_context_set_should_include_label_in_email(self):
        # Arrange
        report = baker.make(
            ContentIssueReport,
            reporter=self.staff_user,
            asset=self.recitation,
            description="A report on an ayah.",
            context={"surah": 2, "ayah": 255},
        )
        self.staff_user.preferred_language = "ar"
        self.staff_user.save(update_fields=["preferred_language"])

        # Act: sent while English is active, to a recipient who reads Arabic.
        with translation.override("en"):
            IssueReportNotificationService().notify_status_changed(report.id, "pending", "resolved")

        # Assert
        self.assertEqual(1, len(mail.outbox))
        self.assertIn("البقرة 2:255", mail.outbox[0].alternatives[0][0])

    def test_notify_status_changed_where_no_context_should_omit_location(self):
        # Arrange
        report = baker.make(
            ContentIssueReport,
            reporter=self.staff_user,
            asset=self.recitation,
            description="A report with no location.",
            context=None,
        )
        self.staff_user.preferred_language = "en"
        self.staff_user.save(update_fields=["preferred_language"])

        # Act
        IssueReportNotificationService().notify_status_changed(report.id, "pending", "resolved")

        # Assert
        self.assertEqual(1, len(mail.outbox))
        self.assertNotIn("Location:", mail.outbox[0].alternatives[0][0])
