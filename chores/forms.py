from django import forms

from .models import HouseholdMembership, User


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