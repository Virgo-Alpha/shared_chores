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
