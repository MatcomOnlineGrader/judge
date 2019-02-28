from django.contrib import admin

import palantir.models as palantir_models


class AccessLogAdmin(admin.ModelAdmin):
    list_display = ('pk', 'user', 'slug', 'date', )
    search_fields = ('slug', 'user__username', )


admin.site.register(palantir_models.AccessLog, AccessLogAdmin)
