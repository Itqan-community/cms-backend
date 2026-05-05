import json

from apps.usage_tracking.services.entity_extractor import extract_entity_ids


class TestEntityExtractor:
    def test_extract_non_json_returns_empty(self):
        assert extract_entity_ids(b"not json at all") == []

    def test_extract_empty_bytes_returns_empty(self):
        assert extract_entity_ids(b"") == []

    def test_extract_none_returns_empty(self):
        assert extract_entity_ids(None) == []

    def test_extract_json_list_returns_top_ids(self):
        body = json.dumps([{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]).encode()

        assert extract_entity_ids(body) == [1, 2]

    def test_extract_paginated_dict_with_items_extracts_inner_ids(self):
        body = json.dumps({"items": [{"id": 7}, {"id": 8}], "count": 2}).encode()

        assert extract_entity_ids(body) == [7, 8]

    def test_extract_paginated_dict_with_results_extracts_inner_ids(self):
        body = json.dumps({"results": [{"id": 11}, {"id": 12}]}).encode()

        assert extract_entity_ids(body) == [11, 12]

    def test_extract_single_dict_with_id_returns_single(self):
        body = json.dumps({"id": 99, "name": "single"}).encode()

        assert extract_entity_ids(body) == [99]

    def test_extract_more_than_100_truncates(self):
        body = json.dumps([{"id": i} for i in range(150)]).encode()

        result = extract_entity_ids(body)

        assert len(result) == 100
        assert result == list(range(100))

    def test_extract_no_id_field_returns_empty(self):
        body = json.dumps([{"name": "no id here"}, {"name": "neither"}]).encode()

        assert extract_entity_ids(body) == []

    def test_extract_string_ids_supported(self):
        body = json.dumps([{"id": "abc-123"}, {"id": "def-456"}]).encode()

        assert extract_entity_ids(body) == ["abc-123", "def-456"]

    def test_extract_mixed_items_skips_non_dict_entries(self):
        body = json.dumps([{"id": 1}, "string", 42, {"id": 2}]).encode()

        assert extract_entity_ids(body) == [1, 2]

    def test_extract_entities_returns_names_alongside_ids(self):
        from apps.usage_tracking.services.entity_extractor import extract_entities

        body = json.dumps([{"id": 1, "name_en": "Ibn Kathir"}, {"id": 2, "name": "Al-Sudais"}]).encode()
        ids, names = extract_entities(body)
        assert ids == [1, 2]
        assert names == ["Ibn Kathir", "Al-Sudais"]

    def test_extract_name_falsy_string_zero_is_returned(self):
        from apps.usage_tracking.services.entity_extractor import extract_entities

        body = json.dumps([{"id": 1, "name": "0"}]).encode()
        ids, names = extract_entities(body)
        assert names == ["0"]

    def test_extract_name_missing_returns_empty_string(self):
        from apps.usage_tracking.services.entity_extractor import extract_entities

        body = json.dumps([{"id": 1}]).encode()
        _, names = extract_entities(body)
        assert names == [""]
