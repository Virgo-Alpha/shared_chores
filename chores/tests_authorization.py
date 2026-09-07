from django.test import TestCase

from datetime import date

from .models import Completion, Household, HouseholdMembership, NotificationPreference, Task, TaskAssignment, TaskOccurrence, User


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

	def test_other_household_cannot_access_completion_or_preferences(self):
		occurrence = TaskOccurrence.objects.create(task=self.task, scheduled_date=date(2026, 9, 7))
		TaskAssignment.objects.create(task=self.task, user=self.owner)
		completion = Completion.objects.create(occurrence=occurrence, user=self.owner)
		other = Household.objects.create(name='Other Protected Home')
		other_user = User.objects.create_user('other-protected@example.com', 'password')
		HouseholdMembership.objects.create(user=other_user, household=other)
		self.client.force_login(other_user)
		self.assertEqual(self.client.post(f'/occurrences/{occurrence.pk}/complete/').status_code, 404)
		self.assertEqual(self.client.post(f'/completions/{completion.pk}/proof/', {'note': 'No'}).status_code, 404)
		self.assertEqual(self.client.post(f'/completions/{completion.pk}/approval/', {'status': 'APPROVED'}).status_code, 404)
		self.assertEqual(self.client.get('/notification-preferences/').status_code, 200)
		self.assertTrue(NotificationPreference.objects.filter(user=other_user).exists())
		self.assertFalse(NotificationPreference.objects.filter(user=self.owner).exists())