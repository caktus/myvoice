from django.shortcuts import redirect
from django.views.generic import FormView, TemplateView
from django.http import Http404

from .forms import SelectClinicForm


class PBFDashboardSelect(FormView):
    template_name = 'pbf/select.html'
    form_class = SelectClinicForm

    def form_valid(self, form):
        return redirect('pbf_dashboard', form.cleaned_data['clinic'])


class PBFDashboard(TemplateView):
    template_name = 'pbf/dashboard/dashboard.html'

    def get_context_data(self, **kwargs):
        from .models import CLINIC_DATA
        clinic_slug = kwargs.pop('clinic_slug')
        if clinic_slug not in CLINIC_DATA:
            raise Http404("Clinic with slug '{0}' not found".format(clinic_slug))
        self.clinic = CLINIC_DATA.get(clinic_slug)
        kwargs['clinic'] = CLINIC_DATA.get(clinic_slug)
        kwargs['total_clinics'] = len(CLINIC_DATA)
        return super(PBFDashboard, self).get_context_data(**kwargs)