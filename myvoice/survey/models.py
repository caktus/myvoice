import datetime

from django.db import models

from myvoice.statistics.models import Statistic


class SurveyQuerySet(models.query.QuerySet):

    def active(self):
        return self.filter(active=True)


class SurveyManager(models.Manager):
    query_set_class = SurveyQuerySet

    def get_query_set(self):
        return self.query_set_class(self.model, using=self._db)

    def active(self):
        return self.get_query_set().active()


class Survey(models.Model):
    """Contains TextIt flow metadata."""

    PATIENT_FEEDBACK = 'patient-feedback'
    PATIENT_REGISTRATION = 'patient-registration'
    SURVEY_ROLES = (
        (PATIENT_FEEDBACK, 'Patient Feedback'),
        (PATIENT_REGISTRATION, 'Patient Registration'),
    )

    flow_id = models.IntegerField(
        max_length=32, unique=True, verbose_name='Flow ID',
        help_text="Must match the TextIt flow identifier.")
    name = models.CharField(
        max_length=255, blank=True,
        help_text="Name as it is known on TextIt.")
    active = models.BooleanField(
        default=True,
        help_text="We will only try to import responses for active surveys.")

    role = models.CharField(
        unique=True, max_length=32, null=True, blank=True,
        choices=SURVEY_ROLES, help_text="If given, must be unique.")

    objects = SurveyManager()

    class Meta:
        verbose_name = 'TextIt Survey'

    def __unicode__(self):
        return self.name


class SurveyQuestion(models.Model):
    """A node in a TextIt flow."""

    OPEN_ENDED = 'open-ended'
    MULTIPLE_CHOICE = 'multiple-choice'
    QUESTION_TYPES = (
        (OPEN_ENDED, 'Open Ended'),
        (MULTIPLE_CHOICE, 'Multiple Choice'),
    )

    POSITIVE = 'positive'
    NEGATIVE = 'negative'
    UNKNOWN = 'unknown'
    DESIGNATIONS = (
        (UNKNOWN, 'Neutral/Unknown'),
        (POSITIVE, 'Positive'),
        (NEGATIVE, 'Negative'),
    )

    survey = models.ForeignKey('Survey')
    question_id = models.CharField(
        max_length=128,
        help_text="UUID for this question, generated by TextIt.")

    # The question_type field does not necessarily match TextIt's designation -
    # for example, we consider some multiple choice questions to be free
    # response. See import code for more details.
    question_type = models.CharField(
        max_length=32, choices=QUESTION_TYPES,
        help_text="Only multiple-choice and open-ended types are supported "
        "for now.")
    label = models.CharField(
        max_length=255, help_text='Must match TextIt question label.')
    categories = models.TextField(
        blank=True,
        help_text="For multiple-choice questions. List each category on a "
        "separate line. This field is disregarded for other question types.")

    # Optional information that helps us display survey results better.
    question = models.CharField(max_length=255, blank=True)
    designation = models.CharField(
        max_length=8, choices=DESIGNATIONS, default=UNKNOWN,
        help_text="For open-ended questions. Whether it asks for positive, "
        "negative, or neutral feedback. This field is disregarded for other "
        "question types.")
    order = models.IntegerField(
        default=0,
        help_text="Manually defined. If not present, questions will be "
        "displayed in the order they were created.")
    statistic = models.ForeignKey(
        'statistics.Statistic', null=True, blank=True,
        help_text="The name of the statistic that responses for this "
        "question should be aggregated for.")
    for_display = models.BooleanField(
        default=True,
        help_text="Whether to display the responses to this question.")

    class Meta:
        verbose_name = 'TextIt Survey Question'
        unique_together = [('survey', 'label')]
        ordering = ['order', 'id']

    def __unicode__(self):
        return self.label

    def get_categories(self):
        return self.categories.splitlines()

    @property
    def primary_answer(self):
        """
        We maintain the convention that the first answer listed is the
        primary answer.
        """
        categories = self.get_categories()
        return categories[0] if categories else None

    def save(self, *args, **kwargs):
        """Attempt to auto-set statistic when question is first saved."""
        if not self.pk and not self.statistic:
            try:
                self.statistic = Statistic.objects.get(slug=self.label)
            except Statistic.DoesNotExist:
                self.statistic = None
        return super(SurveyQuestion, self).save(*args, **kwargs)


class SurveyQuestionResponse(models.Model):
    """An answer to a survey question."""

    phone = models.CharField(max_length=32)
    question = models.ForeignKey('survey.SurveyQuestion')
    response = models.CharField(max_length=255)
    datetime = models.DateTimeField(
        default=datetime.datetime.now,
        help_text="When this response was received.")

    # Add these data points to give some context to the response.
    # Since each survey is used for patients receiving any service from
    # any health clinic, these are fields on the responses rather than, say,
    # the Questions themselves.
    # This data will be collected during the patient registration process.
    clinic = models.ForeignKey(
        'clinics.Clinic', null=True, blank=True,
        help_text="The clinic this response is about, if any.")
    service = models.ForeignKey(
        'clinics.Service', null=True, blank=True,
        help_text="The service this response is about, if any.")

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Response'
        unique_together = [('phone', 'question')]

    def __unicode__(self):
        return self.response
