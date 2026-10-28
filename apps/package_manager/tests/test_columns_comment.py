from apps.content.services.asset_columns import ColumnInfo, VersionStructure
from apps.core.tests.base import BaseTestCase
from apps.package_manager.services.columns_comment import render_columns_comment

QA = VersionStructure(
    template="ayah",
    header=["surah", "ayah", "question", "answer"],
    columns=[ColumnInfo("question", "Question", "السؤال"), ColumnInfo("answer", "Answer", "الجواب")],
)


class RenderColumnsCommentTests(BaseTestCase):
    def test_render_columns_comment_where_two_columns_should_match_the_spec_example(self):
        # Arrange / Act
        lines = render_columns_comment(QA, "  ")

        # Assert
        self.assertEqual(
            lines,
            [
                "  # itqan:columns CSV, one row per ayah: surah, ayah, question, answer",
                "  # itqan:columns   question: Question / السؤال",
                "  # itqan:columns   answer: Answer / الجواب",
            ],
        )

    def test_render_columns_comment_where_single_column_should_render_nothing(self):
        # Arrange
        single = VersionStructure(
            template="ayah", header=["surah", "ayah", "text"], columns=[ColumnInfo("text", "", "")]
        )

        # Act / Assert
        self.assertEqual(render_columns_comment(single, "  "), [])

    def test_render_columns_comment_where_column_has_no_or_one_label_should_skip_or_show_it(self):
        # Arrange
        structure = VersionStructure(
            template="word",
            header=["word_id", "surah", "ayah", "word", "gloss", "note"],
            columns=[ColumnInfo("gloss", "", "المعنى"), ColumnInfo("note", "", "")],
        )

        # Act
        lines = render_columns_comment(structure, "    ")

        # Assert
        self.assertEqual(
            lines,
            [
                "    # itqan:columns CSV, one row per word: word_id, surah, ayah, word, gloss, note",
                "    # itqan:columns   gloss: المعنى",
            ],
        )

    def test_render_columns_comment_where_label_has_newlines_should_collapse_it_to_one_line(self):
        # Arrange
        structure = VersionStructure(
            template="ayah",
            header=["surah", "ayah", "question", "answer"],
            columns=[
                ColumnInfo("question", 'Q\n  evil:\n    version: "1.0.0"', ""),
                ColumnInfo("answer", "A\r\nB", ""),
            ],
        )

        # Act
        lines = render_columns_comment(structure, "  ")

        # Assert
        self.assertEqual(
            lines[1:],
            ['  # itqan:columns   question: Q evil: version: "1.0.0"', "  # itqan:columns   answer: A B"],
        )
