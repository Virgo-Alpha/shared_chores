from datetime import date, time

from django.test import TestCase

from .models import Household, HouseholdMembership, Task, TaskOccurrence, User


class CalendarTest(TestCase):
	def test_calendar_returns_due_dates_and_optional_times(self):
		household = Household.objects.create(name='Calendar Home')
		user = User.objects.create_user('calendar@example.com', 'password')
		HouseholdMembership.objects.create(user=user, household=household)
		Task.objects.create(household=household, category=household.categories.get(name='Cleaning'), title='Timed', type=Task.Type.CHORE, due_date=date(2026, 9, 7), due_time=time(18, 30))
		self.client.force_login(user)
		response = self.client.get('/calendar/')
		self.assertEqual(response.json()['events'][0]['time'], '18:30:00')

	def test_calendar_includes_recurring_and_overdue_occurrences(self):
		household = Household.objects.create(name='Occurrence Calendar Home')
		user = User.objects.create_user('occ-calendar@example.com', 'password')
		HouseholdMembership.objects.create(user=user, household=household)
		task = Task.objects.create(household=household, category=household.categories.get(name='Cleaning'), title='Overdue chore', type=Task.Type.CHORE)
		TaskOccurrence.objects.create(task=task, scheduled_date=date(2020, 1, 1))
		self.client.force_login(user)
		events = self.client.get('/calendar/').json()['events']
		self.assertTrue(any(event['title'] == 'Overdue chore' and event['overdue'] for event in events))