from django.contrib import admin
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Household, User


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
