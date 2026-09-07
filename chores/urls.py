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
	path('tasks/<int:task_id>/checklist/', views.checklist_collection, name='checklist-collection'),
	path('tasks/<int:task_id>/checklist/<int:item_id>/', views.checklist_item_update, name='checklist-item-update'),
	path('occurrences/<int:occurrence_id>/complete/', views.occurrence_complete, name='occurrence-complete'),
	path('completions/<int:completion_id>/proof/', views.completion_proof, name='completion-proof'),
	path('completions/<int:completion_id>/approval/', views.completion_approval, name='completion-approval'),
]