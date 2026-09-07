from django.test import TestCase

from .models import Household, HouseholdMembership, Task, User


class AuthorizationRegressionTest(TestCase):
	def setUp(self):
		self.household = Household.objects.create(name='Authorization Home')
		self.owner = User.objects.create_user('auth-owner@example.com', 'password')
		self.member = User.objects.create_user('auth-member@example.com', 'password')
		HouseholdMembership.objects.create(user=self.owner, household=self.household, role=HouseholdMembership.Role.OWNER)
		HouseholdMembership.objects.create(user=self.member, household=self.household, role=HouseholdMembership.Role.RESTRICTED)
		self.task = Task.objects.create(household=self.household, category=self.household.categories.get(name='Cleaning'), title='Protected', type=Task.Type.CHORE)

	def test_anonymous_users_are_redirected_from_protected_endpoints(self):
		self.assertEqual(self.client.get('/tasks/').status_code, 302)
		self.assertEqual(self.client.get('/dashboard/').status_code, 302)

	def test_restricted_member_cannot_manage_members(self):
		self.client.force_login(self.member)
		self.assertEqual(self.client.get('/members/').status_code, 403)

	def test_other_household_cannot_access_task(self):
		other = Household.objects.create(name='Other Authorization Home')
		user = User.objects.create_user('other-auth@example.com', 'password')
		HouseholdMembership.objects.create(user=user, household=other)
		self.client.force_login(user)
		self.assertEqual(self.client.get(f'/tasks/{self.task.pk}/').status_code, 404)