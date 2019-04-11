from django.contrib import admin
from django.db.models import Q

import palantir.models as palantir_models


class AccessLogAdmin(admin.ModelAdmin):
    class DefinedUserFilter(admin.SimpleListFilter):
        title = 'user'
        parameter_name = 'user'

        def lookups(self, request, model_admin):
            return (
                ('active-user', 'Active users'),
                ('inactive-user', 'Inactive users'),
                ('defined-user', 'Defined users (active & inactive)'),
            )

        def queryset(self, request, queryset):
            if self.value() == 'active-user':
                return queryset.filter(user__is_active=True)
            if self.value() == 'inactive-user':
                return queryset.filter(user__is_active=False)
            if self.value() == 'defined-user':
                return queryset.filter(~Q(user=None))

    list_display = ('pk', 'user', 'slug', 'date', )
    search_fields = ('slug', 'user__username', )
    list_filter = (DefinedUserFilter, )


admin.site.register(palantir_models.AccessLog, AccessLogAdmin)
