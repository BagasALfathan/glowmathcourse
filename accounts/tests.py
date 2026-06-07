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


# ── Register wizard coverage ──────────────────────────────────────────────

# All register tests hit the real POST endpoints behind
# accounts.views.register_student_view and register_teacher_view, plus the
# _parse_register_payload validator. UI text is Bahasa Indonesia; messages
# rendered by the templates are also asserted in the response HTML.

STUDENT_BASE = {
    "email": "newstudent@example.com",
    "password": "StrongPass123!",
    "password2": "StrongPass123!",
    "full_name": "Andi Pratama",
    "phone": "081234567890",
    "date_of_birth": "2010-05-20",
    "gender": "MALE",
    "level": "SMA",
    "school_name": "SMA Negeri 1",
    "school_grade": "11",
    "parent_name": "Bapak Pratama",
    "parent_phone": "081234567899",
    "parent_email": "ortu@example.com",
}

TEACHER_BASE = {
    "email": "newteacher@example.com",
    "password": "StrongPass123!",
    "password2": "StrongPass123!",
    "full_name": "Bu Sari",
    "phone": "081234567000",
    "education": "S1",
    "specialization": "Matematika SMA",
    "experience_years": "5",
    "bio": "Pengajar SMA.",
    # jenjang_levels is a multi-value field; Django test client accepts list.
    "jenjang_levels": ["SMP", "SMA"],
}


class RegisterStudentTests(TestCase):
    def test_happy_path_creates_pending_user_redirects_to_waiting(self):
        resp = self.client.post(reverse("accounts:register"), STUDENT_BASE, follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp["Location"].endswith("/waiting/"))
        u = User.objects.get(email__iexact=STUDENT_BASE["email"])
        self.assertEqual(u.role, Role.STUDENT)
        self.assertEqual(u.approval_status, ApprovalStatus.PENDING)
        self.assertFalse(u.is_active)
        # Profile fields landed correctly
        sp = u.student_profile
        self.assertEqual(sp.level, "SMA")
        self.assertEqual(sp.school_name, "SMA Negeri 1")
        self.assertEqual(sp.school_grade, 11)
        self.assertEqual(sp.gender, "MALE")
        self.assertEqual(sp.parent_name, "Bapak Pratama")

    def test_duplicate_email_of_approved_user_rejected(self):
        # Pre-create an APPROVED user with the same email.
        existing = User.objects.create(
            username="taken_user", email=STUDENT_BASE["email"],
            role=Role.STUDENT, approval_status=ApprovalStatus.APPROVED, is_active=True,
        )
        existing.set_password("oldpass"); existing.save()
        before = User.objects.count()

        resp = self.client.post(reverse("accounts:register"), STUDENT_BASE, follow=False)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(User.objects.count(), before)
        body = resp.content.decode("utf-8", errors="replace")
        self.assertIn("Email sudah terdaftar.", body)

    def test_duplicate_email_of_pending_user_redirects_to_waiting(self):
        existing = User.objects.create(
            username="pending_user", email=STUDENT_BASE["email"],
            first_name="Pending", last_name="User",
            role=Role.STUDENT, approval_status=ApprovalStatus.PENDING, is_active=False,
        )
        before = User.objects.count()

        resp = self.client.post(reverse("accounts:register"), STUDENT_BASE, follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp["Location"].endswith("/waiting/"))
        # No second account created
        self.assertEqual(User.objects.count(), before)

    def test_rejected_email_errors_no_user_created(self):
        existing = User.objects.create(
            username="rej_user", email=STUDENT_BASE["email"],
            role=Role.STUDENT, approval_status=ApprovalStatus.REJECTED, is_active=False,
        )
        before = User.objects.count()
        resp = self.client.post(reverse("accounts:register"), STUDENT_BASE, follow=False)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(User.objects.count(), before)
        body = resp.content.decode("utf-8", errors="replace")
        self.assertIn("ditolak admin", body.lower())

    def test_password_mismatch_no_user_created(self):
        payload = dict(STUDENT_BASE, password2="DifferentPass456!")
        resp = self.client.post(reverse("accounts:register"), payload, follow=False)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            User.objects.filter(email__iexact=STUDENT_BASE["email"]).exists()
        )
        body = resp.content.decode("utf-8", errors="replace")
        self.assertIn("Konfirmasi kata sandi tidak cocok.", body)

    def test_weak_password_rejected_by_validate_password(self):
        payload = dict(STUDENT_BASE, password="weak", password2="weak")
        resp = self.client.post(reverse("accounts:register"), payload, follow=False)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            User.objects.filter(email__iexact=STUDENT_BASE["email"]).exists()
        )
        body = resp.content.decode("utf-8", errors="replace")
        # validate_password yields an Indonesian-translated set of reasons; the
        # joined message reliably mentions "too short" or "pendek" or
        # "minimal" depending on the locale. We only assert SOME error message
        # describing the weak password landed in the page.
        self.assertTrue(
            any(w in body.lower() for w in (
                "terlalu pendek", "minimal", "umum", "kata sandi",
            )),
            f'Expected weak-password error text in body, got: {body[:400]}',
        )


class RegisterTeacherTests(TestCase):
    def test_happy_path_creates_pending_user_with_teacher_jenjang(self):
        resp = self.client.post(
            reverse("accounts:register_teacher"), TEACHER_BASE, follow=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp["Location"].endswith("/waiting/"))
        u = User.objects.get(email__iexact=TEACHER_BASE["email"])
        self.assertEqual(u.role, Role.TEACHER)
        self.assertEqual(u.approval_status, ApprovalStatus.PENDING)
        self.assertFalse(u.is_active)
        # TeacherJenjang rows from the ticked levels
        from accounts.models import TeacherJenjang
        levels = set(
            TeacherJenjang.objects
            .filter(teacher_profile=u.teacher_profile)
            .values_list("level", flat=True)
        )
        self.assertEqual(levels, {"SMP", "SMA"})
        # Profile basics
        tp = u.teacher_profile
        self.assertEqual(tp.education, "S1")
        self.assertEqual(tp.specialization, "Matematika SMA")
        self.assertEqual(tp.experience_years, 5)

    def test_missing_jenjang_rejected_no_user_created(self):
        payload = dict(TEACHER_BASE)
        payload.pop("jenjang_levels")
        before = User.objects.count()
        resp = self.client.post(
            reverse("accounts:register_teacher"), payload, follow=False,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(User.objects.count(), before)
        body = resp.content.decode("utf-8", errors="replace")
        self.assertIn("Pilih minimal satu jenjang", body)
