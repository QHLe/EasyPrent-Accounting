import datetime
import unittest

from easyprent_accounting.domain import DateRange, DomainError

class DomainTests(unittest.TestCase):
    def test_domain_error_stores_code_and_reason(self):
        error = DomainError("invalid_value", "The value is not valid.")
        self.assertEqual("invalid_value", error.code)
        self.assertEqual("The value is not valid.", error.reason)
        self.assertEqual("invalid_value: The value is not valid.", str(error))
        
    def test_date_range_stores_start_and_end(self):
        start = datetime.date(2025, 1, 1)
        end = datetime.date(2025, 12, 31)
        dr = DateRange(start, end)
        self.assertEqual(start, dr.start)
        self.assertEqual(end, dr.end)
        
    def test_date_range_rejects_end_before_start(self):
        start = datetime.date(2025, 1, 1)
        end = datetime.date(2024, 12, 31)
        with self.assertRaises(DomainError) as cm:
            DateRange(start, end)
        self.assertEqual("invalid_date_range", cm.exception.code)
        
    def test_date_range_equality(self):
        start = datetime.date(2025, 1, 1)
        end = datetime.date(2025, 12, 31)
        dr1 = DateRange(start, end)
        dr2 = DateRange(start, end)
        self.assertEqual(dr1, dr2)
        self.assertEqual(hash(dr1), hash(dr2))
        
    def test_date_range_allows_same_start_and_end(self):
        start = datetime.date(2025, 1, 1)
        dr = DateRange(start, start)
        self.assertEqual(start, dr.start)
        self.assertEqual(start, dr.end)
