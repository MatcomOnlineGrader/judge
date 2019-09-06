from django.contrib import admin
from .models import *


class UserProfileAdmin(admin.ModelAdmin):
    class RoleFilter(admin.SimpleListFilter):
        title = 'role'
        parameter_name = 'role'

        def lookups(self, request, model_admin):
            return (
                ('admin', 'Administrator'),
                ('browser', 'Code Browser'),
                ('observer', 'Observer'),
                ('*', 'All roles')
            )

        def queryset(self, request, queryset):
            if self.value() == 'admin':
                return queryset.filter(role='admin')
            elif self.value() == 'browser':
                return queryset.filter(role='browser')
            elif self.value() == 'observer':
                return queryset.filter(role='observer')
            elif self.value() == '*':
                return queryset.filter(Q(role='admin') | Q(role='browser') | Q(role='observer'))

    search_fields = ('user__username', )
    list_filter = (RoleFilter, )


class CheckerAdmin(admin.ModelAdmin):
    ordering = ('name', )


class CountryAdmin(admin.ModelAdmin):
    list_display = ('name', )
    ordering = ('name', )
    readonly_fields = ('flag_image_tag', )


class InstitutionAdmin(admin.ModelAdmin):
    ordering = ('name',)


class TagAdmin(admin.ModelAdmin):
    ordering = ('name',)


class UserFeedbackAdmin(admin.ModelAdmin):
    ordering = ('-submitted_date',)


class ContestPermissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'contest', 'role', 'granted', 'date', )

    class ActiveContestPermission(admin.SimpleListFilter):
        title = 'role'
        parameter_name = 'role'

        def lookups(self, request, model_admin):
            return (
                ('active', 'Active'),
                ('judges', 'Judges'),
                ('observers', 'Observers'),
            )

        def queryset(self, request, queryset):
            roles = {
                'active': ['judge', 'observer'],
                'judges': ['judge'],
                'observers': ['observer'],
            }.get(self.value())

            if not roles:
                return None

            ids, saw = [], set()
            for row in queryset.order_by('-pk'):
                key = row.user_id, row.contest_id, row.role
                if key not in saw and row.role in roles:
                    saw.add(key)
                    ids.append(row.pk)

            return queryset.filter(pk__in=ids)

    list_filter = (ActiveContestPermission, )


admin.site.register(Checker, CheckerAdmin)
admin.site.register(Comment)
admin.site.register(Compiler)
admin.site.register(Contest)
admin.site.register(ContestInstance)
admin.site.register(ContestPermission, ContestPermissionAdmin)
admin.site.register(Country, CountryAdmin)
admin.site.register(Division)
admin.site.register(Institution, InstitutionAdmin)
admin.site.register(Message)
admin.site.register(Post)
admin.site.register(Problem)
admin.site.register(RatingChange)
admin.site.register(Result)
admin.site.register(Submission)
admin.site.register(Tag, TagAdmin)
admin.site.register(Team)
admin.site.register(UserFeedback, UserFeedbackAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
