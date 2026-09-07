from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Category, ChecklistItem, Completion, HouseholdMembership, RecurrenceRule, Task, TaskAssignment, TaskOccurrence, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
	ordering = ('email',)
	list_display = ('email', 'is_staff', 'is_active')
	fieldsets = (
		(None, {'fields': ('email', 'password')}),
		('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
		('Important dates', {'fields': ('last_login', 'date_joined')}),
	)
	add_fieldsets = (
		(None, {
			'classes': ('wide',),
			'fields': ('email', 'password1', 'password2', 'is_staff', 'is_active'),
		}),
	)


@admin.register(HouseholdMembership)
class HouseholdMembershipAdmin(admin.ModelAdmin):
	list_display = ('user', 'household', 'role')
	list_filter = ('role',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
	list_display = ('name', 'household')
	list_filter = ('household',)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
	list_display = ('title', 'household', 'type', 'priority', 'due_date')
	list_filter = ('type', 'priority', 'household')


@admin.register(TaskAssignment)
class TaskAssignmentAdmin(admin.ModelAdmin):
	list_display = ('task', 'user')


@admin.register(RecurrenceRule)
class RecurrenceRuleAdmin(admin.ModelAdmin):
	list_display = ('task', 'frequency')


@admin.register(TaskOccurrence)
class TaskOccurrenceAdmin(admin.ModelAdmin):
	list_display = ('task', 'scheduled_date', 'completed_at')


@admin.register(ChecklistItem)
class ChecklistItemAdmin(admin.ModelAdmin):
	list_display = ('task', 'position', 'text', 'completed')


@admin.register(Completion)
class CompletionAdmin(admin.ModelAdmin):
	list_display = ('occurrence', 'user', 'completed_at')
