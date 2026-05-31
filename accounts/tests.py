"""Smoke tests — approval gate at the login portals.

Covers business behavior in accounts.views._do_role_login:
  * APPROVED  student -> logged in, redirected to dashboard
  * PENDING   student -> redirected to /waiting/ (not the dashboard)
  * REJECTED  student -> login refused, stays anonymous
  * wrong password    -> login refused
  * wrong portal      -> role mismatch refused

Run:  python manage.py test accounts
"""
from django.test import TestCase
from django.urls import reverse

from accounts.models import User, Role, ApprovalStatus

PWD = "pass12345"


class LoginApprovalGateTests(TestCase):
    def setUp(self):
        self.login_url = reverse("accounts:login")  # student portal = "/"
        self.approved = self._student("appr", ApprovalStatus.APPROVED)
        self.pending = self._student("pend", ApprovalStatus.PENDING)
        self.rejected = self._student("rej", ApprovalStatus.REJECTED)

    def _student(self, slug, status):
        u = User(
            username=f"{slug}_student",
            email=f"{slug}@example.com",
            role=Role.STUDENT,
            approval_status=status,
            is_active=True,
        )
        u.set_password(PWD)
        u.save()  # signal auto-creates StudentProfile
        return u

    def _logged_in(self):
        return "_auth_user_id" in self.client.session

    def test_approved_student_logs_in_and_reaches_dashboard(self):
        resp = self.client.post(
            self.login_url, {"username": "appr_student", "password": PWD}
        )
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("/waiting/", resp.url)
        self.assertTrue(self._logged_in())

    def test_pending_student_redirected_to_waiting(self):
        resp = self.client.post(
            self.login_url, {"username": "pend_student", "password": PWD}
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("accounts:waiting"))

    def test_rejected_student_cannot_log_in(self):
        resp = self.client.post(
            self.login_url, {"username": "rej_student", "password": PWD}
        )
        self.assertEqual(resp.status_code, 200)  # re-renders form with error
        self.assertFalse(self._logged_in())

    def test_wrong_password_refused(self):
        resp = self.client.post(
            self.login_url, {"username": "appr_student", "password": "nope"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(self._logged_in())

    def test_wrong_portal_role_mismatch_refused(self):
        # Approved STUDENT trying to use the TEACHER portal.
        resp = self.client.post(
            reverse("accounts:login_teacher"),
            {"username": "appr_student", "password": PWD},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(self._logged_in())


class ProfileSignalTests(TestCase):
    def test_student_profile_autocreated(self):
        u = User.objects.create(username="sig1", role=Role.STUDENT)
        self.assertTrue(hasattr(u, "student_profile"))

    def test_teacher_profile_autocreated(self):
        u = User.objects.create(username="sig2", role=Role.TEACHER)
        self.assertTrue(hasattr(u, "teacher_profile"))
