import mock

from django.test import TestCase
from django.utils import timezone

from myvoice.clinics.models import Visit
from myvoice.core.tests import factories

from .. import tasks
from .. import models
from ..textit import TextItException


@mock.patch('myvoice.survey.tasks.importer.import_responses')
class TestImportResponses(TestCase):

    def test_active_survey(self, import_responses):
        """We should call the import_responses utility for active surveys."""
        self.survey = factories.Survey(active=True)
        tasks.import_responses()
        self.assertEqual(import_responses.call_count, 1)
        self.assertEqual(import_responses.call_args, ((self.survey.flow_id,),))

    def test_inactive_survey(self, import_responses):
        """We should not try to import responses for inactive surveys."""
        self.survey = factories.Survey(active=False)
        tasks.import_responses()
        self.assertEqual(import_responses.call_count, 0)


@mock.patch.object(tasks.TextItApi, 'start_flow')
class TestStartFeedbackSurvey(TestCase):

    def setUp(self):
        super(TestStartFeedbackSurvey, self).setUp()
        self.survey = factories.Survey(role=models.Survey.PATIENT_FEEDBACK)
        self.visit = factories.Visit(mobile='01234567890')

    def test_no_such_survey(self, start_flow):
        """No flow should be started if there is no patient feedback survey."""
        self.survey.delete()
        self.assertRaises(models.Survey.DoesNotExist,
                          tasks.start_feedback_survey,
                          self.visit.pk)
        self.assertEqual(start_flow.call_count, 0)
        self.visit = Visit.objects.get(pk=self.visit.pk)
        self.assertIsNone(self.visit.survey_sent)

    def test_no_such_visit(self, start_flow):
        """No flow should be started if there is no associated visit."""
        self.assertRaises(Visit.DoesNotExist,
                          tasks.start_feedback_survey,
                          12345)
        self.assertEqual(start_flow.call_count, 0)
        self.visit = Visit.objects.get(pk=self.visit.pk)
        self.assertIsNone(self.visit.survey_sent)

    def test_start_flow(self, start_flow):
        """When survey is sent, survey_sent field should be updated."""
        tasks.start_feedback_survey(self.visit.pk)
        self.assertEqual(start_flow.call_count, 1)
        expected = ((self.survey.flow_id, self.visit.mobile),)
        self.assertEqual(start_flow.call_args, expected)
        self.visit = Visit.objects.get(pk=self.visit.pk)
        self.assertIsNotNone(self.visit.survey_sent)

    def test_error(self, start_flow):
        """If error occurs during start_flow, survey_sent should be null."""
        start_flow.side_effect = TextItException
        self.assertRaises(start_flow.side_effect,
                          tasks.start_feedback_survey,
                          self.visit.pk)
        self.assertEqual(start_flow.call_count, 1)
        expected = ((self.survey.flow_id, self.visit.mobile),)
        self.assertEqual(start_flow.call_args, expected)
        self.visit = Visit.objects.get(pk=self.visit.pk)
        self.assertIsNone(self.visit.survey_sent)


@mock.patch.object(tasks.TextItApi, 'send_message')
@mock.patch('myvoice.survey.tasks.start_feedback_survey.apply_async')
class TestHandleNewVisits(TestCase):

    def setUp(self):
        super(TestHandleNewVisits, self).setUp()
        self.survey = factories.Survey(role=models.Survey.PATIENT_FEEDBACK)

    def test_new_visit(self, start_feedback_survey, send_message):
        """
        We should send a welcome message and schedule the survey to be started
        for a new visit.
        """
        visit = factories.Visit(welcome_sent=None, mobile='01234567890')
        tasks.handle_new_visits()
        self.assertEqual(send_message.call_count, 0)
        visit = Visit.objects.get(pk=visit.pk)
        self.assertIsNotNone(visit.welcome_sent)
        self.assertEqual(start_feedback_survey.call_count, 1)

    def test_only_invalid(self, start_feedback_survey, send_message):
        """Nothing should happen if all phone numbers are invalid."""
        visit = factories.Visit(welcome_sent=None, mobile='invalid')
        tasks.handle_new_visits()
        self.assertEqual(send_message.call_count, 0)
        visit = Visit.objects.get(pk=visit.pk)
        self.assertIsNone(visit.welcome_sent)
        self.assertEqual(start_feedback_survey.call_count, 0)

    def test_mixed_valid_invalid_phones(self, start_feedback_survey, send_message):
        """
        We should send a welcome message and schedule the survey to be started
        for a new visit.
        """
        visit1 = factories.Visit(welcome_sent=None, mobile='invalid')
        visit2 = factories.Visit(welcome_sent=None, mobile='01234567890')
        tasks.handle_new_visits()

        # No welcome message sent so send_message.call_count = 0
        self.assertEqual(send_message.call_count, 0)
        visit1 = Visit.objects.get(pk=visit1.pk)
        self.assertIsNone(visit1.welcome_sent)
        visit2 = Visit.objects.get(pk=visit2.pk)
        self.assertIsNotNone(visit2.welcome_sent)
        self.assertEqual(start_feedback_survey.call_count, 1)

    def test_past_visit(self, start_feedback_survey, send_message):
        """
        We should not do anything for visits that have already had the
        welcome message sent.
        """
        welcome_sent = timezone.now()
        visit = factories.Visit(welcome_sent=welcome_sent, mobile='01234567890')
        tasks.handle_new_visits()

        # No welcome message sent so send_message.call_count = 0
        self.assertEqual(send_message.call_count, 0)
        self.assertEqual(start_feedback_survey.call_count, 0)
        visit = Visit.objects.get(pk=visit.pk)
        self.assertEqual(visit.welcome_sent, welcome_sent)
        self.assertIsNone(visit.survey_sent)

    def test_blocked_number(self, start_feedback_survey, send_message):
        """
        We don't start surveys for blocked numbers which are those that are senders
        in one or more Visits.
        """
        factories.Visit(welcome_sent=None, mobile='01234567890', sender='09876543210')
        visit2 = factories.Visit(welcome_sent=None, mobile='09876543210')
        tasks.handle_new_visits()

        # No welcome message sent so send_message.call_count = 0
        self.assertEqual(send_message.call_count, 0)
        visit2 = Visit.objects.get(pk=visit2.pk)
        self.assertIsNone(visit2.welcome_sent)
        self.assertEqual(start_feedback_survey.call_count, 1)


@mock.patch('myvoice.survey.tasks.settings')
class TestGetSurveyStartTime(TestCase):

    def setUp(self):
        self.t1 = timezone.make_aware(
            timezone.datetime(2014, 07, 21, 10, 0, 0, 0), timezone.utc)

    def test_get_start_time(self, settings):
        settings.DEFAULT_SURVEY_DELAY = timezone.timedelta(minutes=5)
        settings.SURVEY_TIME_WINDOW = (7, 20)
        eta = tasks._get_survey_start_time(self.t1)
        self.assertEqual(eta, self.t1.replace(minute=5))

    def test_get_eta_early(self, settings):
        settings.DEFAULT_SURVEY_DELAY = timezone.timedelta(minutes=5)
        settings.SURVEY_TIME_WINDOW = (7, 20)
        tm = self.t1.replace(hour=4)
        eta = tasks._get_survey_start_time(tm)
        self.assertEqual(eta, self.t1.replace(hour=7))

    def test_get_eta_late(self, settings):
        settings.DEFAULT_SURVEY_DELAY = timezone.timedelta(minutes=5)
        settings.SURVEY_TIME_WINDOW = (7, 20)
        tm = self.t1.replace(hour=23)
        eta = tasks._get_survey_start_time(tm)
        self.assertEqual(eta, self.t1.replace(hour=7, day=22))
