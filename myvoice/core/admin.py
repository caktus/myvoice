from django.contrib import admin

from rapidsms.contrib.messagelog.models import Message


admin.site.unregister(Message)
