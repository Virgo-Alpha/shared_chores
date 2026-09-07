from django.test import TestCase


class ProjectSmokeTest(TestCase):
	def test_admin_url_loads(self):
		response = self.client.get('/admin/')

		self.assertEqual(response.status_code, 302)
