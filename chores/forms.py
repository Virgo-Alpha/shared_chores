from django import forms

from .models import Category, HouseholdMembership, Task, User


class MemberCreateForm(forms.Form):
	email = forms.EmailField()
	password = forms.CharField(min_length=8, widget=forms.PasswordInput)
	role = forms.ChoiceField(choices=HouseholdMembership.Role.choices)

	def clean_email(self):
		return User.objects.normalize_email(self.cleaned_data['email'])


class MemberUpdateForm(forms.ModelForm):
	class Meta:
		model = User
		fields = ('email', 'is_active')


class TaskForm(forms.ModelForm):
	class Meta:
		model = Task
		fields = (
			'title', 'description', 'type', 'priority', 'estimated_effort',
			'workload_points', 'category', 'due_date', 'due_time',
		)

	def __init__(self, *args, household, **kwargs):
		super().__init__(*args, **kwargs)
		self.household = household
		self.fields['category'].queryset = Category.objects.filter(household=household)
		self.fields['estimated_effort'].required = False
		self.fields['workload_points'].required = False
		self.fields['due_date'].required = False
		self.fields['due_time'].required = False

	def save(self, commit=True):
		self.instance.household = self.household
		return super().save(commit=commit)