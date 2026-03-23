from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .forms import AdvanceForm, ExpenseItemForm
from .models import ExpenseReport


User = get_user_model()


class ExpenseWorkflowTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='pass1234')
        self.approver = User.objects.create_user(
            username='approver',
            password='pass1234',
            is_staff=True,
        )

        self.report = ExpenseReport.objects.create(
            title='Site Visit',
            submitted_by=self.owner,
            status='draft',
        )

    def test_owner_can_submit_draft_statement(self):
        self.client.login(username='owner', password='pass1234')

        response = self.client.post(reverse('expenses:submit_report', args=[self.report.id]))

        self.assertEqual(response.status_code, 302)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, 'submitted')

    def test_non_owner_cannot_submit_statement(self):
        self.client.login(username='approver', password='pass1234')

        response = self.client.post(reverse('expenses:submit_report', args=[self.report.id]))

        self.assertEqual(response.status_code, 404)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, 'draft')

    def test_staff_can_approve_submitted_statement(self):
        self.report.status = 'submitted'
        self.report.save(update_fields=['status'])

        self.client.login(username='approver', password='pass1234')
        response = self.client.post(reverse('expenses:approve_report', args=[self.report.id]))

        self.assertEqual(response.status_code, 302)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, 'approved')

    def test_non_approver_cannot_approve_statement(self):
        self.report.status = 'submitted'
        self.report.save(update_fields=['status'])

        self.client.login(username='owner', password='pass1234')
        response = self.client.post(reverse('expenses:approve_report', args=[self.report.id]))

        self.assertEqual(response.status_code, 302)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, 'submitted')


class DraftSelectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='user1', password='pass1234')
        self.other_user = User.objects.create_user(username='user2', password='pass1234')

        self.draft_report = ExpenseReport.objects.create(
            title='Draft Statement',
            submitted_by=self.user,
            status='draft',
        )
        self.approved_report = ExpenseReport.objects.create(
            title='Approved Statement',
            submitted_by=self.user,
            status='approved',
        )
        self.other_users_draft = ExpenseReport.objects.create(
            title='Other User Draft',
            submitted_by=self.other_user,
            status='draft',
        )

    def test_expense_form_report_queryset_only_own_draft(self):
        form = ExpenseItemForm(user=self.user)
        report_ids = set(form.fields['report'].queryset.values_list('id', flat=True))

        self.assertIn(self.draft_report.id, report_ids)
        self.assertNotIn(self.approved_report.id, report_ids)
        self.assertNotIn(self.other_users_draft.id, report_ids)

    def test_advance_form_report_queryset_only_own_draft(self):
        form = AdvanceForm(user=self.user)
        report_ids = set(form.fields['report'].queryset.values_list('id', flat=True))

        self.assertIn(self.draft_report.id, report_ids)
        self.assertNotIn(self.approved_report.id, report_ids)
        self.assertNotIn(self.other_users_draft.id, report_ids)
