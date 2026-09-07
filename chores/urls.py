from django.urls import path

from . import views

urlpatterns = [
	path('members/', views.member_list, name='member-list'),
	path('members/create/', views.member_create, name='member-create'),
	path('members/<int:user_id>/update/', views.member_update, name='member-update'),
	path('members/<int:user_id>/deactivate/', views.member_deactivate, name='member-deactivate'),
]