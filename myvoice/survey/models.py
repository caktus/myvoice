import datetime

from django.db import models


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
    SURVEY_ROLES = (
        (PATIENT_FEEDBACK, 'Patient Feedback'),
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
    question = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = 'TextIt Survey Question'
        unique_together = [('survey', 'label')]

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


class SurveyQuestionResponse(models.Model):
    """An answer to a survey question."""

    question = models.ForeignKey('survey.SurveyQuestion')
    response = models.CharField(
        max_length=255,
        help_text="Normalized response to the question.")
    datetime = models.DateTimeField(
        default=datetime.datetime.now,
        help_text="When this response was received.")
    visit = models.ForeignKey(
        'clinics.Visit', null=True, blank=True,
        help_text="The visit this response is associated with, if any.")

    # FIXME - These fields are set in the save method based on the value of
    # the visit's service and the visit's patient's clinic. It should be
    # possible to use the visit's values directly.
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
        unique_together = [('visit', 'question')]

    def __unicode__(self):
        return self.response

    def save(self, *args, **kwargs):
        """Set the associated clinic and service."""
        self.clinic_id = self.service_id = None
        if self.visit:
            self.service_id = self.visit.service_id
            if self.visit.patient:
                self.clinic_id = self.visit.patient.clinic_id
        super(SurveyQuestionResponse, self).save(*args, **kwargs)
