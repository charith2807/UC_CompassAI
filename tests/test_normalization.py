"""Prevent tuition units from shifting when empty HTML table cells collapse."""
import unittest
from crawler.normalize import align_table_columns

class TableAlignmentTests(unittest.TestCase):
    def test_empty_cell_is_restored_from_matching_header_and_row(self):
        text="## Executive Programs | ## Rate Per Bi-Term | ## Per Credit Hour |\n| Master's Programs | $549 | |\n| Doctoral Programs | $749 | |"
        saved="| Executive Programs | Rate Per Bi-Term | Per Credit Hour |\n| Master's Programs | | $549 |\n| Doctoral Programs | | $749 |"
        aligned=align_table_columns(text,[saved])
        self.assertIn('| Doctoral Programs |  | $749 |',aligned)
        self.assertIn("| Master's Programs |  | $549 |",aligned)
        self.assertEqual(align_table_columns(aligned,[saved]),aligned)
    def test_unrelated_header_cannot_supply_same_named_row(self):
        text='## Nursing | Per Credit Hour |\n| Online | $539 | |'
        table="| Graduate - Master's | Rate Per Bi-Term | Per Credit Hour |\n| Online | | $355 |"
        self.assertEqual(align_table_columns(text,[table]),text)
    def test_conflicting_saved_tables_are_not_guessed(self):
        text='## Executive Programs | Per Credit Hour |\n| Doctoral Programs | $749 | |'
        first='| Executive Programs | Rate Per Bi-Term | Per Credit Hour |\n| Doctoral Programs | | $749 |'
        second=first.replace('$749','$999')
        self.assertEqual(align_table_columns(text,[first,second]),text)

if __name__=='__main__':unittest.main()
