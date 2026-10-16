"""Tests for AuditedModelAdmin in Django Admin (ITQ-35 / Issue #433)."""

from django.urls import reverse

from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class AuditedModelAdminTest(BaseTestCase):
    def test_history_view_where_object_exists_should_render_200_and_list_versions(self):
        """Verifies that the admin history page renders successfully and displays historical entries."""
        # Arrange: create staff user and publisher with history
        staff_user = User.objects.create(
            email="admin@itqan.dev",
            name="Admin User",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(staff_user)

        publisher = Publisher.objects.create(name="Publisher One", slug="pub-one")
        publisher.name = "Publisher One Updated"
        publisher.save()

        history_url = reverse("admin:publishers_publisher_history", args=[publisher.pk])

        # Act: access object history in Django Admin
        response = self.client.get(history_url)

        # Assert: returns 200 and renders history template
        assert response.status_code == 200
        assert "history_list_display" in response.context
        assert len(response.context["page_obj"]) == 2

    def test_history_view_where_object_deleted_should_render_200(self):
        """Verifies that the admin history page for a deleted object renders successfully."""
        # Arrange: create staff user and delete publisher
        staff_user = User.objects.create(
            email="admin2@itqan.dev",
            name="Admin User 2",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(staff_user)

        publisher = Publisher.objects.create(name="To Delete", slug="to-del")
        pub_id = publisher.pk
        publisher.delete()
        assert not Publisher.objects.filter(pk=pub_id).exists()

        history_url = reverse("admin:publishers_publisher_history", args=[pub_id])

        # Act: access history of deleted object in Django Admin
        response = self.client.get(history_url)

        # Assert: returns 200 and renders historical records
        assert response.status_code == 200
        assert len(response.context["page_obj"]) >= 1

    def test_history_form_view_where_revert_edited_object_should_restore_prior_values(self):
        """Verifies that submitting the revert form in admin restores previous values for an edited object."""
        # Arrange: create publisher (v1), update to v2
        staff_user = User.objects.create(
            email="admin3@itqan.dev",
            name="Admin User 3",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(staff_user)

        publisher = Publisher.objects.create(
            name_en="Original English",
            name_ar="الأصل العربي",
            slug="orig-pub",
        )
        v1_record = publisher.history.first()

        publisher.name_en = "Changed English"
        publisher.save()

        revert_url = reverse(
            "admin:publishers_publisher_simple_history",
            args=[publisher.pk, v1_record.history_id],
        )

        # Act: POST to revert form view with v1 data
        post_data = {
            "name_en": "Original English",
            "name_ar": "الأصل العربي",
            "slug": "orig-pub",
        }
        response = self.client.post(revert_url, post_data)

        # Assert: redirects to change view and field restored in DB
        assert response.status_code == 302
        publisher.refresh_from_db()
        assert publisher.name_en == "Original English"

    def test_history_form_view_where_revert_deleted_object_should_resurrect_row_in_database(self):
        """Verifies that submitting the revert form in admin resurrects a deleted object with its original PK."""
        # Arrange: create publisher, then delete it
        staff_user = User.objects.create(
            email="admin4@itqan.dev",
            name="Admin User 4",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(staff_user)

        publisher = Publisher.objects.create(
            name_en="Resurrect Me",
            name_ar="أعدني للحياة",
            slug="resurrect-pub",
        )
        pub_id = publisher.pk
        v1_record = publisher.history.first()

        publisher.delete()
        assert not Publisher.objects.filter(pk=pub_id).exists()

        revert_url = reverse(
            "admin:publishers_publisher_simple_history",
            args=[pub_id, v1_record.history_id],
        )

        # Act: POST to revert form view to resurrect deleted object
        post_data = {
            "name_en": "Resurrect Me",
            "name_ar": "أعدني للحياة",
            "slug": "resurrect-pub",
        }
        response = self.client.post(revert_url, post_data)

        # Assert: redirects and row is resurrected in database with same PK
        assert response.status_code == 302
        assert Publisher.objects.filter(pk=pub_id).exists()
        recreated = Publisher.objects.get(pk=pub_id)
        assert recreated.name_en == "Resurrect Me"
        # Assert new historical record written with '+'
        latest_history = Publisher.history.order_by("-history_date").first()
        assert latest_history.history_type == "+"
        assert latest_history.history_user_id == staff_user.pk
