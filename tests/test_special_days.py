import calendar
import datetime

from django.test import TestCase

from mog.utils import get_special_day


class SpecialDaysTestCase(TestCase):
    def test_valentine_day(self):
        data = {
            (2013, "2013-02-14"),
            (2014, "2014-02-14"),
            (2015, "2015-02-14"),
            (2016, "2016-02-14"),
            (2017, "2017-02-14"),
            (2018, "2018-02-14"),
            (2019, "2019-02-14"),
            (2020, "2020-02-14"),
            (2021, "2021-02-14"),
            (2022, "2022-02-14"),
            (2023, "2023-02-14"),
        }
        for year, valentine in data:
            valentine = datetime.datetime.strptime(valentine, "%Y-%m-%d")
            for month in range(1, 13):
                _, days = calendar.monthrange(year, month)
                for day in range(1, days + 1):
                    date = datetime.datetime(year=year, month=month, day=day)
                    if get_special_day(date) == "valentine":
                        msg = (
                            'get_special_day detects date "%s" as Valentine Day but it is not!'
                            % date.strftime("%Y-%m-%d")
                        )
                        self.assertEqual(date, valentine, msg)
                    else:
                        msg = (
                            "get_special_day fails to detect date %s as Valentine Day"
                            % date.strftime("%Y-%m-%d")
                        )
                        self.assertNotEqual(date, valentine, msg)

    def test_halloween(self):
        data = {
            (2013, "2013-10-31"),
            (2014, "2014-10-31"),
            (2015, "2015-10-31"),
            (2016, "2016-10-31"),
            (2017, "2017-10-31"),
            (2018, "2018-10-31"),
            (2019, "2019-10-31"),
            (2020, "2020-10-31"),
            (2021, "2021-10-31"),
            (2022, "2022-10-31"),
            (2023, "2023-10-31"),
        }
        for year, halloween in data:
            halloween = datetime.datetime.strptime(halloween, "%Y-%m-%d")
            for month in range(1, 13):
                _, days = calendar.monthrange(year, month)
                for day in range(1, days + 1):
                    date = datetime.datetime(year=year, month=month, day=day)
                    if get_special_day(date) == "halloween":
                        msg = (
                            'get_special_day detects date "%s" as Halloween but it is not!'
                            % date.strftime("%Y-%m-%d")
                        )
                        self.assertEqual(date, halloween, msg)
                    else:
                        msg = (
                            "get_special_day fails to detect date %s as Halloween"
                            % date.strftime("%Y-%m-%d")
                        )
                        self.assertNotEqual(date, halloween, msg)

    def test_thanksgiving(self):
        data = {
            (2013, "2013-11-28"),
            (2014, "2014-11-27"),
            (2015, "2015-11-26"),
            (2016, "2016-11-24"),
            (2017, "2017-11-23"),
            (2018, "2018-11-22"),
            (2019, "2019-11-28"),
            (2020, "2020-11-26"),
            (2021, "2021-11-25"),
            (2022, "2022-11-24"),
            (2023, "2023-11-23"),
        }
        for year, thanksgiving in data:
            thanksgiving = datetime.datetime.strptime(thanksgiving, "%Y-%m-%d")
            for month in range(1, 13):
                _, days = calendar.monthrange(year, month)
                for day in range(1, days + 1):
                    date = datetime.datetime(year=year, month=month, day=day)
                    if get_special_day(date) == "thanksgiving":
                        msg = (
                            'get_special_day detects date "%s" as Thanksgiving but it is not!'
                            % date.strftime("%Y-%m-%d")
                        )
                        self.assertEqual(date, thanksgiving, msg)
                    else:
                        msg = (
                            "get_special_day fails to detect date %s as Thanksgiving"
                            % date.strftime("%Y-%m-%d")
                        )
                        self.assertNotEqual(date, thanksgiving, msg)

    def test_christmas(self):
        """
        Christmas will be celebrated from 19 to 31 of December
        """
        for year in range(2013, 2024):
            for month in range(1, 13):
                _, days = calendar.monthrange(year, month)
                for day in range(1, days + 1):
                    date = datetime.datetime(year=year, month=month, day=day)
                    if get_special_day(date) == "christmas":
                        msg = (
                            'get_special_day detects date "%s" as Christmas but it is not!'
                            % date.strftime("%Y-%m-%d")
                        )
                        self.assertTrue(month == 12 and 19 <= day <= 31, msg)
                    else:
                        msg = (
                            'get_special_day fails to detect date "%s" as Christmas!'
                            % date.strftime("%Y-%m-%d")
                        )
                        self.assertFalse(month == 12 and 19 <= day <= 31, msg)
