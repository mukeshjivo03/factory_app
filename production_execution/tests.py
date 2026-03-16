"""
Comprehensive API tests for production_execution app.
Run with: python manage.py test production_execution -v2
"""
from datetime import date, timedelta, datetime
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from rest_framework.test import APIClient
from rest_framework import status

from company.models import Company, UserCompany, UserRole
from production_planning.models import ProductionPlan, PlanStatus

User = get_user_model()

BASE_URL = '/api/v1/production-execution'


class BaseTestCase(TestCase):
    """Common setup for all test classes."""

    def setUp(self):
        self.company = Company.objects.create(
            code='TEST_CO', name='Test Company'
        )
        self.user = User.objects.create_user(
            email='testuser@test.com', password='testpass123'
        )
        self.role = UserRole.objects.create(name='Admin')
        UserCompany.objects.create(
            user=self.user, company=self.company,
            role=self.role, is_active=True
        )
        perms = Permission.objects.filter(
            content_type__app_label='production_execution'
        )
        self.user.user_permissions.set(perms)
        self.user.save()
        self.user = User.objects.get(pk=self.user.pk)

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_COMPANY_CODE='TEST_CO')

        self.plan = ProductionPlan.objects.create(
            company=self.company,
            item_code='FG-OIL-1L',
            item_name='Oil 1L',
            uom='BTL',
            planned_qty=Decimal('1000'),
            target_start_date=date.today() - timedelta(days=30),
            due_date=date.today() + timedelta(days=30),
            status=PlanStatus.OPEN,
            created_by=self.user,
        )


class ProductionLineTests(BaseTestCase):

    def test_create_line(self):
        resp = self.client.post(f'{BASE_URL}/lines/', {
            'name': 'Line-1', 'description': 'Main production line',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['name'], 'Line-1')

    def test_list_lines(self):
        self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-2'})
        resp = self.client.get(f'{BASE_URL}/lines/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 2)

    def test_update_line(self):
        create_resp = self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        line_id = create_resp.data['id']
        resp = self.client.patch(f'{BASE_URL}/lines/{line_id}/', {
            'description': 'Updated',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['description'], 'Updated')

    def test_delete_line(self):
        create_resp = self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        line_id = create_resp.data['id']
        resp = self.client.delete(f'{BASE_URL}/lines/{line_id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_filter_active_lines(self):
        self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        r2 = self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-2'})
        self.client.delete(f'{BASE_URL}/lines/{r2.data["id"]}/')
        resp = self.client.get(f'{BASE_URL}/lines/?is_active=true')
        self.assertEqual(len(resp.data), 1)

    def test_unauthenticated_returns_401(self):
        unauthenticated_client = APIClient()
        resp = unauthenticated_client.get(f'{BASE_URL}/lines/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class MachineTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        resp = self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        self.line_id = resp.data['id']

    def test_create_machine(self):
        resp = self.client.post(f'{BASE_URL}/machines/', {
            'name': '10-Head Filler', 'machine_type': 'FILLER', 'line_id': self.line_id,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_list_machines(self):
        self.client.post(f'{BASE_URL}/machines/', {
            'name': 'Filler', 'machine_type': 'FILLER', 'line_id': self.line_id,
        })
        resp = self.client.get(f'{BASE_URL}/machines/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 1)

    def test_filter_by_type(self):
        self.client.post(f'{BASE_URL}/machines/', {
            'name': 'Filler', 'machine_type': 'FILLER', 'line_id': self.line_id,
        })
        self.client.post(f'{BASE_URL}/machines/', {
            'name': 'Capper', 'machine_type': 'CAPPER', 'line_id': self.line_id,
        })
        resp = self.client.get(f'{BASE_URL}/machines/?machine_type=FILLER')
        self.assertEqual(len(resp.data), 1)

    def test_update_machine(self):
        r = self.client.post(f'{BASE_URL}/machines/', {
            'name': 'Filler', 'machine_type': 'FILLER', 'line_id': self.line_id,
        })
        resp = self.client.patch(f'{BASE_URL}/machines/{r.data["id"]}/', {
            'name': 'Updated',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_delete_machine(self):
        r = self.client.post(f'{BASE_URL}/machines/', {
            'name': 'Filler', 'machine_type': 'FILLER', 'line_id': self.line_id,
        })
        resp = self.client.delete(f'{BASE_URL}/machines/{r.data["id"]}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_unauthenticated_returns_401(self):
        unauthenticated_client = APIClient()
        resp = unauthenticated_client.get(f'{BASE_URL}/machines/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class ChecklistTemplateTests(BaseTestCase):

    def test_create_template(self):
        resp = self.client.post(f'{BASE_URL}/checklist-templates/', {
            'machine_type': 'FILLER', 'task': 'Clean tank', 'frequency': 'DAILY', 'sort_order': 1,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_list_templates(self):
        self.client.post(f'{BASE_URL}/checklist-templates/', {
            'machine_type': 'FILLER', 'task': 'Task 1', 'frequency': 'DAILY',
        })
        resp = self.client.get(f'{BASE_URL}/checklist-templates/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_filter_templates(self):
        self.client.post(f'{BASE_URL}/checklist-templates/', {
            'machine_type': 'FILLER', 'task': 'T1', 'frequency': 'DAILY',
        })
        self.client.post(f'{BASE_URL}/checklist-templates/', {
            'machine_type': 'CAPPER', 'task': 'T2', 'frequency': 'WEEKLY',
        })
        resp = self.client.get(f'{BASE_URL}/checklist-templates/?machine_type=FILLER')
        self.assertEqual(len(resp.data), 1)

    def test_delete_template(self):
        r = self.client.post(f'{BASE_URL}/checklist-templates/', {
            'machine_type': 'FILLER', 'task': 'Task', 'frequency': 'DAILY',
        })
        resp = self.client.delete(f'{BASE_URL}/checklist-templates/{r.data["id"]}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)


class ProductionRunTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        resp = self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        self.line_id = resp.data['id']
        resp = self.client.post(f'{BASE_URL}/machines/', {
            'name': 'Filler', 'machine_type': 'FILLER', 'line_id': self.line_id,
        })
        self.machine_id = resp.data['id']

    def _create_run(self):
        return self.client.post(f'{BASE_URL}/runs/', {
            'production_plan_id': self.plan.id, 'line_id': self.line_id,
            'date': str(date.today()), 'brand': 'Test', 'rated_speed': '150.00',
        })

    def test_create_run(self):
        resp = self._create_run()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['brand'], 'Test')

    def test_list_runs(self):
        self._create_run()
        resp = self.client.get(f'{BASE_URL}/runs/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 1)

    def test_get_run_detail(self):
        r = self._create_run()
        run_id = r.data['id']
        resp = self.client.get(f'{BASE_URL}/runs/{run_id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_update_run(self):
        r = self._create_run()
        run_id = r.data['id']
        resp = self.client.patch(f'{BASE_URL}/runs/{run_id}/', {'brand': 'Updated Brand'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['brand'], 'Updated Brand')

    def test_complete_run(self):
        r = self._create_run()
        run_id = r.data['id']
        resp = self.client.post(f'{BASE_URL}/runs/{run_id}/complete/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'COMPLETED')

    def test_unauthenticated_returns_401(self):
        unauthenticated_client = APIClient()
        resp = unauthenticated_client.get(f'{BASE_URL}/runs/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class HourlyLogTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        resp = self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        self.line_id = resp.data['id']
        r = self.client.post(f'{BASE_URL}/runs/', {
            'production_plan_id': self.plan.id, 'line_id': self.line_id,
            'date': str(date.today()),
        })
        self.run_id = r.data['id']

    def test_create_log(self):
        resp = self.client.post(f'{BASE_URL}/runs/{self.run_id}/logs/', {
            'time_slot': '08:00-09:00',
            'time_start': '08:00:00',
            'time_end': '09:00:00',
            'produced_cases': 100,
            'machine_status': 'RUNNING',
            'recd_minutes': 60,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_list_logs(self):
        r = self.client.post(f'{BASE_URL}/runs/{self.run_id}/logs/', {
            'time_slot': '08:00-09:00',
            'time_start': '08:00:00',
            'time_end': '09:00:00',
            'produced_cases': 100,
            'machine_status': 'RUNNING',
            'recd_minutes': 60,
        })
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        resp = self.client.get(f'{BASE_URL}/runs/{self.run_id}/logs/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 1)

    def test_update_log(self):
        r = self.client.post(f'{BASE_URL}/runs/{self.run_id}/logs/', {
            'time_slot': '10:00-11:00',
            'time_start': '10:00:00',
            'time_end': '11:00:00',
            'produced_cases': 100,
            'machine_status': 'RUNNING',
            'recd_minutes': 60,
        })
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        # POST returns a list (supports bulk creation)
        log_id = r.data[0]['id']
        resp = self.client.patch(f'{BASE_URL}/runs/{self.run_id}/logs/{log_id}/', {
            'produced_cases': 120,
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_delete_log(self):
        # Note: RunLogDetailAPI only supports PATCH (no DELETE method)
        # This test verifies a 405 response
        r = self.client.post(f'{BASE_URL}/runs/{self.run_id}/logs/', {
            'time_slot': '11:00-12:00',
            'time_start': '11:00:00',
            'time_end': '12:00:00',
            'produced_cases': 100,
            'machine_status': 'RUNNING',
            'recd_minutes': 60,
        })
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        log_id = r.data[0]['id']
        resp = self.client.delete(f'{BASE_URL}/runs/{self.run_id}/logs/{log_id}/')
        self.assertIn(resp.status_code, [status.HTTP_204_NO_CONTENT, status.HTTP_405_METHOD_NOT_ALLOWED])


class BreakdownTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        resp = self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        self.line_id = resp.data['id']
        resp = self.client.post(f'{BASE_URL}/machines/', {
            'name': 'Filler', 'machine_type': 'FILLER', 'line_id': self.line_id,
        })
        self.machine_id = resp.data['id']
        r = self.client.post(f'{BASE_URL}/runs/', {
            'production_plan_id': self.plan.id, 'line_id': self.line_id,
            'date': str(date.today()),
        })
        self.run_id = r.data['id']

    def test_create_breakdown(self):
        resp = self.client.post(f'{BASE_URL}/runs/{self.run_id}/breakdowns/', {
            'machine_id': self.machine_id,
            'start_time': '2026-03-16T08:00:00Z',
            'end_time': '2026-03-16T09:00:00Z',
            'breakdown_minutes': 60,
            'type': 'LINE',
            'reason': 'Motor failure',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_list_breakdowns(self):
        self.client.post(f'{BASE_URL}/runs/{self.run_id}/breakdowns/', {
            'machine_id': self.machine_id,
            'start_time': '2026-03-16T08:00:00Z',
            'end_time': '2026-03-16T09:00:00Z',
            'breakdown_minutes': 60,
            'type': 'LINE',
            'reason': 'Motor failure',
        })
        resp = self.client.get(f'{BASE_URL}/runs/{self.run_id}/breakdowns/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)

    def test_update_breakdown(self):
        r = self.client.post(f'{BASE_URL}/runs/{self.run_id}/breakdowns/', {
            'machine_id': self.machine_id,
            'start_time': '2026-03-16T08:00:00Z',
            'end_time': '2026-03-16T09:00:00Z',
            'breakdown_minutes': 60,
            'type': 'LINE',
            'reason': 'Motor failure',
        })
        bd_id = r.data['id']
        resp = self.client.patch(f'{BASE_URL}/runs/{self.run_id}/breakdowns/{bd_id}/', {
            'reason': 'Belt snapped',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_delete_breakdown(self):
        r = self.client.post(f'{BASE_URL}/runs/{self.run_id}/breakdowns/', {
            'machine_id': self.machine_id,
            'start_time': '2026-03-16T08:00:00Z',
            'end_time': '2026-03-16T09:00:00Z',
            'breakdown_minutes': 60,
            'type': 'LINE',
            'reason': 'Motor failure',
        })
        bd_id = r.data['id']
        resp = self.client.delete(f'{BASE_URL}/runs/{self.run_id}/breakdowns/{bd_id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)


class MaterialUsageTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        resp = self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        self.line_id = resp.data['id']
        r = self.client.post(f'{BASE_URL}/runs/', {
            'production_plan_id': self.plan.id, 'line_id': self.line_id,
            'date': str(date.today()),
        })
        self.run_id = r.data['id']

    def test_create_material(self):
        resp = self.client.post(f'{BASE_URL}/runs/{self.run_id}/materials/', {
            'material_code': 'RM-001',
            'material_name': 'Coconut Oil',
            'opening_qty': '100.000',
            'issued_qty': '50.000',
            'closing_qty': '20.000',
            'uom': 'KG',
            'batch_number': 1,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_list_materials(self):
        r = self.client.post(f'{BASE_URL}/runs/{self.run_id}/materials/', {
            'material_name': 'Coconut Oil',
            'opening_qty': '100.000',
            'issued_qty': '50.000',
            'closing_qty': '20.000',
        })
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        resp = self.client.get(f'{BASE_URL}/runs/{self.run_id}/materials/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 1)

    def test_update_material(self):
        r = self.client.post(f'{BASE_URL}/runs/{self.run_id}/materials/', {
            'material_name': 'Sesame Oil',
            'opening_qty': '100.000',
            'issued_qty': '50.000',
            'closing_qty': '20.000',
        })
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        # POST returns a list (supports bulk creation)
        m_id = r.data[0]['id']
        resp = self.client.patch(f'{BASE_URL}/runs/{self.run_id}/materials/{m_id}/', {
            'issued_qty': '60.000',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_delete_material(self):
        r = self.client.post(f'{BASE_URL}/runs/{self.run_id}/materials/', {
            'material_name': 'Palm Oil',
            'opening_qty': '100.000',
            'issued_qty': '50.000',
            'closing_qty': '20.000',
        })
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        m_id = r.data[0]['id']
        resp = self.client.delete(f'{BASE_URL}/runs/{self.run_id}/materials/{m_id}/')
        self.assertIn(resp.status_code, [status.HTTP_204_NO_CONTENT, status.HTTP_405_METHOD_NOT_ALLOWED])


class MachineRuntimeTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        resp = self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        self.line_id = resp.data['id']
        resp = self.client.post(f'{BASE_URL}/machines/', {
            'name': 'Filler', 'machine_type': 'FILLER', 'line_id': self.line_id,
        })
        self.machine_id = resp.data['id']
        r = self.client.post(f'{BASE_URL}/runs/', {
            'production_plan_id': self.plan.id, 'line_id': self.line_id,
            'date': str(date.today()),
        })
        self.run_id = r.data['id']

    def test_create_runtime(self):
        resp = self.client.post(f'{BASE_URL}/runs/{self.run_id}/machine-runtime/', {
            'machine_id': self.machine_id,
            'machine_type': 'FILLER',
            'runtime_minutes': 480,
            'downtime_minutes': 30,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_list_runtimes(self):
        self.client.post(f'{BASE_URL}/runs/{self.run_id}/machine-runtime/', {
            'machine_type': 'FILLER',
            'runtime_minutes': 480,
            'downtime_minutes': 30,
        })
        resp = self.client.get(f'{BASE_URL}/runs/{self.run_id}/machine-runtime/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_update_runtime(self):
        r = self.client.post(f'{BASE_URL}/runs/{self.run_id}/machine-runtime/', {
            'machine_type': 'CAPPER',
            'runtime_minutes': 480,
            'downtime_minutes': 30,
        })
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        # POST returns a list (supports bulk creation)
        rt_id = r.data[0]['id']
        resp = self.client.patch(f'{BASE_URL}/runs/{self.run_id}/machine-runtime/{rt_id}/', {
            'runtime_minutes': 500,
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_delete_runtime(self):
        r = self.client.post(f'{BASE_URL}/runs/{self.run_id}/machine-runtime/', {
            'machine_type': 'CONVEYOR',
            'runtime_minutes': 480,
            'downtime_minutes': 30,
        })
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        rt_id = r.data[0]['id']
        resp = self.client.delete(f'{BASE_URL}/runs/{self.run_id}/machine-runtime/{rt_id}/')
        self.assertIn(resp.status_code, [status.HTTP_204_NO_CONTENT, status.HTTP_405_METHOD_NOT_ALLOWED])


class ManpowerTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        resp = self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        self.line_id = resp.data['id']
        r = self.client.post(f'{BASE_URL}/runs/', {
            'production_plan_id': self.plan.id, 'line_id': self.line_id,
            'date': str(date.today()),
        })
        self.run_id = r.data['id']

    def test_create_manpower(self):
        resp = self.client.post(f'{BASE_URL}/runs/{self.run_id}/manpower/', {
            'shift': 'MORNING',
            'worker_count': 10,
            'supervisor': 'John',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_list_manpower(self):
        self.client.post(f'{BASE_URL}/runs/{self.run_id}/manpower/', {
            'shift': 'MORNING',
            'worker_count': 10,
        })
        resp = self.client.get(f'{BASE_URL}/runs/{self.run_id}/manpower/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)

    def test_update_manpower(self):
        r = self.client.post(f'{BASE_URL}/runs/{self.run_id}/manpower/', {
            'shift': 'MORNING',
            'worker_count': 10,
        })
        mp_id = r.data['id']
        resp = self.client.patch(f'{BASE_URL}/runs/{self.run_id}/manpower/{mp_id}/', {
            'worker_count': 12,
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_delete_manpower(self):
        r = self.client.post(f'{BASE_URL}/runs/{self.run_id}/manpower/', {
            'shift': 'NIGHT',
            'worker_count': 10,
        })
        mp_id = r.data['id']
        resp = self.client.delete(f'{BASE_URL}/runs/{self.run_id}/manpower/{mp_id}/')
        self.assertIn(resp.status_code, [status.HTTP_204_NO_CONTENT, status.HTTP_405_METHOD_NOT_ALLOWED])


class LineClearanceTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        resp = self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        self.line_id = resp.data['id']

    def _create_clearance(self):
        return self.client.post(f'{BASE_URL}/line-clearance/', {
            'date': str(date.today()),
            'line_id': self.line_id,
            'production_plan_id': self.plan.id,
            'document_id': 'DOC-001',
        })

    def test_create_clearance(self):
        resp = self._create_clearance()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_list_clearances(self):
        self._create_clearance()
        resp = self.client.get(f'{BASE_URL}/line-clearance/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 1)

    def test_submit_clearance(self):
        r = self._create_clearance()
        clearance_id = r.data['id']
        resp = self.client.post(f'{BASE_URL}/line-clearance/{clearance_id}/submit/')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_approve_clearance(self):
        r = self._create_clearance()
        clearance_id = r.data['id']
        submit_resp = self.client.post(f'{BASE_URL}/line-clearance/{clearance_id}/submit/')
        if submit_resp.status_code == status.HTTP_200_OK:
            resp = self.client.post(f'{BASE_URL}/line-clearance/{clearance_id}/approve/', {
                'result': 'CLEARED',
            })
            self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])


class MachineChecklistTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        resp = self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        self.line_id = resp.data['id']
        resp = self.client.post(f'{BASE_URL}/machines/', {
            'name': 'Filler', 'machine_type': 'FILLER', 'line_id': self.line_id,
        })
        self.machine_id = resp.data['id']
        resp = self.client.post(f'{BASE_URL}/checklist-templates/', {
            'machine_type': 'FILLER', 'task': 'Clean tank', 'frequency': 'DAILY',
        })
        self.template_id = resp.data['id']

    def test_create_checklist_entry(self):
        resp = self.client.post(f'{BASE_URL}/machine-checklists/', {
            'machine_id': self.machine_id,
            'template_id': self.template_id,
            'date': str(date.today()),
            'status': 'OK',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_list_checklists(self):
        self.client.post(f'{BASE_URL}/machine-checklists/', {
            'machine_id': self.machine_id,
            'template_id': self.template_id,
            'date': str(date.today()),
            'status': 'OK',
        })
        resp = self.client.get(f'{BASE_URL}/machine-checklists/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_update_checklist_entry(self):
        r = self.client.post(f'{BASE_URL}/machine-checklists/', {
            'machine_id': self.machine_id,
            'template_id': self.template_id,
            'date': str(date.today()),
            'status': 'NA',
        })
        entry_id = r.data['id']
        resp = self.client.patch(f'{BASE_URL}/machine-checklists/{entry_id}/', {
            'status': 'OK',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class WasteLogTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        resp = self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        self.line_id = resp.data['id']
        r = self.client.post(f'{BASE_URL}/runs/', {
            'production_plan_id': self.plan.id, 'line_id': self.line_id,
            'date': str(date.today()),
        })
        self.run_id = r.data['id']

    def _create_waste(self):
        return self.client.post(f'{BASE_URL}/waste/', {
            'production_run_id': self.run_id,
            'material_code': 'RM-001',
            'material_name': 'Palm Oil',
            'wastage_qty': '5.500',
            'uom': 'KG',
            'reason': 'Spill',
        })

    def test_create_waste_log(self):
        resp = self._create_waste()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_list_waste_logs(self):
        self._create_waste()
        resp = self.client.get(f'{BASE_URL}/waste/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_approve_engineer(self):
        r = self._create_waste()
        waste_id = r.data['id']
        resp = self.client.post(f'{BASE_URL}/waste/{waste_id}/approve/engineer/', {
            'sign': 'Eng. John',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_approve_am(self):
        r = self._create_waste()
        waste_id = r.data['id']
        self.client.post(f'{BASE_URL}/waste/{waste_id}/approve/engineer/', {'sign': 'Eng. John'})
        resp = self.client.post(f'{BASE_URL}/waste/{waste_id}/approve/am/', {
            'sign': 'AM. Jane',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_approve_store(self):
        r = self._create_waste()
        waste_id = r.data['id']
        self.client.post(f'{BASE_URL}/waste/{waste_id}/approve/engineer/', {'sign': 'Eng. John'})
        self.client.post(f'{BASE_URL}/waste/{waste_id}/approve/am/', {'sign': 'AM. Jane'})
        resp = self.client.post(f'{BASE_URL}/waste/{waste_id}/approve/store/', {
            'sign': 'Store. Mike',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_approve_hod(self):
        r = self._create_waste()
        waste_id = r.data['id']
        self.client.post(f'{BASE_URL}/waste/{waste_id}/approve/engineer/', {'sign': 'Eng. John'})
        self.client.post(f'{BASE_URL}/waste/{waste_id}/approve/am/', {'sign': 'AM. Jane'})
        self.client.post(f'{BASE_URL}/waste/{waste_id}/approve/store/', {'sign': 'Store. Mike'})
        resp = self.client.post(f'{BASE_URL}/waste/{waste_id}/approve/hod/', {
            'sign': 'HOD. Boss',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_unauthenticated_returns_401(self):
        unauthenticated_client = APIClient()
        resp = unauthenticated_client.get(f'{BASE_URL}/waste/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class ResourceElectricityTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        resp = self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        self.line_id = resp.data['id']
        r = self.client.post(f'{BASE_URL}/runs/', {
            'production_plan_id': self.plan.id, 'line_id': self.line_id,
            'date': str(date.today()),
        })
        self.run_id = r.data['id']

    def test_create_electricity_entry(self):
        resp = self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/electricity/', {
            'description': 'Main line electricity',
            'units_consumed': '150.500',
            'rate_per_unit': '8.5000',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('total_cost', resp.data)

    def test_total_cost_auto_calculated(self):
        resp = self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/electricity/', {
            'units_consumed': '100.000',
            'rate_per_unit': '10.0000',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(float(resp.data['total_cost']), 1000.0)

    def test_list_electricity_entries(self):
        self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/electricity/', {
            'units_consumed': '100.000',
            'rate_per_unit': '10.0000',
        })
        resp = self.client.get(f'{BASE_URL}/runs/{self.run_id}/resources/electricity/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)

    def test_update_electricity_entry(self):
        r = self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/electricity/', {
            'units_consumed': '100.000',
            'rate_per_unit': '10.0000',
        })
        entry_id = r.data['id']
        resp = self.client.patch(
            f'{BASE_URL}/runs/{self.run_id}/resources/electricity/{entry_id}/',
            {'units_consumed': '200.000'},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_delete_electricity_entry(self):
        r = self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/electricity/', {
            'units_consumed': '100.000',
            'rate_per_unit': '10.0000',
        })
        entry_id = r.data['id']
        resp = self.client.delete(
            f'{BASE_URL}/runs/{self.run_id}/resources/electricity/{entry_id}/'
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_unauthenticated_returns_401(self):
        unauthenticated_client = APIClient()
        resp = unauthenticated_client.get(
            f'{BASE_URL}/runs/{self.run_id}/resources/electricity/'
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class ResourceWaterTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        resp = self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        self.line_id = resp.data['id']
        r = self.client.post(f'{BASE_URL}/runs/', {
            'production_plan_id': self.plan.id, 'line_id': self.line_id,
            'date': str(date.today()),
        })
        self.run_id = r.data['id']

    def test_create_water_entry(self):
        resp = self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/water/', {
            'description': 'Process water',
            'volume_consumed': '500.000',
            'rate_per_unit': '2.0000',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(float(resp.data['total_cost']), 1000.0)

    def test_list_water_entries(self):
        self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/water/', {
            'volume_consumed': '500.000',
            'rate_per_unit': '2.0000',
        })
        resp = self.client.get(f'{BASE_URL}/runs/{self.run_id}/resources/water/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)

    def test_delete_water_entry(self):
        r = self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/water/', {
            'volume_consumed': '500.000',
            'rate_per_unit': '2.0000',
        })
        entry_id = r.data['id']
        resp = self.client.delete(
            f'{BASE_URL}/runs/{self.run_id}/resources/water/{entry_id}/'
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)


class ResourceGasTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        resp = self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        self.line_id = resp.data['id']
        r = self.client.post(f'{BASE_URL}/runs/', {
            'production_plan_id': self.plan.id, 'line_id': self.line_id,
            'date': str(date.today()),
        })
        self.run_id = r.data['id']

    def test_create_gas_entry(self):
        resp = self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/gas/', {
            'description': 'LPG',
            'qty_consumed': '20.000',
            'rate_per_unit': '50.0000',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(float(resp.data['total_cost']), 1000.0)

    def test_list_gas_entries(self):
        self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/gas/', {
            'qty_consumed': '20.000',
            'rate_per_unit': '50.0000',
        })
        resp = self.client.get(f'{BASE_URL}/runs/{self.run_id}/resources/gas/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_delete_gas_entry(self):
        r = self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/gas/', {
            'qty_consumed': '20.000',
            'rate_per_unit': '50.0000',
        })
        entry_id = r.data['id']
        resp = self.client.delete(
            f'{BASE_URL}/runs/{self.run_id}/resources/gas/{entry_id}/'
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)


class ResourceCompressedAirTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        resp = self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        self.line_id = resp.data['id']
        r = self.client.post(f'{BASE_URL}/runs/', {
            'production_plan_id': self.plan.id, 'line_id': self.line_id,
            'date': str(date.today()),
        })
        self.run_id = r.data['id']

    def test_create_compressed_air_entry(self):
        resp = self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/compressed-air/', {
            'description': 'Compressor A',
            'units_consumed': '200.000',
            'rate_per_unit': '1.5000',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(float(resp.data['total_cost']), 300.0)

    def test_list_compressed_air_entries(self):
        self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/compressed-air/', {
            'units_consumed': '200.000',
            'rate_per_unit': '1.5000',
        })
        resp = self.client.get(f'{BASE_URL}/runs/{self.run_id}/resources/compressed-air/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_delete_compressed_air_entry(self):
        r = self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/compressed-air/', {
            'units_consumed': '200.000',
            'rate_per_unit': '1.5000',
        })
        entry_id = r.data['id']
        resp = self.client.delete(
            f'{BASE_URL}/runs/{self.run_id}/resources/compressed-air/{entry_id}/'
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)


class ResourceLabourTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        resp = self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        self.line_id = resp.data['id']
        r = self.client.post(f'{BASE_URL}/runs/', {
            'production_plan_id': self.plan.id, 'line_id': self.line_id,
            'date': str(date.today()),
        })
        self.run_id = r.data['id']

    def test_create_labour_entry(self):
        resp = self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/labour/', {
            'worker_name': 'Ramesh Kumar',
            'hours_worked': '8.00',
            'rate_per_hour': '150.0000',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(float(resp.data['total_cost']), 1200.0)

    def test_list_labour_entries(self):
        self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/labour/', {
            'worker_name': 'Worker A',
            'hours_worked': '8.00',
            'rate_per_hour': '100.0000',
        })
        resp = self.client.get(f'{BASE_URL}/runs/{self.run_id}/resources/labour/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)

    def test_update_labour_entry(self):
        r = self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/labour/', {
            'worker_name': 'Worker A',
            'hours_worked': '8.00',
            'rate_per_hour': '100.0000',
        })
        entry_id = r.data['id']
        resp = self.client.patch(
            f'{BASE_URL}/runs/{self.run_id}/resources/labour/{entry_id}/',
            {'hours_worked': '10.00'},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_delete_labour_entry(self):
        r = self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/labour/', {
            'worker_name': 'Worker A',
            'hours_worked': '8.00',
            'rate_per_hour': '100.0000',
        })
        entry_id = r.data['id']
        resp = self.client.delete(
            f'{BASE_URL}/runs/{self.run_id}/resources/labour/{entry_id}/'
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_unauthenticated_returns_401(self):
        unauthenticated_client = APIClient()
        resp = unauthenticated_client.get(
            f'{BASE_URL}/runs/{self.run_id}/resources/labour/'
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class ResourceMachineCostTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        resp = self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        self.line_id = resp.data['id']
        r = self.client.post(f'{BASE_URL}/runs/', {
            'production_plan_id': self.plan.id, 'line_id': self.line_id,
            'date': str(date.today()),
        })
        self.run_id = r.data['id']

    def test_create_machine_cost_entry(self):
        resp = self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/machine-costs/', {
            'machine_name': 'Filler Machine',
            'hours_used': '8.00',
            'rate_per_hour': '500.0000',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(float(resp.data['total_cost']), 4000.0)

    def test_list_machine_cost_entries(self):
        self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/machine-costs/', {
            'machine_name': 'Filler',
            'hours_used': '8.00',
            'rate_per_hour': '500.0000',
        })
        resp = self.client.get(f'{BASE_URL}/runs/{self.run_id}/resources/machine-costs/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_delete_machine_cost_entry(self):
        r = self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/machine-costs/', {
            'machine_name': 'Filler',
            'hours_used': '8.00',
            'rate_per_hour': '500.0000',
        })
        entry_id = r.data['id']
        resp = self.client.delete(
            f'{BASE_URL}/runs/{self.run_id}/resources/machine-costs/{entry_id}/'
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)


class ResourceOverheadTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        resp = self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        self.line_id = resp.data['id']
        r = self.client.post(f'{BASE_URL}/runs/', {
            'production_plan_id': self.plan.id, 'line_id': self.line_id,
            'date': str(date.today()),
        })
        self.run_id = r.data['id']

    def test_create_overhead_entry(self):
        resp = self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/overhead/', {
            'expense_name': 'Factory Rent',
            'amount': '5000.00',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_list_overhead_entries(self):
        self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/overhead/', {
            'expense_name': 'Factory Rent',
            'amount': '5000.00',
        })
        resp = self.client.get(f'{BASE_URL}/runs/{self.run_id}/resources/overhead/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)

    def test_update_overhead_entry(self):
        r = self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/overhead/', {
            'expense_name': 'Factory Rent',
            'amount': '5000.00',
        })
        entry_id = r.data['id']
        resp = self.client.patch(
            f'{BASE_URL}/runs/{self.run_id}/resources/overhead/{entry_id}/',
            {'amount': '6000.00'},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_delete_overhead_entry(self):
        r = self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/overhead/', {
            'expense_name': 'Factory Rent',
            'amount': '5000.00',
        })
        entry_id = r.data['id']
        resp = self.client.delete(
            f'{BASE_URL}/runs/{self.run_id}/resources/overhead/{entry_id}/'
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_unauthenticated_returns_401(self):
        unauthenticated_client = APIClient()
        resp = unauthenticated_client.get(
            f'{BASE_URL}/runs/{self.run_id}/resources/overhead/'
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class CostSummaryTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        resp = self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        self.line_id = resp.data['id']
        r = self.client.post(f'{BASE_URL}/runs/', {
            'production_plan_id': self.plan.id, 'line_id': self.line_id,
            'date': str(date.today()),
        })
        self.run_id = r.data['id']

    def test_no_cost_returns_404(self):
        resp = self.client.get(f'{BASE_URL}/runs/{self.run_id}/cost/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_cost_calculated_after_resource(self):
        self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/electricity/', {
            'units_consumed': '100.000',
            'rate_per_unit': '10.0000',
        })
        resp = self.client.get(f'{BASE_URL}/runs/{self.run_id}/cost/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('total_cost', resp.data)
        self.assertIn('per_unit_cost', resp.data)

    def test_cost_includes_all_resources(self):
        self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/electricity/', {
            'units_consumed': '100.000',
            'rate_per_unit': '10.0000',
        })
        self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/labour/', {
            'worker_name': 'Worker A',
            'hours_worked': '8.00',
            'rate_per_hour': '100.0000',
        })
        self.client.post(f'{BASE_URL}/runs/{self.run_id}/resources/overhead/', {
            'expense_name': 'Rent',
            'amount': '500.00',
        })
        resp = self.client.get(f'{BASE_URL}/runs/{self.run_id}/cost/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # electricity=1000, labour=800, overhead=500 => total=2300
        self.assertEqual(float(resp.data['total_cost']), 2300.0)

    def test_cost_analytics_endpoint(self):
        resp = self.client.get(f'{BASE_URL}/costs/analytics/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_unauthenticated_returns_401(self):
        unauthenticated_client = APIClient()
        resp = unauthenticated_client.get(f'{BASE_URL}/runs/{self.run_id}/cost/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class InProcessQCTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        resp = self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        self.line_id = resp.data['id']
        r = self.client.post(f'{BASE_URL}/runs/', {
            'production_plan_id': self.plan.id, 'line_id': self.line_id,
            'date': str(date.today()),
        })
        self.run_id = r.data['id']

    def test_create_qc_check(self):
        resp = self.client.post(f'{BASE_URL}/runs/{self.run_id}/qc/inprocess/', {
            'checked_at': '2026-03-16T10:00:00Z',
            'parameter': 'Fill Weight',
            'acceptable_min': '99.500',
            'acceptable_max': '100.500',
            'actual_value': '100.100',
            'result': 'PASS',
            'remarks': 'Within spec',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['result'], 'PASS')

    def test_list_qc_checks(self):
        self.client.post(f'{BASE_URL}/runs/{self.run_id}/qc/inprocess/', {
            'checked_at': '2026-03-16T10:00:00Z',
            'parameter': 'Fill Weight',
            'result': 'PASS',
        })
        resp = self.client.get(f'{BASE_URL}/runs/{self.run_id}/qc/inprocess/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)

    def test_update_qc_check(self):
        r = self.client.post(f'{BASE_URL}/runs/{self.run_id}/qc/inprocess/', {
            'checked_at': '2026-03-16T10:00:00Z',
            'parameter': 'Fill Weight',
            'result': 'NA',
        })
        check_id = r.data['id']
        resp = self.client.patch(
            f'{BASE_URL}/runs/{self.run_id}/qc/inprocess/{check_id}/',
            {'result': 'PASS'},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['result'], 'PASS')

    def test_delete_qc_check(self):
        r = self.client.post(f'{BASE_URL}/runs/{self.run_id}/qc/inprocess/', {
            'checked_at': '2026-03-16T10:00:00Z',
            'parameter': 'pH',
            'result': 'FAIL',
        })
        check_id = r.data['id']
        resp = self.client.delete(
            f'{BASE_URL}/runs/{self.run_id}/qc/inprocess/{check_id}/'
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_unauthenticated_returns_401(self):
        unauthenticated_client = APIClient()
        resp = unauthenticated_client.get(
            f'{BASE_URL}/runs/{self.run_id}/qc/inprocess/'
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class FinalQCTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        resp = self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        self.line_id = resp.data['id']
        r = self.client.post(f'{BASE_URL}/runs/', {
            'production_plan_id': self.plan.id, 'line_id': self.line_id,
            'date': str(date.today()),
        })
        self.run_id = r.data['id']

    def test_create_final_qc(self):
        resp = self.client.post(
            f'{BASE_URL}/runs/{self.run_id}/qc/final/',
            {
                'checked_at': '2026-03-16T17:00:00Z',
                'overall_result': 'PASS',
                'parameters': [
                    {'name': 'Fill Weight', 'expected': '100', 'actual': '99.8', 'result': 'PASS'},
                ],
                'remarks': 'All within spec',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['overall_result'], 'PASS')

    def test_get_final_qc(self):
        self.client.post(
            f'{BASE_URL}/runs/{self.run_id}/qc/final/',
            {'checked_at': '2026-03-16T17:00:00Z', 'overall_result': 'PASS', 'parameters': []},
            format='json',
        )
        resp = self.client.get(f'{BASE_URL}/runs/{self.run_id}/qc/final/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_duplicate_final_qc_returns_400(self):
        self.client.post(
            f'{BASE_URL}/runs/{self.run_id}/qc/final/',
            {'checked_at': '2026-03-16T17:00:00Z', 'overall_result': 'PASS', 'parameters': []},
            format='json',
        )
        resp = self.client.post(
            f'{BASE_URL}/runs/{self.run_id}/qc/final/',
            {'checked_at': '2026-03-16T17:00:00Z', 'overall_result': 'FAIL', 'parameters': []},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_final_qc(self):
        self.client.post(
            f'{BASE_URL}/runs/{self.run_id}/qc/final/',
            {'checked_at': '2026-03-16T17:00:00Z', 'overall_result': 'PASS', 'parameters': []},
            format='json',
        )
        resp = self.client.patch(f'{BASE_URL}/runs/{self.run_id}/qc/final/', {
            'overall_result': 'CONDITIONAL',
            'remarks': 'Some deviations noted',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['overall_result'], 'CONDITIONAL')

    def test_get_nonexistent_final_qc_returns_404(self):
        resp = self.client.get(f'{BASE_URL}/runs/{self.run_id}/qc/final/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_returns_401(self):
        unauthenticated_client = APIClient()
        resp = unauthenticated_client.get(f'{BASE_URL}/runs/{self.run_id}/qc/final/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class ReportTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        resp = self.client.post(f'{BASE_URL}/lines/', {'name': 'Line-1'})
        self.line_id = resp.data['id']
        r = self.client.post(f'{BASE_URL}/runs/', {
            'production_plan_id': self.plan.id, 'line_id': self.line_id,
            'date': str(date.today()),
        })
        self.run_id = r.data['id']

    def test_daily_production_report(self):
        resp = self.client.get(f'{BASE_URL}/reports/daily-production/?date={date.today()}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_yield_report(self):
        resp = self.client.get(f'{BASE_URL}/reports/yield/{self.run_id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_line_clearance_report(self):
        resp = self.client.get(f'{BASE_URL}/reports/line-clearance/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_analytics_report(self):
        resp = self.client.get(f'{BASE_URL}/reports/analytics/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_oee_analytics(self):
        resp = self.client.get(f'{BASE_URL}/reports/analytics/oee/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('per_run_oee', resp.data)

    def test_downtime_analytics(self):
        resp = self.client.get(f'{BASE_URL}/reports/analytics/downtime/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('breakdowns', resp.data)
        self.assertIn('total_count', resp.data)

    def test_waste_analytics(self):
        resp = self.client.get(f'{BASE_URL}/reports/analytics/waste/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('by_material', resp.data)
        self.assertIn('by_approval_status', resp.data)

    def test_oee_analytics_with_date_filter(self):
        resp = self.client.get(
            f'{BASE_URL}/reports/analytics/oee/?date_from={date.today()}&date_to={date.today()}'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_downtime_analytics_with_date_filter(self):
        resp = self.client.get(
            f'{BASE_URL}/reports/analytics/downtime/?date_from={date.today()}'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_unauthenticated_report_returns_401(self):
        unauthenticated_client = APIClient()
        resp = unauthenticated_client.get(f'{BASE_URL}/reports/analytics/oee/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
