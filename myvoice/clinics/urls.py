from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^clinics/patient/$', views.VisitView.as_view(), name='visit'),
    url(r'^reports/region/(?P<pk>\d+)/$',
        views.RegionReport.as_view(),
        name='region_report'),
    url(r'^reports/facility/$',
        views.ClinicReportSelectClinic.as_view(),
        name='select_clinic'),
    url(r'^reports/facility/(?P<slug>[ \w-]+)/$',
        views.ClinicReport.as_view(),
        name='clinic_report'),
    url(r'^analyst_summary/$',
        views.AnalystSummary.as_view(),
        name='analyst_summary'),
    url(r'^visit/$', views.VisitView.as_view(), name='visit'),
    url(r'^feedback/$', views.FeedbackView.as_view(), name='visit'),
    url(r'^wamba_report/$',
        views.RegionReport.as_view(),
        name='wamba',
        kwargs=dict(pk=599)),
]
