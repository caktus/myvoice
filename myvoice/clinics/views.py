from itertools import groupby
import json
from dateutil.parser import parse
from operator import attrgetter, itemgetter

from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, View, FormView, TemplateView
from django.utils import timezone
from django.db.models.aggregates import Max, Min
from django.template.loader import get_template
from django.template import Context

from myvoice.core.utils import get_week_start, get_week_end, make_percentage, daterange
from myvoice.survey import utils as survey_utils
from myvoice.clinics import utils as clinic_utils

from myvoice.survey.models import Survey, SurveyQuestion, SurveyQuestionResponse
from myvoice.clinics.models import Clinic, Service, Visit

from . import forms
from . import models


class VisitView(View):
    form_class = forms.VisitForm
    success_msg = "Entry received for patient with serial number {}. Thank you."
    error_msg = "1 or more of your entry are missing, please check and enter "\
                "the registration agian."
    serial_min = 3
    serial_max = 6

    @csrf_exempt
    def dispatch(self, *args, **kwargs):
        return super(VisitView, self).dispatch(*args, **kwargs)

    def post(self, request):
        form = self.form_class(request.POST)
        if form.is_valid():

            clnc, mobile, serial, serv, txt = form.cleaned_data['text']
            sender = survey_utils.convert_to_local_format(form.cleaned_data['phone'])
            try:
                patient = models.Patient.objects.get(clinic=clnc, serial=serial)
            except models.Patient.DoesNotExist:
                patient = models.Patient.objects.create(
                    clinic=clnc,
                    serial=serial,
                    mobile=mobile)

            output_msg = self.success_msg.format(serial)

            models.Visit.objects.create(patient=patient, service=serv, mobile=mobile, sender=sender)
            data = json.dumps({'text': output_msg})
        else:
            data = json.dumps({'text': self.get_error_msg(form)})

        response = HttpResponse(data, content_type='text/json')

        # This is to test webhooks from localhost
        # response['Access-Control-Allow-Origin'] = '*'
        return response

    def get_error_msg(self, form):
        """Extract the first error message from the form's 'text' field."""
        return form.errors['text'][0]


class ClinicReportSelectClinic(FormView):
    template_name = 'clinics/select.html'
    form_class = forms.SelectClinicForm

    def form_valid(self, form):
        clinic = form.cleaned_data['clinic']
        return redirect('clinic_report', slug=clinic.slug)


class ReportMixin(object):

    def _check_assumptions(self):
        """Fail fast if our hard-coded assumpions are not met."""
        for label in ['Open Facility', 'Respectful Staff Treatment',
                      'Clean Hospital Materials', 'Charged Fairly',
                      'Wait Time']:
            if label not in self.questions:
                raise Exception("Expecting question with label " + label)

    def initialize_data(self, obj):
        """Called by get_object to initialize state information."""
        self.survey = Survey.objects.get(role=Survey.PATIENT_FEEDBACK)
        self.questions = self.survey.surveyquestion_set.all()
        self.questions = dict([(q.label, q) for q in self.questions])
        self._check_assumptions()

    def get_feedback_by_service(self):
        """Return analyzed feedback by service then question."""
        data = []
        responses = self.responses.exclude(service=None)
        by_service = survey_utils.group_responses(responses, 'service.id', 'service')
        for service, service_responses in by_service:
            by_question = survey_utils.group_responses(service_responses, 'question.label')
            responses_by_question = dict(by_question)
            service_data = []
            for label in ['Open Facility', 'Respectful Staff Treatment',
                          'Clean Hospital Materials', 'Charged Fairly']:
                if label in responses_by_question:
                    question = self.questions[label]
                    question_responses = responses_by_question[label]
                    total_responses = len(question_responses)
                    answers = [response.response for response in question_responses]
                    percentage = survey_utils.analyze(answers, question.primary_answer)
                    service_data.append(('{}%'.format(percentage), total_responses))
                else:
                    service_data.append((None, 0))
            if 'Wait Time' in responses_by_question:
                wait_times = [r.response for r in responses_by_question['Wait Time']]
                mode = survey_utils.get_mode(
                    wait_times, self.questions.get('Wait Time').get_categories())
                service_data.append((mode, len(wait_times)))
            else:
                service_data.append((None, 0))
            data.append((service, service_data))
        return data


class ClinicReport(ReportMixin, DetailView):
    template_name = 'clinics/report.html'
    model = models.Clinic

    def _get_patient_satisfaction(self, responses):
        """Patient satisfaction is gauged on their answers to 3 questions."""
        if not responses:
            return None  # Avoid divide-by-zero error.
        treatment = self.questions['Respectful Staff Treatment']
        overcharge = self.questions['Charged Fairly']
        wait_time = self.questions['Wait Time']
        unsatisfied_count = 0
        grouped = survey_utils.group_responses(responses, 'visit.id', 'visit')
        required = ['Respectful Staff Treatment', 'Clean Hospital Materials',
                    'Charged Fairly', 'Wait Time']
        count = 0  # Number of runs that contain at least one required question.
        for visit, visit_responses in grouped:
            # Map question label to the response given for that question.
            answers = dict([(r.question.label, r.response) for r in visit_responses])
            if any([r in answers for r in required]):
                count += 1
            if treatment.label in answers:
                if answers.get(treatment.label) != treatment.primary_answer:
                    unsatisfied_count += 1
                    continue
            if overcharge.label in answers:
                if answers.get(overcharge.label) != overcharge.primary_answer:
                    unsatisfied_count += 1
                    continue
            if wait_time.label in answers:
                if answers.get(wait_time.label) == wait_time.get_categories()[-1]:
                    unsatisfied_count += 1
                    continue
        if not count:
            return None
        return 100 - make_percentage(unsatisfied_count, count)

    def get_object(self, queryset=None):
        obj = super(ClinicReport, self).get_object(queryset)
        self.initialize_data(obj)
        self.responses = obj.surveyquestionresponse_set.filter(display_on_dashboard=True)
        self.responses = self.responses.select_related('question', 'service', 'visit')
        self.generic_feedback = obj.genericfeedback_set.filter(display_on_dashboard=True)
        return obj

    def get_feedback_by_week(self):
        data = []
        responses = self.responses.order_by('datetime')
        by_week = groupby(responses, lambda r: get_week_start(r.datetime))
        for week_start, week_responses in by_week:
            week_responses = list(week_responses)
            by_question = survey_utils.group_responses(week_responses, 'question.label')
            responses_by_question = dict(by_question)
            week_data = []
            survey_num = 0
            for label in ['Open Facility', 'Respectful Staff Treatment',
                          'Clean Hospital Materials', 'Charged Fairly']:
                if label in responses_by_question:
                    question = self.questions[label]
                    question_responses = list(responses_by_question[label])
                    total_responses = len(question_responses)
                    if label is 'Open Facility':
                        survey_num += total_responses
                    answers = [response.response for response in question_responses]
                    percentage = survey_utils.analyze(answers, question.primary_answer)
                    week_data.append((percentage, total_responses))
                else:
                    week_data.append((None, 0))
            wait_times = [r.response for r in responses_by_question.get('Wait Time', [])]
            data.append({
                'week_start': week_start,
                'week_end': get_week_end(week_start),
                'data': week_data,
                'patient_satisfaction': self._get_patient_satisfaction(week_responses),
                'wait_time_mode': survey_utils.get_mode(
                    wait_times, self.questions.get('Wait Time').get_categories()),
                'survey_num': survey_num
            })
        return data

    def get_date_range(self):
        if self.responses:
            min_date = min(self.responses, key=attrgetter('datetime')).datetime
            max_date = max(self.responses, key=attrgetter('datetime')).datetime
            return get_week_start(min_date), get_week_end(max_date)
        return None, None

    def get_detailed_comments(self):
        """Combine open-ended survey comments with General Feedback."""
        open_ended_responses = self.responses.filter(
            question__question_type=SurveyQuestion.OPEN_ENDED)
        comments = [
            {
                'question': r.question.label,
                'datetime': r.datetime,
                'response': r.response,
            }
            for r in open_ended_responses
            if survey_utils.display_feedback(r.response)
        ]

        feedback_label = self.generic_feedback.model._meta.verbose_name
        for feedback in self.generic_feedback:
            if survey_utils.display_feedback(feedback.message):
                comments.append(
                    {
                        'question': feedback_label,
                        'datetime': feedback.message_date,
                        'response': feedback.message
                    })

        return sorted(comments, key=lambda item: (item['question'], item['datetime']))

    def get_context_data(self, **kwargs):
        kwargs['responses'] = self.responses
        kwargs['detailed_comments'] = self.get_detailed_comments()
        kwargs['feedback_by_service'] = self.get_feedback_by_service()
        kwargs['feedback_by_week'] = self.get_feedback_by_week()
        kwargs['min_date'], kwargs['max_date'] = self.get_date_range()
        num_registered = survey_utils.get_registration_count(self.object)
        num_started = survey_utils.get_started_count(self.responses)
        num_completed = survey_utils.get_completion_count(self.responses)

        if num_registered:
            percent_started = make_percentage(num_started, num_registered)
            percent_completed = make_percentage(num_completed, num_registered)
        else:
            percent_completed = None
            percent_started = None

        kwargs['num_registered'] = num_registered
        kwargs['num_started'] = num_started
        kwargs['percent_started'] = percent_started
        kwargs['num_completed'] = num_completed
        kwargs['percent_completed'] = percent_completed

        # TODO - participation rank amongst other clinics.
        return super(ClinicReport, self).get_context_data(**kwargs)


class AnalystSummary(TemplateView):
    template_name = 'analysts/analysts.html'
    allowed_methods = ['get', 'post', 'put', 'delete', 'options']

    def options(self, request, id):
        response = HttpResponse()
        response['allow'] = ','.join([self.allowed_methods])
        return response

    def get_clinic_visit_counts(cls, clinics, **kwargs):
        """Get the count of visits to each of clinics for service
        and between start_date and end_date.

        Return dict of clinic: count_of_visits"""
        visit_counts = {}
        start_date = kwargs.get('start_date', None)
        end_date = kwargs.get('end_date', None)
        service = kwargs.get('service', None)

        # Build filter params
        params = {'survey_sent__isnull': False}
        if service:
            params.update({'service': service})
        if start_date:
            params.update({'visit_time__gte': start_date})
        if end_date:
            params.update({'visit_time__lte': end_date})
        if clinics:
            params.update({'patient__clinic': clinics})

        visits = models.Visit.objects.filter(**params)

        for clinic in clinics:
            visit_counts.update({clinic: visits.filter(patient__clinic=clinic).count()})
        return visit_counts

    def get_completion_table(self, clinic=None, start_date=None, end_date=None, service=None):
        completion_table = []
        st_total = 0            # Surveys Triggered
        ss_total = 0            # Surveys Started
        sc_total = 0            # Surveys Completed

        # All Clinics to Loop Through, build our own dict of data
        clinics_to_add = Clinic.objects.all().order_by("name")

        # Filter for Start Date, End Date and Service
        if start_date:
            if type(start_date) is str:
                start_date = parse(start_date)

        if end_date:
            if type(end_date) is str:
                end_date = parse(end_date)

        if service:
            if type(service) is str:
                service = Service.objects.get(name__iexact=service)

        # Loop through the Clinics, summating the data required.
        for a_clinic in clinics_to_add:

            st_count = clinic_utils.get_triggered_count(a_clinic, service, start_date, end_date)
            st_total += st_count

            # Survey Started Query Statistics
            ss_count = survey_utils.get_started_count("", a_clinic, service, start_date, end_date)
            ss_total += ss_count

            # Survey Completed Query Statistics
            sc_count = survey_utils.get_completion_qcount(
                "", a_clinic, service, start_date, end_date)
            sc_total += sc_count

            # Survey Percentages
            if st_count:
                ss_st_percent = 100*ss_count/st_count
                sc_st_percent = 100*sc_count/st_count
            else:
                ss_st_percent = "--"
                sc_st_percent = "--"

            completion_table.append({
                "clinic_id": a_clinic.id,
                "clinic_name": a_clinic.name,
                "st_count": st_count,
                "ss_count": ss_count,
                "ss_st_percent": ss_st_percent,
                "sc_count": sc_count,
                "sc_st_percent": sc_st_percent
            })

        if st_total:
            ss_st_percent_total = 100*ss_total/st_total
            sc_st_percent_total = 100*sc_total/st_total
        else:
            ss_st_percent_total = "--"
            sc_st_percent_total = "--"

        completion_table.append({
            "clinic_id": -1,
            "clinic_name": "Total",
            "st_count": st_total,
            "ss_count": ss_total,
            "ss_st_percent": ss_st_percent_total,
            "sc_count": sc_total,
            "sc_st_percent": sc_st_percent_total,
        })

        return completion_table

    # Returns a list of Datetime Days between two dates
    def get_date_range(self, start_date, end_date):
        return_dates = []
        if isinstance(start_date, basestring):
            start_date = parse(start_date)
        if isinstance(end_date, basestring):
            end_date = parse(end_date)
        for single_date in daterange(start_date, end_date):
            return_dates.append(single_date)
        return return_dates

    def get_survey_question_responses(self):
        return SurveyQuestionResponse.objects.all()

    def get_surveys_triggered_summary(self):
        """Total number of Surveys Triggered."""
        return Visit.objects.filter(survey_sent__isnull=False)

    def get_surveys_started_summary(self):
        return SurveyQuestionResponse.objects.filter(
            question__question_type__iexact="open-ended")

    def get_surveys_completed_summary(self):
        """Total number of Surveys Completed."""
        return SurveyQuestionResponse.objects.filter(question__label__iexact="Wait Time")

    def get_context_data(self, **kwargs):

        context = super(AnalystSummary, self).\
            get_context_data(**kwargs)

        context['responses'] = self.get_survey_question_responses()
        context['completion_table'] = self.get_completion_table()
        context['st'] = self.get_surveys_triggered_summary()
        context['st_count'] = context['st'].count()

        context['ss'] = self.get_surveys_started_summary()
        context['ss_count'] = context['ss'].count()

        context['sc'] = self.get_surveys_completed_summary()
        context['sc_count'] = context['sc'].count()

        if context['ss_count']:
            context['ss_st_percent'] = 100*context['ss_count']/context['st_count']
        else:
            context['ss_st_percent'] = "--"

        if context['st_count']:
            context['sc_st_percent'] = 100*context['sc_count']/context['st_count']
        else:
            context['sc_st_percent'] = "--"

        # Needed for to populate the Dropdowns (Selects)
        context['services'] = Service.objects.all()
        first_date = Visit.objects.aggregate(Min('visit_time'))['visit_time__min'].date()
        last_date = Visit.objects.aggregate(Max('visit_time'))['visit_time__max'].date()
        context['date_range'] = self.get_date_range(first_date, last_date)
        context['clinics'] = Clinic.objects.all().order_by("name")
        return context


class FilterMixin(object):

    def get_variable(self, request, variable_name, ignore_value):
        data = request.GET.get(variable_name, ignore_value)
        if not data or data == ignore_value:
            return None
        return data


class CompletionFilter(FilterMixin, View):

    def get(self, request):
        the_service = self.get_variable(request, "service", "Service")
        the_start_date = self.get_variable(request, "start_date", "Start Date")
        the_end_date = self.get_variable(request, "end_date", "End Date")

        if not the_start_date or "Start Date" in the_start_date:
            the_start_date = Visit.objects.all().order_by("visit_time")[0].visit_time.date()
        else:
            the_start_date = parse(the_start_date)
        if not the_end_date or "End Date" in the_end_date:
            the_end_date = Visit.objects.all().order_by("-visit_time")[0].visit_time.date()
        else:
            the_end_date = parse(the_end_date)

        a = AnalystSummary()
        data = a.get_completion_table(
            start_date=the_start_date, end_date=the_end_date, service=the_service)
        content = {"clinic_data": {}}
        for a_clinic in data:
            content["clinic_data"][a_clinic["clinic_id"]] = {
                "name": a_clinic["clinic_name"],
                "st": a_clinic["st_count"],
                "ss": a_clinic["ss_count"],
                "sc": a_clinic["sc_count"],
                "scp": a_clinic["sc_st_percent"]
            }

        return HttpResponse(json.dumps(content), content_type="text/json")


class FeedbackFilter(FilterMixin, View):

    def get(self, request):
        the_service = self.get_variable(request, "service", "Service")
        the_clinic = self.get_variable(request, "clinic", "Clinic")
        the_start_date = self.get_variable(request, "start_date", "Start Date")
        the_end_date = self.get_variable(request, "end_date", "End Date")

        qset = SurveyQuestionResponse.objects.all()
        responses = survey_utils.filter_sqr_query(
            qset, clinic=the_clinic, service=the_service,
            start_date=the_start_date, end_date=the_end_date)

        # Render template with responses as context
        tmpl = get_template('analysts/_rates.html')
        ctx = Context({'responses': responses})
        html = tmpl.render(ctx)
        return HttpResponse(html, content_type='text/html')


class RegionReport(ReportMixin, DetailView):
    template_name = 'clinics/summary.html'
    model = models.Region

    def __init__(self, *args, **kwargs):
        super(RegionReport, self).__init__(*args, **kwargs)
        self.curr_date = None
        self.start_date = None
        self.end_date = None

    def get(self, request, *args, **kwargs):
        if 'day' in request.GET and 'month' in request.GET and 'year' in request.GET:
            day = request.GET.get('day')
            month = request.GET.get('month')
            year = request.GET.get('year')
            try:
                self.curr_date = timezone.now().replace(
                    year=int(year), month=int(month), day=int(day))
            except (TypeError, ValueError):
                pass
        return super(RegionReport, self).get(request, *args, **kwargs)

    def calculate_date_range(self):
        try:
            self.start_date = get_week_start(self.curr_date)
            self.end_date = get_week_end(self.curr_date)
        except (ValueError, AttributeError):
            pass

    def get_object(self, queryset=None):
        obj = super(RegionReport, self).get_object(queryset)
        self.calculate_date_range()
        self.initialize_data(obj)
        self.responses = SurveyQuestionResponse.objects.filter(clinic__lga__iexact=obj.name)
        if self.start_date and self.end_date:
            self.responses = self.responses.filter(
                visit__visit_time__range=(self.start_date, self.end_date))
        else:
            self.start_date = self.responses.aggregate(min_date=Min('datetime'))['min_date']
            self.end_date = self.responses.aggregate(max_date=Max('datetime'))['max_date']
        self.responses = self.responses.select_related('question', 'service', 'visit')
        return obj

    def get_context_data(self, **kwargs):
        kwargs['responses'] = self.responses
        kwargs['feedback_by_service'] = self.get_feedback_by_service()
        kwargs['feedback_by_clinic'] = self.get_feedback_by_clinic()
        kwargs['min_date'] = self.start_date
        kwargs['max_date'] = self.end_date
        data = super(RegionReport, self).get_context_data(**kwargs)
        return data

    def get_satisfaction_counts(self, responses):
        """Return satisfaction percentage and total of survey participants

        responses is already grouped by visit"""
        unsatisfied = 0
        total = 0

        target_questions = ['Respectful Staff Treatment', 'Charged Fairly', 'Wait Time']

        for visit, visit_responses in responses:
            if any(r['question__label'] in target_questions for r in visit_responses):
                total += 1
            else:
                continue

            for resp in visit_responses:
                question = resp['question__label']
                answer = resp['response']
                if question in target_questions[:2] and answer != self.questions[
                        question].primary_answer:
                    unsatisfied += 1
                    continue
                if question == target_questions[2] and answer == self.questions[
                        question].get_categories()[-1]:
                    unsatisfied += 1

        if not total:
            return 0, 0

        return 100 - make_percentage(unsatisfied, total), total

    def get_feedback_participation(self, responses, clinic):
        """Return % of surveys responded to to total visits.

        responses already grouped by question."""
        survey_count = len(responses.get('Open Facility', []))
        visits = models.Visit.objects.filter(
            patient__clinic=clinic, survey_sent__isnull=False)
        if self.curr_date:
            visits = visits.filter(visit_time__range=(self.start_date, self.end_date))
        total_visits = visits.count()

        if total_visits:
            survey_percent = make_percentage(survey_count, total_visits)
        else:
            survey_percent = None
        return survey_percent, total_visits

    def get_feedback_by_clinic(self):
        """Return analyzed feedback by clinic then question."""
        data = []

        # So we can get the name of the clinic for the template
        clinic_map = dict(models.Clinic.objects.values_list('id', 'name'))

        responses = self.responses.exclude(clinic=None).values(
            'clinic', 'question__label', 'response', 'visit')
        by_clinic = survey_utils.group_responses(responses, 'clinic', keyfunc=itemgetter)

        # Add clinics without responses back.
        clinic_ids = [clinic[0] for clinic in by_clinic]
        rest_clinics = set(clinic_map.keys()).difference(clinic_ids)
        for _clinic in rest_clinics:
            by_clinic.append((_clinic, []))

        for clinic, clinic_responses in by_clinic:
            by_question = survey_utils.group_responses(
                clinic_responses, 'question__label', keyfunc=itemgetter)
            responses_by_question = dict(by_question)

            # Get feedback participation
            survey_percent, total_visits = self.get_feedback_participation(
                responses_by_question, clinic)

            # Get patient satisfaction
            responses_by_visit = survey_utils.group_responses(
                clinic_responses, 'visit', keyfunc=itemgetter)
            satis_percent, satis_total = self.get_satisfaction_counts(responses_by_visit)

            # Build the data
            clinic_data = [
                ('{}%'.format(survey_percent), total_visits),
                ('{}%'.format(satis_percent), satis_total),
                (None, 0),
                (None, 0)
            ]
            for label in ['Open Facility', 'Respectful Staff Treatment',
                          'Clean Hospital Materials', 'Charged Fairly']:
                if label in responses_by_question:
                    question = self.questions[label]
                    question_responses = responses_by_question[label]
                    total_responses = len(question_responses)
                    answers = [response['response'] for response in question_responses]
                    percentage = survey_utils.analyze(answers, question.primary_answer)
                    clinic_data.append(('{}%'.format(percentage), total_responses))
                else:
                    clinic_data.append((None, 0))

            if 'Wait Time' in responses_by_question:
                wait_times = [r['response'] for r in responses_by_question['Wait Time']]
                mode = survey_utils.get_mode(
                    wait_times, self.questions.get('Wait Time').get_categories())
                clinic_data.append((mode, len(wait_times)))
            else:
                clinic_data.append((None, 0))
            data.append((clinic_map[clinic], clinic_data))
        return data


class FeedbackView(View):
    form_class = forms.FeedbackForm

    @csrf_exempt
    def dispatch(self, *args, **kwargs):
        return super(FeedbackView, self).dispatch(*args, **kwargs)

    def post(self, request):
        form = self.form_class(request.POST)
        if form.is_valid():
            values = form.cleaned_data['values']
            models.GenericFeedback.objects.create(
                sender=form.cleaned_data['phone'],
                clinic=values.get('clinic'),
                message=values.get('message'))

        return HttpResponse('ok')
