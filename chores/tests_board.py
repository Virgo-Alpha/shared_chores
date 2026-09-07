from django.test import TestCase

from .models import Household, HouseholdMembership, Task, User


class BoardTest(TestCase):
	def test_board_lists_household_tasks_and_filters(self):
		household = Household.objects.create(name='Board Home')
		user = User.objects.create_user('board@example.com', 'password')
		HouseholdMembership.objects.create(user=user, household=household)
		Task.objects.create(household=household, category=household.categories.get(name='Cleaning'), title='Board task', type=Task.Type.CHORE)
		self.client.force_login(user)
		response = self.client.get('/board/?type=CHORE')
		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.json()['tasks']), 1)