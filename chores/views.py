from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from .forms import MemberCreateForm, MemberUpdateForm
from .models import HouseholdMembership, User


def owner_required(view):
	@login_required
	def wrapped(request, *args, **kwargs):
		membership = getattr(request.user, 'household_membership', None)
		if not membership or membership.role != HouseholdMembership.Role.OWNER:
			return JsonResponse({'error': 'Owner/Admin access required.'}, status=403)
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
