import calendar
from datetime import date, timedelta

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
	def create_user(self, email, password=None, **extra_fields):
		if not email:
			raise ValueError('Users must have an email address.')

		user = self.model(email=self.normalize_email(email), **extra_fields)
		user.set_password(password)
		user.save(using=self._db)
		return user

	def create_superuser(self, email, password=None, **extra_fields):
		extra_fields.setdefault('is_staff', True)
		extra_fields.setdefault('is_superuser', True)
		extra_fields.setdefault('is_active', True)

		if extra_fields.get('is_staff') is not True:
			raise ValueError('Superuser must have is_staff=True.')
		if extra_fields.get('is_superuser') is not True:
			raise ValueError('Superuser must have is_superuser=True.')

		return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
	email = models.EmailField(unique=True)
	is_staff = models.BooleanField(default=False)
	is_active = models.BooleanField(default=True)
	date_joined = models.DateTimeField(auto_now_add=True)

	objects = UserManager()

	USERNAME_FIELD = 'email'
	REQUIRED_FIELDS = []

	def __str__(self):
		return self.email


class Household(models.Model):
	name = models.CharField(max_length=200)

	def save(self, *args, **kwargs):
		is_new = self._state.adding
		super().save(*args, **kwargs)
		if is_new:
			Category.objects.bulk_create([
				Category(household=self, name=name)
				for name in Category.DEFAULT_NAMES
			])

	def __str__(self):
		return self.name


class HouseholdMembership(models.Model):
	class Role(models.TextChoices):
		OWNER = 'OWNER', 'Owner/Admin'
		MEMBER = 'MEMBER', 'Member'
		RESTRICTED = 'RESTRICTED', 'Child/Restricted Member'

	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='household_membership')
	household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name='memberships')
	role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)

	def __str__(self):
		return f'{self.user} - {self.household} ({self.get_role_display()})'


class Category(models.Model):
	DEFAULT_NAMES = ('Cleaning', 'Cooking', 'Laundry', 'Shopping', 'Maintenance')

	household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name='categories')
	name = models.CharField(max_length=100)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=('household', 'name'), name='unique_category_per_household'),
		]

	def __str__(self):
		return self.name


class Task(models.Model):
	class Type(models.TextChoices):
		CHORE = 'CHORE', 'Chore'
		ONE_OFF = 'ONE_OFF', 'One-off'

	class Priority(models.TextChoices):
		LOW = 'LOW', 'Low'
		MEDIUM = 'MEDIUM', 'Medium'
		HIGH = 'HIGH', 'High'

	class AssignmentMode(models.TextChoices):
		SINGLE = 'SINGLE', 'Single'
		JOINT = 'JOINT', 'Joint'
		ANY_OF = 'ANY_OF', 'Any of'
		CLAIMABLE = 'CLAIMABLE', 'Claimable pool'

	household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name='tasks')
	category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='tasks')
	title = models.CharField(max_length=200)
	description = models.TextField(blank=True)
	type = models.CharField(max_length=10, choices=Type.choices)
	priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
	assignment_mode = models.CharField(max_length=10, choices=AssignmentMode.choices, default=AssignmentMode.SINGLE)
	rotation_index = models.PositiveIntegerField(default=0)
	estimated_effort = models.PositiveIntegerField(null=True, blank=True)
	workload_points = models.PositiveIntegerField(default=0)
	due_date = models.DateField(null=True, blank=True)
	due_time = models.TimeField(null=True, blank=True)

	def clean(self):
		super().clean()
		if self.category_id and self.household_id and self.category.household_id != self.household_id:
			from django.core.exceptions import ValidationError

			raise ValidationError({'category': 'Category must belong to the task household.'})

	def __str__(self):
		return self.title

	def assign_next_member(self):
		from django.db import transaction

		with transaction.atomic():
			task = Task.objects.select_for_update().get(pk=self.pk)
			memberships = list(
				task.household.memberships.filter(user__is_active=True).order_by('pk')
			)
			if not memberships:
				return None
			membership = memberships[task.rotation_index % len(memberships)]
			TaskAssignment.objects.update_or_create(task=task, defaults={'user': membership.user})
			task.rotation_index = (task.rotation_index + 1) % len(memberships)
			task.save(update_fields=['rotation_index'])
			self.rotation_index = task.rotation_index
			return membership.user

	def claim(self, user):
		from django.core.exceptions import ValidationError
		from django.db import transaction

		with transaction.atomic():
			task = Task.objects.select_for_update().get(pk=self.pk)
			membership = getattr(user, 'household_membership', None)
			if task.assignment_mode != self.AssignmentMode.CLAIMABLE:
				raise ValidationError('Only claimable tasks can be claimed.')
			if not user.is_active or not membership or membership.household_id != task.household_id:
				raise ValidationError('Only active household members can claim this task.')
			assignment = task.assignments.first()
			if assignment:
				if assignment.user_id != user.pk:
					raise ValidationError('This task has already been claimed.')
				return assignment
			return TaskAssignment.objects.create(task=task, user=user)


class TaskAssignment(models.Model):
	task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='assignments')
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task_assignments')

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=('task', 'user'), name='unique_task_assignment'),
		]

	def clean(self):
		super().clean()
		membership = getattr(self.user, 'household_membership', None)
		if not membership or not self.user.is_active or membership.household_id != self.task.household_id:
			from django.core.exceptions import ValidationError

			raise ValidationError({'user': 'Assignment must target an active member of the task household.'})
		if self.task.assignment_mode == Task.AssignmentMode.SINGLE:
			queryset = TaskAssignment.objects.filter(task=self.task)
			if self.pk:
				queryset = queryset.exclude(pk=self.pk)
			if queryset.exists():
				from django.core.exceptions import ValidationError

				raise ValidationError({'task': 'Single-assignee tasks accept one member.'})


class RecurrenceRule(models.Model):
	class Frequency(models.TextChoices):
		DAILY = 'DAILY', 'Daily'
		WEEKLY = 'WEEKLY', 'Weekly'
		MONTHLY = 'MONTHLY', 'Monthly'
		INTERVAL = 'INTERVAL', 'Every N days'
		WEEKDAYS = 'WEEKDAYS', 'Weekdays'
		MONTHLY_WEEKDAY = 'MONTHLY_WEEKDAY', 'First weekday of month'

	task = models.OneToOneField(Task, on_delete=models.CASCADE, related_name='recurrence')
	frequency = models.CharField(max_length=20, choices=Frequency.choices)
	interval_days = models.PositiveIntegerField(null=True, blank=True)
	weekday = models.PositiveSmallIntegerField(null=True, blank=True)

	def clean(self):
		from django.core.exceptions import ValidationError

		super().clean()
		if self.frequency == self.Frequency.INTERVAL and not self.interval_days:
			raise ValidationError({'interval_days': 'An interval must be at least one day.'})
		if self.frequency != self.Frequency.INTERVAL and self.interval_days:
			raise ValidationError({'interval_days': 'Intervals are only valid for interval rules.'})
		if self.frequency == self.Frequency.MONTHLY_WEEKDAY and self.weekday not in range(7):
			raise ValidationError({'weekday': 'A weekday from Monday to Sunday is required.'})

	def next_date(self, start):
		if self.frequency == self.Frequency.DAILY:
			return start + timedelta(days=1)
		if self.frequency == self.Frequency.WEEKLY:
			return start + timedelta(days=7)
		if self.frequency == self.Frequency.MONTHLY:
			month = start.month % 12 + 1
			year = start.year + (start.month == 12)
			return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))
		if self.frequency == self.Frequency.INTERVAL:
			return start + timedelta(days=self.interval_days)
		if self.frequency == self.Frequency.WEEKDAYS:
			candidate = start + timedelta(days=1)
			while candidate.weekday() >= 5:
				candidate += timedelta(days=1)
			return candidate
		first = date(start.year, start.month, 1)
		while first.weekday() != self.weekday:
			first += timedelta(days=1)
		if first <= start:
			month = start.month % 12 + 1
			year = start.year + (start.month == 12)
			first = date(year, month, 1)
			while first.weekday() != self.weekday:
				first += timedelta(days=1)
		return first


class TaskOccurrence(models.Model):
	task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='occurrences')
	scheduled_date = models.DateField()
	completed_at = models.DateTimeField(null=True, blank=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=('task', 'scheduled_date'), name='unique_task_occurrence'),
		]

	@property
	def is_overdue(self):
		from django.utils import timezone

		return self.completed_at is None and self.scheduled_date < timezone.localdate()

	@classmethod
	def generate_for_date(cls, task, scheduled_date):
		occurrence, _ = cls.objects.get_or_create(task=task, scheduled_date=scheduled_date)
		return occurrence


class ChecklistItem(models.Model):
	task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='checklist_items')
	text = models.CharField(max_length=300)
	position = models.PositiveIntegerField(default=0)
	completed = models.BooleanField(default=False)

	class Meta:
		ordering = ('position', 'pk')

	def __str__(self):
		return self.text


class Completion(models.Model):
	occurrence = models.ForeignKey(TaskOccurrence, on_delete=models.CASCADE, related_name='completions')
	user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='completions')
	completed_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=('occurrence', 'user'), name='unique_occurrence_completion'),
		]

	def clean(self):
		from django.core.exceptions import ValidationError

		assigned = self.occurrence.task.assignments.filter(user=self.user).exists()
		if not assigned:
			raise ValidationError({'user': 'Only an assigned member can complete this task.'})

	@property
	def task(self):
		return self.occurrence.task


class CompletionProof(models.Model):
	completion = models.OneToOneField(Completion, on_delete=models.CASCADE, related_name='proof')
	note = models.TextField(blank=True)
	photo = models.CharField(max_length=500, blank=True)

	def clean(self):
		from django.core.exceptions import ValidationError

		if not self.note and not self.photo:
			raise ValidationError('A proof note or photo is required.')


class Approval(models.Model):
	class Status(models.TextChoices):
		PENDING = 'PENDING', 'Pending'
		APPROVED = 'APPROVED', 'Approved'
		REJECTED = 'REJECTED', 'Rejected'

	completion = models.OneToOneField(Completion, on_delete=models.CASCADE, related_name='approval')
	reviewer = models.ForeignKey(User, on_delete=models.PROTECT, related_name='approvals')
	status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
	reviewed_at = models.DateTimeField(null=True, blank=True)

	def clean(self):
		from django.core.exceptions import ValidationError

		membership = getattr(self.reviewer, 'household_membership', None)
		if not membership or membership.household_id != self.completion.task.household_id:
			raise ValidationError({'reviewer': 'Reviewer must belong to the task household.'})


class NotificationPreference(models.Model):
	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
	upcoming_due = models.BooleanField(default=True)
	overdue = models.BooleanField(default=True)
	assignments = models.BooleanField(default=True)
	rotation_changes = models.BooleanField(default=True)
	completions = models.BooleanField(default=True)
	approval_requests = models.BooleanField(default=True)
	approval_results = models.BooleanField(default=True)


def occurrence_is_complete(self):
	assignments = set(self.task.assignments.values_list('user_id', flat=True))
	completions = set(self.completions.values_list('user_id', flat=True))
	if self.task.assignment_mode == Task.AssignmentMode.JOINT:
		return assignments <= completions
	return bool(assignments & completions)


TaskOccurrence.is_complete = property(occurrence_is_complete)
