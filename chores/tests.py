from datetime import date
from datetime import datetime, timezone as dt_timezone

from django.contrib import admin
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Approval, Category, ChecklistItem, Completion, CompletionProof, Household, HouseholdMembership, Notification, NotificationPreference, PointsLedger, RecurrenceRule, Streak, Task, TaskAssignment, TaskOccurrence, User, household_workload


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


class TaskAssignmentTest(TestCase):
	def setUp(self):
		self.household = Household.objects.create(name='Assignment Home')
		self.category = self.household.categories.get(name='Cleaning')
		self.task = Task.objects.create(
			household=self.household, category=self.category,
			title='Assigned task', type=Task.Type.CHORE,
		)
		self.first_user = User.objects.create_user('first@example.com', 'password')
		self.second_user = User.objects.create_user('second@example.com', 'password')
		for user in (self.first_user, self.second_user):
			HouseholdMembership.objects.create(user=user, household=self.household)

	def test_single_mode_accepts_one_assignee_only(self):
		TaskAssignment.objects.create(task=self.task, user=self.first_user)
		second = TaskAssignment(task=self.task, user=self.second_user)

		with self.assertRaises(ValidationError):
			second.full_clean()

	def test_joint_and_any_of_allow_multiple_assignees(self):
		for mode in (Task.AssignmentMode.JOINT, Task.AssignmentMode.ANY_OF):
			task = Task.objects.create(
				household=self.household, category=self.category,
				title=mode, type=Task.Type.CHORE, assignment_mode=mode,
			)
			TaskAssignment.objects.create(task=task, user=self.first_user)
			TaskAssignment.objects.create(task=task, user=self.second_user)

	def test_inactive_and_cross_household_users_are_rejected(self):
		self.first_user.is_active = False
		self.first_user.save(update_fields=['is_active'])
		inactive = TaskAssignment(task=self.task, user=self.first_user)
		with self.assertRaises(ValidationError):
			inactive.full_clean()

		other_household = Household.objects.create(name='Other Assignment Home')
		other_user = User.objects.create_user('other-assignment@example.com', 'password')
		HouseholdMembership.objects.create(user=other_user, household=other_household)
		cross_household = TaskAssignment(task=self.task, user=other_user)
		with self.assertRaises(ValidationError):
			cross_household.full_clean()

	def test_claimable_task_can_be_claimed_once_by_an_active_member(self):
		self.task.assignment_mode = Task.AssignmentMode.CLAIMABLE
		self.task.save(update_fields=['assignment_mode'])

		self.assertEqual(self.task.claim(self.first_user).user, self.first_user)
		self.assertEqual(self.task.claim(self.first_user).user, self.first_user)
		with self.assertRaises(ValidationError):
			self.task.claim(self.second_user)

	def test_claim_rejects_inactive_or_cross_household_users(self):
		self.task.assignment_mode = Task.AssignmentMode.CLAIMABLE
		self.task.save(update_fields=['assignment_mode'])
		self.first_user.is_active = False
		self.first_user.save(update_fields=['is_active'])
		with self.assertRaises(ValidationError):
			self.task.claim(self.first_user)

		other_household = Household.objects.create(name='Claim Other Home')
		other_user = User.objects.create_user('claim-other@example.com', 'password')
		HouseholdMembership.objects.create(user=other_user, household=other_household)
		with self.assertRaises(ValidationError):
			self.task.claim(other_user)

	def test_non_claimable_task_cannot_be_claimed(self):
		with self.assertRaises(ValidationError):
			self.task.claim(self.first_user)

	def test_round_robin_orders_wraps_and_skips_inactive_members(self):
		third_user = User.objects.create_user('third@example.com', 'password')
		HouseholdMembership.objects.create(user=third_user, household=self.household)

		self.assertEqual(self.task.assign_next_member(), self.first_user)
		self.assertEqual(self.task.assign_next_member(), self.second_user)
		self.assertEqual(self.task.assign_next_member(), third_user)
		self.assertEqual(self.task.assign_next_member(), self.first_user)

		self.second_user.is_active = False
		self.second_user.save(update_fields=['is_active'])
		self.assertEqual(self.task.assign_next_member(), third_user)
		self.assertEqual(self.task.assign_next_member(), self.first_user)
		self.assertEqual(self.task.assign_next_member(), third_user)
		self.assertEqual(Task.objects.get(pk=self.task.pk).rotation_index, 0)

	def test_claimable_task_can_be_claimed_once_by_an_active_member(self):
		self.task.assignment_mode = Task.AssignmentMode.CLAIMABLE
		self.task.save(update_fields=['assignment_mode'])

		self.assertEqual(self.task.claim(self.first_user).user, self.first_user)
		self.assertEqual(self.task.claim(self.first_user).user, self.first_user)
		with self.assertRaises(ValidationError):
			self.task.claim(self.second_user)

	def test_claim_rejects_inactive_or_cross_household_users(self):
		self.task.assignment_mode = Task.AssignmentMode.CLAIMABLE
		self.task.save(update_fields=['assignment_mode'])
		self.first_user.is_active = False
		self.first_user.save(update_fields=['is_active'])
		with self.assertRaises(ValidationError):
			self.task.claim(self.first_user)


class RecurrenceRuleTest(TestCase):
	def setUp(self):
		household = Household.objects.create(name='Recurrence Home')
		self.task = Task.objects.create(
			household=household, category=household.categories.get(name='Cleaning'),
			title='Recurring task', type=Task.Type.CHORE,
		)

	def test_supported_rules_calculate_next_dates(self):
		cases = [
			(RecurrenceRule.Frequency.DAILY, {}, date(2026, 9, 8)),
			(RecurrenceRule.Frequency.WEEKLY, {}, date(2026, 9, 14)),
			(RecurrenceRule.Frequency.MONTHLY, {}, date(2026, 10, 7)),
			(RecurrenceRule.Frequency.INTERVAL, {'interval_days': 3}, date(2026, 9, 10)),
			(RecurrenceRule.Frequency.WEEKDAYS, {}, date(2026, 9, 8)),
		]
		for frequency, fields, expected in cases:
			rule = RecurrenceRule(task=self.task, frequency=frequency, **fields)
			rule.full_clean()
			self.assertEqual(rule.next_date(date(2026, 9, 7)), expected)

	def test_first_weekday_of_next_month(self):
		rule = RecurrenceRule(
			task=self.task,
			frequency=RecurrenceRule.Frequency.MONTHLY_WEEKDAY,
			weekday=5,
		)

		self.assertEqual(rule.next_date(date(2026, 9, 7)), date(2026, 10, 3))

	def test_invalid_rule_parameters_are_rejected(self):
		rule = RecurrenceRule(task=self.task, frequency=RecurrenceRule.Frequency.INTERVAL)
		with self.assertRaises(ValidationError):
			rule.full_clean()

	def test_timezone_is_explicit_and_aware_datetimes_use_it(self):
		rule = RecurrenceRule(task=self.task, frequency=RecurrenceRule.Frequency.DAILY, timezone='America/New_York')
		rule.full_clean()

		self.assertEqual(
			rule.next_date(datetime(2026, 9, 7, 1, tzinfo=dt_timezone.utc)),
			date(2026, 9, 7),
		)
		with self.assertRaises(ValidationError):
			RecurrenceRule(task=self.task, frequency=RecurrenceRule.Frequency.DAILY, timezone='Not/AZone').full_clean()


class TaskOccurrenceTest(TestCase):
	def setUp(self):
		household = Household.objects.create(name='Occurrence Home')
		self.task = Task.objects.create(
			household=household, category=household.categories.get(name='Cleaning'),
			title='Recurring task', type=Task.Type.CHORE,
		)

	@override_settings(USE_TZ=True)
	def test_occurrence_is_idempotent_and_overdue_until_completed(self):
		occurrence = TaskOccurrence.generate_for_date(self.task, date(2020, 1, 1))
		self.assertTrue(occurrence.is_overdue)
		self.assertEqual(TaskOccurrence.generate_for_date(self.task, date(2020, 1, 1)).pk, occurrence.pk)
		occurrence.completed_at = timezone.now()
		occurrence.save(update_fields=['completed_at'])
		self.assertFalse(occurrence.is_overdue)

	def test_next_occurrence_uses_task_recurrence_and_is_idempotent(self):
		RecurrenceRule.objects.create(task=self.task, frequency=RecurrenceRule.Frequency.DAILY)

		first = TaskOccurrence.generate_next(self.task, date(2026, 9, 7))
		second = TaskOccurrence.generate_next(self.task, date(2026, 9, 7))

		self.assertEqual(first.scheduled_date, date(2026, 9, 8))
		self.assertEqual(first.pk, second.pk)


class ChecklistItemTest(TestCase):
	def test_items_are_ordered_and_can_be_completed_or_reopened(self):
		household = Household.objects.create(name='Checklist Home')
		task = Task.objects.create(
			household=household, category=household.categories.get(name='Cleaning'),
			title='Clean kitchen', type=Task.Type.CHORE,
		)
		last = ChecklistItem.objects.create(task=task, text='Mop floor', position=2)
		first = ChecklistItem.objects.create(task=task, text='Wipe counters', position=1)

		self.assertEqual(list(task.checklist_items.all()), [first, last])
		first.completed = True
		first.save(update_fields=['completed'])
		first.completed = False
		first.save(update_fields=['completed'])
		self.assertFalse(ChecklistItem.objects.get(pk=first.pk).completed)

	def test_checklist_endpoints_create_edit_reorder_and_complete(self):
		household = Household.objects.create(name='Checklist API Home')
		user = User.objects.create_user('checklist-api@example.com', 'password')
		HouseholdMembership.objects.create(user=user, household=household)
		task = Task.objects.create(household=household, category=household.categories.get(name='Cleaning'), title='API checklist', type=Task.Type.CHORE)
		self.client.force_login(user)
		created = self.client.post(f'/tasks/{task.pk}/checklist/', {'text': 'Wipe counters', 'position': 2})
		self.assertEqual(created.status_code, 201)
		item_id = created.json()['id']
		updated = self.client.post(f'/tasks/{task.pk}/checklist/{item_id}/', {'text': 'Clean counters', 'position': 1, 'completed': 'true'})
		self.assertEqual(updated.json()['completed'], True)
		self.assertEqual(self.client.get(f'/tasks/{task.pk}/checklist/').json()['items'][0]['position'], 1)

	def test_parent_deletion_cascades_checklist_items(self):
		household = Household.objects.create(name='Checklist Delete Home')
		task = Task.objects.create(household=household, category=household.categories.get(name='Cleaning'), title='Delete checklist', type=Task.Type.CHORE)
		item = ChecklistItem.objects.create(task=task, text='Remove me')
		task.delete()
		self.assertFalse(ChecklistItem.objects.filter(pk=item.pk).exists())


class CompletionTest(TestCase):
	def setUp(self):
		household = Household.objects.create(name='Completion Home')
		self.task = Task.objects.create(
			household=household, category=household.categories.get(name='Cleaning'),
			title='Complete task', type=Task.Type.CHORE,
		)
		self.first_user = User.objects.create_user('completion-one@example.com', 'password')
		self.second_user = User.objects.create_user('completion-two@example.com', 'password')
		for user in (self.first_user, self.second_user):
			HouseholdMembership.objects.create(user=user, household=household)
			TaskAssignment.objects.create(task=self.task, user=user)
		self.occurrence = TaskOccurrence.objects.create(task=self.task, scheduled_date=date(2026, 9, 7))

	def test_joint_completion_requires_all_assignees(self):
		self.task.assignment_mode = Task.AssignmentMode.JOINT
		self.task.save(update_fields=['assignment_mode'])
		Completion.objects.create(occurrence=self.occurrence, user=self.first_user)
		self.assertFalse(self.occurrence.is_complete)
		Completion.objects.create(occurrence=self.occurrence, user=self.second_user)
		self.assertTrue(self.occurrence.is_complete)

	def test_any_of_completion_requires_one_assignee(self):
		self.task.assignment_mode = Task.AssignmentMode.ANY_OF
		self.task.save(update_fields=['assignment_mode'])
		Completion.objects.create(occurrence=self.occurrence, user=self.first_user)
		self.assertTrue(self.occurrence.is_complete)

	def test_unassigned_user_cannot_complete(self):
		outsider = User.objects.create_user('outsider@example.com', 'password')
		with self.assertRaises(ValidationError):
			Completion(occurrence=self.occurrence, user=outsider).full_clean()

	def test_completion_action_is_idempotent_and_marks_occurrence(self):
		self.assertEqual(Completion.record(self.occurrence, self.first_user).pk, Completion.record(self.occurrence, self.first_user).pk)
		self.assertEqual(Completion.objects.filter(occurrence=self.occurrence, user=self.first_user).count(), 1)
		self.assertTrue(self.occurrence.is_complete)


class ProofAndApprovalTest(TestCase):
	def setUp(self):
		household = Household.objects.create(name='Approval Home')
		self.user = User.objects.create_user('proof-user@example.com', 'password')
		self.reviewer = User.objects.create_user('reviewer@example.com', 'password')
		for user in (self.user, self.reviewer):
			HouseholdMembership.objects.create(user=user, household=household)
		task = Task.objects.create(
			household=household, category=household.categories.get(name='Cleaning'),
			title='Proof task', type=Task.Type.CHORE,
		)
		TaskAssignment.objects.create(task=task, user=self.user)
		occurrence = TaskOccurrence.objects.create(task=task, scheduled_date=date(2026, 9, 7))
		self.completion = Completion.objects.create(occurrence=occurrence, user=self.user)

	def test_proof_requires_note_or_photo_and_approval_can_be_recorded(self):
		with self.assertRaises(ValidationError):
			CompletionProof(completion=self.completion).full_clean()
		proof = CompletionProof.objects.create(completion=self.completion, note='Done')
		self.assertEqual(proof.note, 'Done')
		approval = Approval.objects.create(completion=self.completion, reviewer=self.reviewer)
		approval.status = Approval.Status.APPROVED
		approval.save(update_fields=['status'])
		self.assertEqual(Approval.objects.get(pk=approval.pk).status, Approval.Status.APPROVED)


class NotificationPreferenceTest(TestCase):
	def test_preferences_have_defaults_and_can_be_updated(self):
		user = User.objects.create_user('notifications@example.com', 'password')
		preferences = NotificationPreference.objects.create(user=user)
		self.assertTrue(preferences.upcoming_due)
		preferences.overdue = False
		preferences.save(update_fields=['overdue'])
		self.assertFalse(NotificationPreference.objects.get(user=user).overdue)

	def test_notifications_respect_preferences_and_are_idempotent(self):
		user = User.objects.create_user('event@example.com', 'password')
		household = Household.objects.create(name='Event Home')
		task = Task.objects.create(household=household, category=household.categories.get(name='Cleaning'), title='Event task', type=Task.Type.CHORE)
		NotificationPreference.objects.create(user=user, assignments=False)
		self.assertIsNone(Notification.create_for_event(user, 'assignments', task, 'Assigned'))
		user.notification_preferences.assignments = True
		user.notification_preferences.save(update_fields=['assignments'])
		Notification.create_for_event(user, 'assignments', task, 'Assigned')
		Notification.create_for_event(user, 'assignments', task, 'Assigned again')
		self.assertEqual(Notification.objects.count(), 1)

	def test_workload_report_groups_completed_points_by_member(self):
		household = Household.objects.create(name='Workload Home')
		user = User.objects.create_user('workload@example.com', 'password')
		HouseholdMembership.objects.create(user=user, household=household)
		task = Task.objects.create(household=household, category=household.categories.get(name='Cleaning'), title='Weighted', type=Task.Type.CHORE, workload_points=4)
		TaskAssignment.objects.create(task=task, user=user)
		occurrence = TaskOccurrence.objects.create(task=task, scheduled_date=date(2026, 9, 7))
		Completion.objects.create(occurrence=occurrence, user=user)
		self.assertEqual(household_workload(household), {'workload@example.com': 4})


class DashboardTest(TestCase):
	def test_dashboard_is_household_scoped(self):
		household = Household.objects.create(name='Dashboard Home')
		user = User.objects.create_user('dashboard@example.com', 'password')
		HouseholdMembership.objects.create(user=user, household=household)
		task = Task.objects.create(
			household=household, category=household.categories.get(name='Cleaning'),
			title='Assigned dashboard task', type=Task.Type.CHORE, workload_points=3,
		)
		TaskAssignment.objects.create(task=task, user=user)
		self.client.force_login(user)
		response = self.client.get('/dashboard/')
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()['assigned'], ['Assigned dashboard task'])
		self.assertEqual(response.json()['workload_points'], 3)


class GamificationTest(TestCase):
	def test_points_are_optional(self):
		household = Household.objects.create(name='Game Home', gamification_enabled=False)
		user = User.objects.create_user('game@example.com', 'password')
		HouseholdMembership.objects.create(user=user, household=household)
		task = Task.objects.create(household=household, category=household.categories.get(name='Cleaning'), title='Points', type=Task.Type.CHORE, workload_points=5)
		TaskAssignment.objects.create(task=task, user=user)
		completion = Completion.objects.create(occurrence=TaskOccurrence.objects.create(task=task, scheduled_date=date(2026, 9, 7)), user=user)
		self.assertIsNone(PointsLedger.award_for_completion(completion))
		household.gamification_enabled = True
		household.save(update_fields=['gamification_enabled'])
		self.assertEqual(PointsLedger.award_for_completion(completion).points, 5)

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


class TaskAdministrationTest(TestCase):
	def setUp(self):
		self.user = User.objects.create_user('task-user@example.com', 'password')
		self.household = Household.objects.create(name='Task Admin Home')
		HouseholdMembership.objects.create(user=self.user, household=self.household)
		self.category = self.household.categories.get(name='Cleaning')
		self.client.force_login(self.user)

	def test_user_can_create_view_edit_and_delete_task(self):
		response = self.client.post('/tasks/', {
			'title': 'Wash dishes', 'description': 'After dinner',
			'type': Task.Type.CHORE, 'priority': Task.Priority.MEDIUM,
			'category': self.category.pk, 'workload_points': 2,
		})
		self.assertEqual(response.status_code, 201)
		task_id = response.json()['id']

		self.assertEqual(self.client.get(f'/tasks/{task_id}/').status_code, 200)
		response = self.client.post(f'/tasks/{task_id}/', {
			'title': 'Wash all dishes', 'type': Task.Type.CHORE,
			'priority': Task.Priority.HIGH, 'category': self.category.pk,
		})
		self.assertEqual(response.status_code, 200)
		self.assertEqual(Task.objects.get(pk=task_id).title, 'Wash all dishes')
		self.assertEqual(self.client.delete(f'/tasks/{task_id}/').status_code, 204)

	def test_invalid_data_returns_visible_errors(self):
		response = self.client.post('/tasks/', {'title': '', 'type': 'INVALID', 'priority': 'INVALID'})

		self.assertEqual(response.status_code, 400)
		self.assertIn('errors', response.json())

	def test_cross_household_task_is_hidden(self):
		other_household = Household.objects.create(name='Other Task Admin Home')
		other_category = other_household.categories.get(name='Cleaning')
		task = Task.objects.create(
			household=other_household, category=other_category,
			title='Private task', type=Task.Type.CHORE,
		)

		self.assertEqual(self.client.get(f'/tasks/{task.pk}/').status_code, 404)
		self.assertEqual(self.client.post(f'/tasks/{task.pk}/', {'title': 'Changed'}).status_code, 404)
		self.assertEqual(self.client.delete(f'/tasks/{task.pk}/').status_code, 404)
