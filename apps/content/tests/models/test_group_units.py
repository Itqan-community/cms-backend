from django.db import IntegrityError, transaction
from django.utils import translation
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionChange,
    AssetVersionEntry,
    CategoryChoice,
    ChangeTypeChoice,
    VersionStateChoice,
)
from apps.content.tests.group_quran_data import GroupQuranDataMixin
from apps.content.unit_keys import decode_group_key, encode_group_key, unit_key_expression, unit_q
from apps.core.tests.base import BaseTestCase


class GroupUnitModelTests(GroupQuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_group_quran()
        self.asset = baker.make(Asset, category=CategoryChoice.TAFSIR, template=AssetTemplateChoice.AYAH_GROUP)
        self.version = baker.make(AssetVersion, asset=self.asset, state=VersionStateChoice.DRAFT)
        self.column = self.asset.ensure_text_columns()[0]

    def _entry(self, **units) -> AssetVersionEntry:
        return AssetVersionEntry.objects.create(version=self.version, column=self.column, text="t", **units)

    def test_encode_group_key_where_round_tripped_should_return_from_and_to(self):
        # Arrange
        key = encode_group_key(4, 77431)

        # Act
        decoded = decode_group_key(key)

        # Assert
        self.assertEqual(decoded, (4, 77431))
        self.assertLess(encode_group_key(1, 5), encode_group_key(2, 2))
        self.assertLess(encode_group_key(1, 2), encode_group_key(1, 5))

    def test_unit_id_where_unsaved_entry_has_no_unit_should_return_none(self):
        # Arrange
        entry = AssetVersionEntry(version=self.version, column=self.column, text="t")

        # Act
        unit_id = entry.unit_id

        # Assert
        self.assertIsNone(unit_id)

    def test_unit_id_where_unsaved_change_has_half_a_range_should_return_none(self):
        # Arrange
        change = AssetVersionChange(
            version=self.version, column=self.column, change_type=ChangeTypeChoice.ADDED, from_word_id=6
        )

        # Act
        unit_id = change.unit_id

        # Assert
        self.assertIsNone(unit_id)

    def test_unit_id_where_ayah_range_entry_should_return_encoded_key(self):
        # Arrange
        entry = self._entry(from_ayah_id=1, to_ayah_id=3)

        # Act
        unit_id = entry.unit_id

        # Assert
        self.assertEqual(unit_id, 1_000_003)

    def test_unit_id_where_word_range_change_should_return_encoded_key(self):
        # Arrange
        change = AssetVersionChange.objects.create(
            version=self.version,
            column=self.column,
            change_type=ChangeTypeChoice.ADDED,
            from_word_id=6,
            to_word_id=7,
        )

        # Act
        unit_id = change.unit_id

        # Assert
        self.assertEqual(unit_id, 6_000_007)

    def test_save_where_two_ranges_start_at_same_ayah_should_store_both(self):
        # Arrange
        self._entry(from_ayah_id=1, to_ayah_id=3)

        # Act
        self._entry(from_ayah_id=1, to_ayah_id=1)

        # Assert
        self.assertEqual(AssetVersionEntry.objects.filter(version=self.version).count(), 2)

    def test_save_where_same_range_twice_in_one_column_should_raise_integrity_error(self):
        # Arrange
        self._entry(from_ayah_id=1, to_ayah_id=3)

        # Act / Assert
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._entry(from_ayah_id=1, to_ayah_id=3)

    def test_save_where_range_end_before_start_should_raise_integrity_error(self):
        # Arrange — nothing stored

        # Act / Assert
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._entry(from_ayah_id=3, to_ayah_id=1)

    def test_save_where_ayah_range_and_ayah_both_set_should_raise_integrity_error(self):
        # Arrange — nothing stored

        # Act / Assert
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._entry(ayah_id=1, from_ayah_id=1, to_ayah_id=2)

    def test_save_where_only_from_ayah_set_should_raise_integrity_error(self):
        # Arrange — nothing stored

        # Act / Assert
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._entry(from_ayah_id=1)

    def test_unit_key_expression_where_annotated_should_match_unit_id(self):
        # Arrange
        entries = [
            self._entry(ayah_id=2),
            self._entry(from_ayah_id=4, to_ayah_id=5),
            self._entry(from_word_id=3, to_word_id=4),
        ]

        # Act
        keys = dict(
            AssetVersionEntry.objects.filter(version=self.version)
            .annotate(unit_key=unit_key_expression())
            .values_list("pk", "unit_key")
        )

        # Assert
        self.assertEqual(keys, {entry.pk: entry.unit_id for entry in entries})

    def test_unit_q_where_mixed_ids_should_match_only_those_rows(self):
        # Arrange
        single = self._entry(ayah_id=2)
        wanted = self._entry(from_ayah_id=4, to_ayah_id=5)
        self._entry(ayah_id=3)
        self._entry(from_ayah_id=4, to_ayah_id=4)

        # Act
        matched = set(
            AssetVersionEntry.objects.filter(unit_q([2, encode_group_key(4, 5)])).values_list("pk", flat=True)
        )

        # Assert
        self.assertEqual(matched, {single.pk, wanted.pk})

    def test_asset_template_choice_where_group_values_should_have_labels(self):
        # Arrange / Act — English: an earlier test may leave another language active
        with translation.override("en"):
            labels = (str(AssetTemplateChoice("ayah_group").label), str(AssetTemplateChoice("word_group").label))

        # Assert
        self.assertEqual(labels, ("Ayah-group based", "Word-group based"))
