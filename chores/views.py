from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from .forms import MemberCreateForm, MemberUpdateForm, TaskForm
from .models import Approval, ChecklistItem, Completion, CompletionProof, HouseholdMembership, NotificationPreference, Task, TaskOccurrence, User


def owner_required(view):
	@login_required
	def wrapped(request, *args, **kwargs):
		membership = getattr(request.user, 'household_membership', None)
		if not membership or membership.role != HouseholdMembership.Role.OWNER:
			return JsonResponse({'error': 'Owner/Admin access required.'}, status=403)
		return view(request, membership, *args, **kwargs)

	return wrapped


def household_required(view):
	@login_required
	def wrapped(request, *args, **kwargs):
		membership = getattr(request.user, 'household_membership', None)
		if not membership or not request.user.is_active:
			return JsonResponse({'error': 'Household membership required.'}, status=403)
		return view(request, membership, *args, **kwargs)

	return wrapped


@owner_required
@require_http_methods(['GET'])
def member_list(request, membership):
	members = User.objects.filter(household_membership__household=membership.household, is_active=True)
	return JsonResponse({'members': [user.email for user in members]})


@owner_required
@require_http_methods(['POST'])
def member_create(request, membership):
	form = MemberCreateForm(request.POST)
	if not form.is_valid():
		return JsonResponse({'errors': form.errors}, status=400)

	with transaction.atomic():
		user = User.objects.create_user(form.cleaned_data['email'], form.cleaned_data['password'])
		HouseholdMembership.objects.create(
			user=user,
			household=membership.household,
			role=form.cleaned_data['role'],
		)
	return JsonResponse({'email': user.email}, status=201)


@owner_required
@require_http_methods(['POST'])
def member_update(request, membership, user_id):
	user = get_object_or_404(User, pk=user_id, household_membership__household=membership.household)
	form = MemberUpdateForm(request.POST, instance=user)
	if not form.is_valid():
		return JsonResponse({'errors': form.errors}, status=400)
	form.save()
	return JsonResponse({'email': user.email, 'is_active': user.is_active})


@owner_required
@require_http_methods(['POST'])
def member_deactivate(request, membership, user_id):
	user = get_object_or_404(User, pk=user_id, household_membership__household=membership.household)
	user.is_active = False
	user.save(update_fields=['is_active'])
	return JsonResponse({'email': user.email, 'is_active': False})


@household_required
@require_http_methods(['GET', 'POST'])
def task_collection(request, membership):
	if request.method == 'GET':
		tasks = Task.objects.filter(household=membership.household).order_by('id')
		return JsonResponse({'tasks': [
			{'id': task.id, 'title': task.title, 'type': task.type, 'priority': task.priority}
			for task in tasks
		]})

	form = TaskForm(request.POST, household=membership.household)
	if not form.is_valid():
		return JsonResponse({'errors': form.errors}, status=400)
	task = form.save()
	return JsonResponse({'id': task.id, 'title': task.title}, status=201)


@household_required
@require_http_methods(['GET', 'POST', 'DELETE'])
def task_detail(request, membership, task_id):
	task = get_object_or_404(Task, pk=task_id, household=membership.household)
	if request.method == 'GET':
		return JsonResponse({
			'id': task.id,
			'title': task.title,
			'description': task.description,
			'type': task.type,
			'priority': task.priority,
			'category': task.category.name,
		})
	if request.method == 'DELETE':
		task.delete()
		return JsonResponse({}, status=204)

	form = TaskForm(request.POST, instance=task, household=membership.household)
	if not form.is_valid():
		return JsonResponse({'errors': form.errors}, status=400)
	task = form.save()
	return JsonResponse({'id': task.id, 'title': task.title})


@household_required
@require_http_methods(['POST'])
def task_claim(request, membership, task_id):
	task = get_object_or_404(Task, pk=task_id, household=membership.household)
	try:
		assignment = task.claim(request.user)
	except ValidationError as error:
		return JsonResponse({'error': error.message}, status=400)
	return JsonResponse({'task_id': task.pk, 'user': assignment.user.email}, status=201)


@household_required
@require_http_methods(['GET'])
def personal_dashboard(request, membership):
	from datetime import date
	from django.utils import timezone
	from .models import household_workload

	tasks = Task.objects.filter(household=membership.household, assignments__user=request.user).distinct()
	try:
		start = date.fromisoformat(request.GET['start']) if request.GET.get('start') else None
		end = date.fromisoformat(request.GET['end']) if request.GET.get('end') else None
	except ValueError:
		return JsonResponse({'error': 'Dates must use YYYY-MM-DD format.'}, status=400)
	due = tasks.filter(due_date=timezone.localdate())
	overdue = tasks.filter(due_date__lt=timezone.localdate())
	completed = tasks.filter(occurrences__completed_at__isnull=False).distinct()
	return JsonResponse({
		'assigned': list(tasks.values_list('title', flat=True)),
		'due': list(due.values_list('title', flat=True)),
		'overdue': list(overdue.values_list('title', flat=True)),
		'completed': list(completed.values_list('title', flat=True)),
		'workload_points': household_workload(membership.household, start, end).get(request.user.email, 0),
		'report_start': start.isoformat() if start else None,
		'report_end': end.isoformat() if end else None,
	})


@household_required
@require_http_methods(['GET'])
def household_board(request, membership):
	tasks = Task.objects.filter(household=membership.household).prefetch_related('assignments__user')
	status = request.GET.get('status')
	if status == 'unassigned':
		tasks = tasks.filter(assignments__isnull=True)
	elif status == 'claimable':
		tasks = tasks.filter(assignment_mode=Task.AssignmentMode.CLAIMABLE)
	elif status and status not in ('assigned',):
		return JsonResponse({'error': 'Unknown status filter.'}, status=400)
	for field in ('type', 'category', 'priority'):
		value = request.GET.get(field)
		if value:
			tasks = tasks.filter(**{field: value})
	tasks = list(tasks.distinct())
	groups = {'unassigned': [], 'claimable': []}
	for task in tasks:
		assignees = [assignment.user.email for assignment in task.assignments.all()]
		item = {
			'id': task.id,
			'title': task.title,
			'assignees': assignees,
			'claimable': task.assignment_mode == Task.AssignmentMode.CLAIMABLE,
		}
		if not assignees:
			groups['unassigned'].append(item)
		else:
			for assignee in assignees:
				groups.setdefault(assignee, []).append(item)
	return JsonResponse({'tasks': [item for items in groups.values() for item in items], 'groups': groups})


@household_required
@require_http_methods(['GET'])
def calendar_view(request, membership):
	tasks = Task.objects.filter(household=membership.household).exclude(due_date__isnull=True)
	events = [
		{'id': task.id, 'title': task.title, 'date': task.due_date.isoformat(), 'time': task.due_time.isoformat() if task.due_time else None}
		for task in tasks.order_by('due_date', 'due_time')
	]
	occurrences = TaskOccurrence.objects.filter(task__household=membership.household).select_related('task')
	events.extend({
		'id': occurrence.id,
		'title': occurrence.task.title,
		'date': occurrence.scheduled_date.isoformat(),
		'time': occurrence.task.due_time.isoformat() if occurrence.task.due_time else None,
		'overdue': occurrence.is_overdue,
	} for occurrence in occurrences)
	return JsonResponse({'events': events})


@household_required
@require_http_methods(['GET', 'POST'])
def checklist_collection(request, membership, task_id):
	task = get_object_or_404(Task, pk=task_id, household=membership.household)
	if request.method == 'POST':
		text = request.POST.get('text', '').strip()
		if not text:
			return JsonResponse({'error': 'Checklist text is required.'}, status=400)
		item = ChecklistItem.objects.create(
			task=task,
			text=text,
			position=int(request.POST.get('position', task.checklist_items.count())),
		)
		return JsonResponse({'id': item.pk, 'text': item.text, 'position': item.position}, status=201)
	return JsonResponse({'items': [
		{'id': item.pk, 'text': item.text, 'position': item.position, 'completed': item.completed}
		for item in task.checklist_items.all()
	]})


@household_required
@require_http_methods(['POST'])
def checklist_item_update(request, membership, task_id, item_id):
	item = get_object_or_404(ChecklistItem, pk=item_id, task_id=task_id, task__household=membership.household)
	if 'text' in request.POST:
		item.text = request.POST['text'].strip()
	if 'position' in request.POST:
		item.position = int(request.POST['position'])
	if 'completed' in request.POST:
		item.completed = request.POST['completed'].lower() in ('1', 'true', 'yes')
	item.save()
	return JsonResponse({'id': item.pk, 'text': item.text, 'position': item.position, 'completed': item.completed})


@household_required
@require_http_methods(['POST'])
def occurrence_complete(request, membership, occurrence_id):
	occurrence = get_object_or_404(TaskOccurrence, pk=occurrence_id, task__household=membership.household)
	try:
		completion = Completion(occurrence=occurrence, user=request.user)
		completion.full_clean()
		completion = Completion.record(occurrence, request.user)
	except ValidationError as error:
		return JsonResponse({'error': error.message_dict if hasattr(error, 'message_dict') else error.messages}, status=400)
	return JsonResponse({'id': completion.pk, 'completed': occurrence.is_complete}, status=201)


@household_required
@require_http_methods(['POST'])
def completion_proof(request, membership, completion_id):
	completion = get_object_or_404(Completion, pk=completion_id, occurrence__task__household=membership.household)
	if completion.user_id != request.user.pk:
		return JsonResponse({'error': 'Only the completing member can submit proof.'}, status=403)
	proof = CompletionProof(completion=completion, note=request.POST.get('note', ''), photo=request.POST.get('photo', ''))
	try:
		proof.full_clean()
		proof.save()
	except ValidationError as error:
		return JsonResponse({'errors': error.message_dict if hasattr(error, 'message_dict') else error.messages}, status=400)
	return JsonResponse({'id': proof.pk}, status=201)


@household_required
@require_http_methods(['POST'])
def completion_approval(request, membership, completion_id):
	completion = get_object_or_404(Completion, pk=completion_id, occurrence__task__household=membership.household)
	approval, _ = Approval.objects.get_or_create(completion=completion, defaults={'reviewer': request.user})
	approval.reviewer = request.user
	try:
		approval.full_clean()
	except ValidationError as error:
		return JsonResponse({'errors': error.message_dict}, status=403)
	status = request.POST.get('status', Approval.Status.PENDING)
	if status not in Approval.Status.values:
		return JsonResponse({'error': 'Invalid approval status.'}, status=400)
	approval.review(status)
	return JsonResponse({'status': approval.status, 'reviewed_at': approval.reviewed_at.isoformat()})


@household_required
@require_http_methods(['GET', 'POST'])
def notification_preferences(request, membership):
	preference, _ = NotificationPreference.objects.get_or_create(user=request.user)
	fields = (
		'upcoming_due', 'overdue', 'assignments', 'rotation_changes',
		'completions', 'approval_requests', 'approval_results',
	)
	if request.method == 'POST':
		unknown = set(request.POST) - set(fields)
		if unknown:
			return JsonResponse({'error': 'Unknown notification preference.'}, status=400)
		for field in fields:
			if field in request.POST:
				value = request.POST[field].lower()
				if value not in ('true', 'false', '1', '0'):
					return JsonResponse({'error': 'Preference values must be boolean.'}, status=400)
				setattr(preference, field, value in ('true', '1'))
		preference.save()
	return JsonResponse({field: getattr(preference, field) for field in fields})


@household_required
@require_http_methods(['GET'])
def workload_report(request, membership):
	from datetime import date
	from .models import household_workload
	try:
		start = date.fromisoformat(request.GET['start']) if request.GET.get('start') else None
		end = date.fromisoformat(request.GET['end']) if request.GET.get('end') else None
	except ValueError:
		return JsonResponse({'error': 'Dates must use YYYY-MM-DD format.'}, status=400)
	return JsonResponse({'workload': household_workload(membership.household, start, end)})
