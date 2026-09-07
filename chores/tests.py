from django.contrib import admin
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction
from django.test import TestCase

from .models import Category, Household, HouseholdMembership, Task, User


class ProjectSmokeTest(TestCase):
	def test_admin_url_loads(self):
		response = self.client.get('/admin/')

		self.assertEqual(response.status_code, 302)


class UserAuthenticationTest(TestCase):
	def test_user_creation_normalizes_email_and_hashes_password(self):
		user = User.objects.create_user('person@EXAMPLE.COM', 'plain-password')

		self.assertEqual(user.email, 'person@example.com')
		self.assertNotEqual(user.password, 'plain-password')
		self.assertTrue(user.check_password('plain-password'))

	def test_valid_credentials_authenticate(self):
		User.objects.create_user('person@example.com', 'correct-password')

		user = authenticate(email='person@example.com', password='correct-password')

		self.assertIsNotNone(user)

	def test_invalid_credentials_are_rejected(self):
		User.objects.create_user('person@example.com', 'correct-password')

		self.assertIsNone(authenticate(email='person@example.com', password='wrong-password'))
		self.assertIsNone(authenticate(email='unknown@example.com', password='correct-password'))

	def test_custom_user_is_registered_with_admin(self):
		self.assertIn(User, admin.site._registry)


class HouseholdModelTest(TestCase):
	def test_household_can_be_created_retrieved_updated_and_deleted(self):
		household = Household.objects.create(name='The Smith Home')

		self.assertEqual(str(household), 'The Smith Home')
		self.assertEqual(Household.objects.get(pk=household.pk).name, 'The Smith Home')

		household.name = 'The Smith Family Home'
		household.save()
		self.assertEqual(Household.objects.get(pk=household.pk).name, 'The Smith Family Home')

		household.delete()
		self.assertFalse(Household.objects.filter(pk=household.pk).exists())

	def test_household_name_is_required(self):
		household = Household()

		with self.assertRaises(ValidationError):
			household.full_clean()


class CategoryModelTest(TestCase):
	def test_new_household_gets_default_categories(self):
		household = Household.objects.create(name='Category Home')

		self.assertEqual(
			set(household.categories.values_list('name', flat=True)),
			set(Category.DEFAULT_NAMES),
		)

	def test_custom_category_can_be_renamed(self):
		household = Household.objects.create(name='Category Home')
		category = Category.objects.create(household=household, name='Pets')

		category.name = 'Pet care'
		category.save()

		self.assertEqual(Category.objects.get(pk=category.pk).name, 'Pet care')

	def test_duplicate_category_names_are_scoped_to_household(self):
		household = Household.objects.create(name='Category Home')
		other_household = Household.objects.create(name='Other Home')

		with self.assertRaises(IntegrityError):
			with transaction.atomic():
				Category.objects.create(household=household, name='Cleaning')
		self.assertTrue(other_household.categories.filter(name='Cleaning').exists())

	def test_category_belongs_to_one_household(self):
		household = Household.objects.create(name='Category Home')
		other_household = Household.objects.create(name='Other Home')
		category = Category.objects.create(household=household, name='Pets')

		self.assertNotIn(category, other_household.categories.all())


class TaskModelTest(TestCase):
	def setUp(self):
		self.household = Household.objects.create(name='Task Home')
		self.category = self.household.categories.get(name='Cleaning')

	def test_task_stores_required_and_optional_fields(self):
		task = Task.objects.create(
			household=self.household,
			category=self.category,
			title='Clean kitchen',
			description='Wipe surfaces and mop the floor.',
			type=Task.Type.CHORE,
			priority=Task.Priority.HIGH,
			estimated_effort=45,
			workload_points=5,
			due_date='2026-09-07',
			due_time='18:30',
		)

		self.assertEqual(str(task), 'Clean kitchen')
		self.assertEqual(Task.objects.get(pk=task.pk).workload_points, 5)

	def test_task_accepts_both_types_and_priorities(self):
		for task_type in Task.Type.values:
			for priority in Task.Priority.values:
				task = Task(
					household=self.household,
					category=self.category,
					title=f'{task_type}-{priority}',
					type=task_type,
					priority=priority,
				)
				task.full_clean()

	def test_invalid_choices_and_cross_household_category_are_rejected(self):
		other_household = Household.objects.create(name='Other Task Home')
		task = Task(
			household=self.household,
			category=other_household.categories.get(name='Cleaning'),
			title='Invalid task',
			type='INVALID',
			priority='INVALID',
		)

		with self.assertRaises(ValidationError):
			task.full_clean()

	def test_title_and_type_are_required(self):
		task = Task(household=self.household, category=self.category)

		with self.assertRaises(ValidationError):
			task.full_clean()


class HouseholdMembershipTest(TestCase):
	def setUp(self):
		self.user = User.objects.create_user('member@example.com', 'password')
		self.household = Household.objects.create(name='The Smith Home')

	def test_membership_connects_user_household_and_role(self):
		membership = HouseholdMembership.objects.create(
			user=self.user,
			household=self.household,
			role=HouseholdMembership.Role.OWNER,
		)

		self.assertEqual(self.user.household_membership, membership)
		self.assertEqual(membership.household, self.household)
		self.assertEqual(membership.get_role_display(), 'Owner/Admin')

	def test_user_cannot_have_two_memberships(self):
		HouseholdMembership.objects.create(user=self.user, household=self.household)
		other_household = Household.objects.create(name='The Jones Home')

		with self.assertRaises(IntegrityError):
			HouseholdMembership.objects.create(user=self.user, household=other_household)

	def test_invalid_role_is_rejected(self):
		membership = HouseholdMembership(user=self.user, household=self.household, role='INVALID')

		with self.assertRaises(ValidationError):
			membership.full_clean()


class MemberAdministrationTest(TestCase):
	def setUp(self):
		self.client_owner = User.objects.create_user('owner@example.com', 'password')
		self.owner_household = Household.objects.create(name='Owner Home')
		HouseholdMembership.objects.create(
			user=self.client_owner,
			household=self.owner_household,
			role=HouseholdMembership.Role.OWNER,
		)
		self.client.force_login(self.client_owner)

	def test_owner_can_create_and_deactivate_member(self):
		response = self.client.post('/members/create/', {
			'email': 'new@example.com',
			'password': 'new-password',
			'role': HouseholdMembership.Role.MEMBER,
		})

		self.assertEqual(response.status_code, 201)
		member = User.objects.get(email='new@example.com')
		self.assertTrue(self.client.post(f'/members/{member.pk}/deactivate/').json()['is_active'] is False)
		self.assertFalse(User.objects.get(pk=member.pk).is_active)
		self.assertIsNone(authenticate(email=member.email, password='new-password'))

	def test_non_owner_is_denied(self):
		member = User.objects.create_user('member@example.com', 'password')
		HouseholdMembership.objects.create(
			user=member,
			household=self.owner_household,
			role=HouseholdMembership.Role.MEMBER,
		)
		self.client.force_login(member)

		self.assertEqual(self.client.get('/members/').status_code, 403)
		self.assertEqual(self.client.post('/members/create/').status_code, 403)

	def test_owner_cannot_manage_another_household(self):
		other_user = User.objects.create_user('other@example.com', 'password')
		other_household = Household.objects.create(name='Other Home')
		HouseholdMembership.objects.create(
			user=other_user,
			household=other_household,
			role=HouseholdMembership.Role.MEMBER,
		)

		self.assertEqual(self.client.post(f'/members/{other_user.pk}/deactivate/').status_code, 404)
