"""A grader that is asked to stop finishes its current submission and takes no
new ones; see StopRequest in api/management/commands/grader.py."""

import os
import signal

from django.test import SimpleTestCase

from api.management.commands.grader import StopRequest


class StopRequestTestCase(SimpleTestCase):
    def setUp(self):
        saved = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
        self.addCleanup(lambda: [signal.signal(s, h) for s, h in saved.items()])

    def test_stop_signals_request_a_stop(self):
        for sig in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signal=sig.name):
                stop = StopRequest()
                os.kill(os.getpid(), sig)
                self.assertTrue(stop.requested)

    def test_no_claim_starts_after_a_stop(self):
        # The grader claims submissions inside held(): a signal sent meanwhile
        # is handled only when the claim is done, never in the middle of it
        stop = StopRequest()
        with stop.held():
            os.kill(os.getpid(), signal.SIGTERM)
            self.assertFalse(stop.requested)
        self.assertTrue(stop.requested)
