from django.urls import path

from . import views

urlpatterns = [
	path('members/', views.member_list, name='member-list'),
	path('members/create/', views.member_create, name='member-create'),
	path('members/<int:user_id>/update/', views.member_update, name='member-update'),
	path('members/<int:user_id>/deactivate/', views.member_deactivate, name='member-deactivate'),
	path('tasks/', views.task_collection, name='task-collection'),
	path('tasks/<int:task_id>/', views.task_detail, name='task-detail'),
	path('tasks/<int:task_id>/claim/', views.task_claim, name='task-claim'),
	path('dashboard/', views.personal_dashboard, name='personal-dashboard'),
	path('board/', views.household_board, name='household-board'),
	path('calendar/', views.calendar_view, name='calendar'),
]