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
                ('admin|browser', 'Administrator or Code Browser')
            )

        def queryset(self, request, queryset):
            if self.value() == 'admin':
                return queryset.filter(role='admin')
            elif self.value() == 'browser':
                return queryset.filter(role='browser')
            elif self.value() == 'admin|browser':
                return queryset.filter(Q(role='admin') | Q(role='browser'))

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


admin.site.register(Country, CountryAdmin)
admin.site.register(Team)
admin.site.register(Tag, TagAdmin)
admin.site.register(Checker, CheckerAdmin)
admin.site.register(Contest)
admin.site.register(Problem)
admin.site.register(Post)
admin.site.register(Message)
admin.site.register(Division)
admin.site.register(Institution, InstitutionAdmin)
admin.site.register(RatingChange)
admin.site.register(Compiler)
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(Result)
admin.site.register(Submission)
admin.site.register(Comment)
admin.site.register(ContestInstance)
admin.site.register(UserFeedback, UserFeedbackAdmin)
