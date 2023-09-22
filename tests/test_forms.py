from django.test import TestCase

from mog.forms import ContestForm


class ContestFormTestCase(TestCase):
    def test_start_and_end_dates(self):
        data = [
            ("2018-01-01 00:00:00", "2018-01-01 00:00:00", False),  # same datetime
            (
                "2018-01-01 12:00:00",
                "2018-01-01 10:00:00",
                False,
            ),  # ends two hours before starts
            (
                "2018-01-01 12:00:00",
                "2018-01-01 11:59:59",
                False,
            ),  # ends one second before starts
            ("2018-01-01 00:00:00", "2018-01-02 00:00:00", True),  # one day after
            (
                "2017-12-31 00:00:00",
                "2018-01-01 00:00:00",
                True,
            ),  # one day after (end year)
            ("2018-01-01 00:00:00", "2018-01-01 00:00:01", True),  # one second after
            ("2017-12-01 00:00:00", "2018-02-01 00:00:00", True),  # different years
            ("2017-01-01 00:00:00", "2018-02-01 00:00:00", True),  # different years
        ]
        for start_date, end_date, valid in data:
            contest_form = ContestForm(
                {
                    "name": "Test Contest",
                    "code": "test-contest",
                    "start_date": start_date,
                    "end_date": end_date,
                    "frozen_time": 0,
                    "death_time": 0,
                }
            )
            msg = "Expected %s form, got %s instead for start_date=%s & end_date=%s" % (
                ["invalid", "valid"][valid],
                ["invalid", "valid"][not valid],
                start_date,
                end_date,
            )
            self.assertEqual(contest_form.is_valid(), valid, msg)

    def test_frozen_and_death_time(self):
        """
        ft: Frozen time
        dt: Death time
        """
        data = [
            (60, 15, True),  # last hour of ft, last 15 minutes of dt
            (5 * 60, 0, True),  # full frozen contest
            (15, 15, True),  # last 15 minutes of death time
            (15, 60, False),  # ft must to be grater or equal than dt
            (301, 301, False),  # dt must to be less or equal than contest duration
        ]
        for frozen_time, death_time, valid in data:
            contest_form = ContestForm(
                {
                    "name": "Test Contest",
                    "code": "test-contest",
                    "start_date": "2018-01-01 00:00:00",
                    "end_date": "2018-01-01 05:00:00",
                    "frozen_time": frozen_time,
                    "death_time": death_time,
                }
            )
            msg = (
                "Expected %s form, got %s instead for froze_time=%s & death_time=%s"
                % (
                    ["invalid", "valid"][valid],
                    ["invalid", "valid"][not valid],
                    frozen_time,
                    death_time,
                )
            )
            self.assertEqual(contest_form.is_valid(), valid, msg)
