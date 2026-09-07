from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from .forms import MemberCreateForm, MemberUpdateForm, TaskForm
from .models import Approval, ChecklistItem, Completion, CompletionProof, HouseholdMembership, Task, TaskOccurrence, User


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
	from django.utils import timezone

	tasks = Task.objects.filter(household=membership.household, assignments__user=request.user).distinct()
	due = tasks.filter(due_date=timezone.localdate())
	overdue = tasks.filter(due_date__lt=timezone.localdate())
	completed = tasks.filter(occurrences__completed_at__isnull=False).distinct()
	return JsonResponse({
		'assigned': list(tasks.values_list('title', flat=True)),
		'due': list(due.values_list('title', flat=True)),
		'overdue': list(overdue.values_list('title', flat=True)),
		'completed': list(completed.values_list('title', flat=True)),
		'workload_points': sum(tasks.values_list('workload_points', flat=True)),
	})


@household_required
@require_http_methods(['GET'])
def household_board(request, membership):
	tasks = Task.objects.filter(household=membership.household).prefetch_related('assignments__user')
	filters = ('status', 'type', 'category', 'priority')
	for field in filters:
		value = request.GET.get(field)
		if value:
			if field == 'status' and value == 'unassigned':
				tasks = tasks.filter(assignments__isnull=True)
			else:
				tasks = tasks.filter(**{field: value})
	return JsonResponse({'tasks': [
		{'id': task.id, 'title': task.title, 'assignees': [a.user.email for a in task.assignments.all()]}
		for task in tasks.distinct()
	]})


@household_required
@require_http_methods(['GET'])
def calendar_view(request, membership):
	tasks = Task.objects.filter(household=membership.household).exclude(due_date__isnull=True)
	return JsonResponse({'events': [
		{'id': task.id, 'title': task.title, 'date': task.due_date.isoformat(), 'time': task.due_time.isoformat() if task.due_time else None}
		for task in tasks.order_by('due_date', 'due_time')
	]})


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
