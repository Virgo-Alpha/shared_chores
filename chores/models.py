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
