from django.contrib import admin
from leaflet.admin import LeafletGeoAdmin

from . import models
from .forms import ClinicStatisticAdminForm


class ClinicStaffInline(admin.TabularInline):
    model = models.ClinicStaff
    extra = 0


# NOTE: This is included for early development/debugging purposes. Eventually,
# there will be many more statistics for a clinic than a simple inline can
# handle.
class ClinicStatisticInline(admin.TabularInline):
    model = models.ClinicStatistic
    extra = 0
    form = ClinicStatisticAdminForm


class ClinicAdmin(LeafletGeoAdmin):
    inlines = [ClinicStaffInline, ClinicStatisticInline]
    list_display = ['name', 'lga']
    prepopulated_fields = {'slug': ['name']}
    readonly_fields = ['lga_rank', 'pbf_rank']
    display_raw = True


class ClinicStatisticAdmin(admin.ModelAdmin):
    form = ClinicStatisticAdminForm
    list_display = ['statistic', 'month', 'clinic', 'service', 'value', 'n', 'rank']
    list_filter = ['statistic', 'clinic', 'service']
    date_hierarchy = 'month'
    readonly_fields = ['rank']

    def value(self, obj):
        return obj.get_value_display()


class RegionAdmin(LeafletGeoAdmin):
    search_fields = ['name', 'alternate_name', 'external_id']
    list_display = ['name', 'alternate_name', 'type']
    list_filter = ['type']
    ordering = ['type', 'name']


class PatientAdmin(admin.ModelAdmin):
    list_display = ['name', 'clinic', 'contact']
    search_fields = ['name']


class VisitAdmin(admin.ModelAdmin):
    list_display = ['patient', 'visit_time', 'service_type', 'staff']
    date_hierarchy = 'visit_time'


class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    ordering = ['name']


admin.site.register(models.Clinic, ClinicAdmin)
admin.site.register(models.ClinicStatistic, ClinicStatisticAdmin)
admin.site.register(models.Region, RegionAdmin)
admin.site.register(models.Patient, PatientAdmin)
admin.site.register(models.Visit, VisitAdmin)
admin.site.register(models.Service, ServiceAdmin)
