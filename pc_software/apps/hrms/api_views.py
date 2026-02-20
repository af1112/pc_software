import datetime
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.hrms.models import (
    AttendanceLog,
    Employee,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
    PayrollOvertimeEntry,
    PayrollPeriod,
    PayrollResult,
    SalaryStructure,
    ShiftTemplate,
    ShiftVersion,
    Timesheet,
    WorkCalendar,
)
from apps.hrms.permissions import IsEmployeeSelfService, IsExecutiveOrHRManager, IsHRMSManager, IsHRMSManagerOrReadOnly
from apps.hrms.serializers import (
    AttendanceLogSerializer,
    EmployeeSerializer,
    ESSAttendancePunchSerializer,
    ESSLeaveRequestCreateSerializer,
    ExecutiveDashboardSerializer,
    LeaveBalanceSerializer,
    LeaveRequestSerializer,
    LeaveTypeSerializer,
    PayrollPeriodSerializer,
    PayrollOvertimeEntrySerializer,
    PayrollResultSerializer,
    SalaryStructureSerializer,
    ShiftTemplateSerializer,
    ShiftVersionSerializer,
    TimesheetSerializer,
    WorkCalendarSerializer,
)
from apps.hrms.services import LeaveManagementService, OvertimePayService, PayrollEngineService, TimesheetEngine
from apps.hrms.tenant import TenantResolutionError, require_company_for_request


class TenantFilteredModelViewSet(viewsets.ModelViewSet):
    permission_classes = [IsHRMSManagerOrReadOnly]
    tenant_field_name = 'tenant'

    def get_queryset(self):
        try:
            company = require_company_for_request(self.request)
        except TenantResolutionError as exc:
            raise NotFound(str(exc)) from exc
        queryset = self.queryset
        return queryset.filter(**{self.tenant_field_name: company})

    def perform_create(self, serializer):
        try:
            company = require_company_for_request(self.request)
        except TenantResolutionError as exc:
            raise ValidationError(str(exc)) from exc
        serializer.save(**{self.tenant_field_name: company})


class EmployeeViewSet(TenantFilteredModelViewSet):
    serializer_class = EmployeeSerializer
    queryset = Employee.objects.select_related('tenant', 'user', 'personnel_employee').all()

    def get_queryset(self):
        queryset = super().get_queryset()
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=str(is_active).lower() == 'true')
        return queryset


class WorkCalendarViewSet(TenantFilteredModelViewSet):
    serializer_class = WorkCalendarSerializer
    queryset = WorkCalendar.objects.select_related('tenant').all()


class ShiftTemplateViewSet(TenantFilteredModelViewSet):
    serializer_class = ShiftTemplateSerializer
    queryset = ShiftTemplate.objects.select_related('tenant').all()


class ShiftVersionViewSet(TenantFilteredModelViewSet):
    serializer_class = ShiftVersionSerializer
    queryset = ShiftVersion.objects.select_related('tenant', 'shift').all()


class AttendanceLogViewSet(TenantFilteredModelViewSet):
    serializer_class = AttendanceLogSerializer
    queryset = AttendanceLog.objects.select_related('tenant', 'employee').all()


class TimesheetViewSet(TenantFilteredModelViewSet):
    serializer_class = TimesheetSerializer
    queryset = Timesheet.objects.select_related('tenant', 'employee').all()

    @action(detail=False, methods=['post'])
    def rebuild(self, request):
        try:
            company = require_company_for_request(request)
        except TenantResolutionError as exc:
            raise ValidationError(str(exc)) from exc
        employee_id = request.data.get('employee_id')
        work_date = request.data.get('work_date')

        if not employee_id or not work_date:
            return Response({'detail': 'employee_id and work_date are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            parsed_work_date = datetime.date.fromisoformat(str(work_date))
        except ValueError:
            return Response({'detail': 'work_date must be in YYYY-MM-DD format.'}, status=status.HTTP_400_BAD_REQUEST)

        employee = Employee.objects.filter(tenant=company, id=employee_id).first()
        if employee is None:
            return Response({'detail': 'Employee not found in tenant.'}, status=status.HTTP_404_NOT_FOUND)

        result = TimesheetEngine.build_for_date(company, employee, parsed_work_date)
        payload = TimesheetSerializer(result.timesheet).data
        payload['created'] = result.created
        return Response(payload)


class PayrollOvertimeEntryViewSet(TenantFilteredModelViewSet):
    serializer_class = PayrollOvertimeEntrySerializer
    queryset = PayrollOvertimeEntry.objects.select_related('tenant', 'employee').all()

    @action(detail=False, methods=['post'])
    def generate(self, request):
        try:
            company = require_company_for_request(request)
        except TenantResolutionError as exc:
            raise ValidationError(str(exc)) from exc
        employee_id = request.data.get('employee_id')
        year = request.data.get('year')
        month = request.data.get('month')

        if not employee_id or not year or not month:
            return Response({'detail': 'employee_id, year, and month are required.'}, status=status.HTTP_400_BAD_REQUEST)

        employee = Employee.objects.filter(tenant=company, id=employee_id).first()
        if employee is None:
            return Response({'detail': 'Employee not found in tenant.'}, status=status.HTTP_404_NOT_FOUND)

        entry = OvertimePayService.generate_monthly_entry(company, employee, int(year), int(month))
        return Response(PayrollOvertimeEntrySerializer(entry).data)


class LeaveTypeViewSet(TenantFilteredModelViewSet):
    serializer_class = LeaveTypeSerializer
    queryset = LeaveType.objects.select_related('tenant').all()

    def get_queryset(self):
        queryset = super().get_queryset()
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=str(is_active).lower() == 'true')
        return queryset


class LeaveBalanceViewSet(TenantFilteredModelViewSet):
    serializer_class = LeaveBalanceSerializer
    queryset = LeaveBalance.objects.select_related('tenant', 'employee', 'leave_type').all()

    def get_queryset(self):
        queryset = super().get_queryset()
        employee_id = self.request.query_params.get('employee_id')
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        return queryset


class LeaveRequestViewSet(TenantFilteredModelViewSet):
    serializer_class = LeaveRequestSerializer
    queryset = LeaveRequest.objects.select_related('tenant', 'employee', 'leave_type', 'approved_by').all()

    def get_queryset(self):
        queryset = super().get_queryset()
        status_param = self.request.query_params.get('status')
        employee_id = self.request.query_params.get('employee_id')
        if status_param:
            queryset = queryset.filter(status=status_param)
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        return queryset

    def create(self, request, *args, **kwargs):
        try:
            company = require_company_for_request(request)
        except TenantResolutionError as exc:
            raise ValidationError(str(exc)) from exc

        employee_id = request.data.get('employee')
        leave_type_id = request.data.get('leave_type')
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')

        if not all([employee_id, leave_type_id, start_date, end_date]):
            raise ValidationError('employee, leave_type, start_date and end_date are required.')

        employee = Employee.objects.filter(tenant=company, id=employee_id).first()
        leave_type = LeaveType.objects.filter(tenant=company, id=leave_type_id, is_active=True).first()
        if employee is None or leave_type is None:
            raise ValidationError('Invalid employee or leave_type for tenant.')

        try:
            parsed_start = datetime.date.fromisoformat(start_date)
            parsed_end = datetime.date.fromisoformat(end_date)
        except ValueError as exc:
            raise ValidationError('start_date and end_date must be in YYYY-MM-DD format.') from exc

        try:
            leave_request = LeaveManagementService.submit_request(
                tenant=company,
                employee=employee,
                leave_type=leave_type,
                start_date=parsed_start,
                end_date=parsed_end,
                reason=request.data.get('reason', ''),
                attachment=request.FILES.get('attachment'),
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(self.get_serializer(leave_request).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[IsHRMSManager])
    def approve(self, request, pk=None):
        leave_request = self.get_object()
        try:
            LeaveManagementService.approve_request(leave_request, approver=request.user)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(self.get_serializer(leave_request).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        leave_request = self.get_object()
        user_emp = Employee.objects.filter(tenant=leave_request.tenant, user=request.user).first()
        is_manager = IsHRMSManager().has_permission(request, self)
        if not is_manager and (user_emp is None or user_emp.id != leave_request.employee_id):
            return Response({'detail': 'Not allowed to cancel this leave request.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            LeaveManagementService.cancel_request(leave_request)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(self.get_serializer(leave_request).data)


class PayrollPeriodViewSet(TenantFilteredModelViewSet):
    serializer_class = PayrollPeriodSerializer
    queryset = PayrollPeriod.objects.select_related('tenant').all()
    permission_classes = [IsHRMSManager]

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        period = self.get_object()
        processed = PayrollEngineService.generate_payroll_for_period(period.tenant, period)
        return Response({'processed_employees': processed, 'status': period.status})


class SalaryStructureViewSet(TenantFilteredModelViewSet):
    serializer_class = SalaryStructureSerializer
    queryset = SalaryStructure.objects.select_related('tenant', 'employee').all()
    permission_classes = [IsHRMSManager]

    def get_queryset(self):
        queryset = super().get_queryset()
        employee_id = self.request.query_params.get('employee_id')
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        return queryset


class PayrollResultViewSet(TenantFilteredModelViewSet):
    serializer_class = PayrollResultSerializer
    queryset = PayrollResult.objects.select_related('tenant', 'employee', 'period').all()
    permission_classes = [IsHRMSManager]

    def get_queryset(self):
        queryset = super().get_queryset()
        period_id = self.request.query_params.get('period_id')
        employee_id = self.request.query_params.get('employee_id')
        if period_id:
            queryset = queryset.filter(period_id=period_id)
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        return queryset


class ESSViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, IsEmployeeSelfService]

    def _resolve_company_employee(self, request):
        try:
            company = require_company_for_request(request)
        except TenantResolutionError as exc:
            raise NotFound(str(exc)) from exc
        employee = Employee.objects.filter(tenant=company, user=request.user, is_active=True).first()
        if employee is None:
            raise NotFound('Employee profile not found for authenticated user in this tenant.')
        return company, employee

    @action(detail=False, methods=['get'])
    def profile(self, request):
        _, employee = self._resolve_company_employee(request)
        return Response(EmployeeSerializer(employee).data)

    @action(detail=False, methods=['get'])
    def timesheets(self, request):
        _, employee = self._resolve_company_employee(request)
        queryset = Timesheet.objects.filter(employee=employee).order_by('-work_date')
        month = request.query_params.get('month')
        if month:
            try:
                year, month_num = [int(p) for p in month.split('-')]
                queryset = queryset.filter(work_date__year=year, work_date__month=month_num)
            except (ValueError, TypeError):
                raise ValidationError('month must be in YYYY-MM format.')
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(TimesheetSerializer(page, many=True).data)
        return Response(TimesheetSerializer(queryset, many=True).data)

    @action(detail=False, methods=['get'])
    def payslips(self, request):
        _, employee = self._resolve_company_employee(request)
        queryset = PayrollResult.objects.filter(employee=employee).select_related('period').order_by('-created_at')
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(PayrollResultSerializer(page, many=True).data)
        return Response(PayrollResultSerializer(queryset, many=True).data)

    @action(detail=False, methods=['get'])
    def leave_balances(self, request):
        _, employee = self._resolve_company_employee(request)
        queryset = LeaveBalance.objects.filter(employee=employee).select_related('leave_type')
        return Response(LeaveBalanceSerializer(queryset, many=True).data)

    @action(detail=False, methods=['post'])
    def submit_leave(self, request):
        company, employee = self._resolve_company_employee(request)
        serializer = ESSLeaveRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        leave_type = LeaveType.objects.filter(tenant=company, id=serializer.validated_data['leave_type_id'], is_active=True).first()
        if leave_type is None:
            raise ValidationError({'leave_type_id': 'Invalid leave_type_id for tenant.'})

        try:
            leave_request = LeaveManagementService.submit_request(
                tenant=company,
                employee=employee,
                leave_type=leave_type,
                start_date=serializer.validated_data['start_date'],
                end_date=serializer.validated_data['end_date'],
                reason=serializer.validated_data.get('reason', ''),
                attachment=serializer.validated_data.get('attachment'),
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(LeaveRequestSerializer(leave_request).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def attendance_punch(self, request):
        company, employee = self._resolve_company_employee(request)
        serializer = ESSAttendancePunchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        now = timezone.now()
        payload = serializer.validated_data

        if payload['action'] == 'in':
            log = AttendanceLog.objects.create(
                tenant=company,
                employee=employee,
                check_in=now,
                source=AttendanceLog.Source.MOBILE,
                device_id=payload.get('device_id'),
                lat=payload.get('lat'),
                lng=payload.get('lng'),
            )
            TimesheetEngine.build_for_date(company, employee, now.date())
            return Response(AttendanceLogSerializer(log).data, status=status.HTTP_201_CREATED)

        open_log = (
            AttendanceLog.objects.filter(tenant=company, employee=employee, check_out__isnull=True)
            .order_by('-check_in')
            .first()
        )
        if open_log is None:
            return Response({'detail': 'No open check-in found.'}, status=status.HTTP_400_BAD_REQUEST)
        open_log.check_out = now
        if payload.get('device_id'):
            open_log.device_id = payload['device_id']
        if payload.get('lat') is not None:
            open_log.lat = payload['lat']
        if payload.get('lng') is not None:
            open_log.lng = payload['lng']
        open_log.save(update_fields=['check_out', 'device_id', 'lat', 'lng'])
        TimesheetEngine.build_for_date(company, employee, open_log.check_in.date())
        return Response(AttendanceLogSerializer(open_log).data)


class ExecutiveDashboardViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsExecutiveOrHRManager]

    @action(detail=False, methods=['get'])
    def kpis(self, request):
        try:
            company = require_company_for_request(request)
        except TenantResolutionError as exc:
            raise NotFound(str(exc)) from exc

        today = timezone.localdate()
        month_start = today.replace(day=1)
        current_period = (
            PayrollPeriod.objects.filter(tenant=company, start_date__lte=today, end_date__gte=today)
            .order_by('-start_date')
            .first()
        )

        employees = Employee.objects.filter(tenant=company)
        total_headcount = employees.count()
        active_employees = employees.filter(is_active=True).count()

        payroll_cost = Decimal('0.000')
        if current_period:
            payroll_cost = (
                PayrollResult.objects.filter(tenant=company, period=current_period).aggregate(v=Sum('net_salary'))['v']
                or Decimal('0.000')
            )

        overtime_cost = (
            Timesheet.objects.filter(tenant=company, work_date__gte=month_start, work_date__lte=today).aggregate(v=Sum('overtime_pay_amount'))['v']
            or Decimal('0.000')
        )

        monthly_timesheets = Timesheet.objects.filter(tenant=company, work_date__gte=month_start, work_date__lte=today)
        total_timesheets = monthly_timesheets.count()
        absent_count = monthly_timesheets.filter(is_absent=True).count()
        late_count = monthly_timesheets.filter(late_minutes__gt=0).count()
        absenteeism_rate = Decimal('0.00') if total_timesheets == 0 else (Decimal(absent_count) / Decimal(total_timesheets) * Decimal('100')).quantize(Decimal('0.01'))
        late_rate = Decimal('0.00') if total_timesheets == 0 else (Decimal(late_count) / Decimal(total_timesheets) * Decimal('100')).quantize(Decimal('0.01'))

        approved_leave_days = (
            LeaveRequest.objects.filter(
                tenant=company,
                status=LeaveRequest.Status.APPROVED,
                start_date__gte=month_start,
                end_date__lte=today,
            ).aggregate(v=Sum('total_days'))['v']
            or Decimal('0.00')
        )
        denominator = Decimal(active_employees) * Decimal(max(today.day, 1))
        leave_utilization_rate = Decimal('0.00') if denominator == 0 else (approved_leave_days / denominator * Decimal('100')).quantize(Decimal('0.01'))

        cost_by_department_qs = (
            PayrollResult.objects.filter(tenant=company, period=current_period)
            .values('employee__personnel_employee__department')
            .annotate(total_cost=Sum('net_salary'), headcount=Count('employee', distinct=True))
            .order_by('-total_cost')
            if current_period
            else []
        )
        cost_by_department = [
            {
                'department': row.get('employee__personnel_employee__department') or 'Unassigned',
                'total_cost': row['total_cost'] or Decimal('0.000'),
                'headcount': row['headcount'],
            }
            for row in cost_by_department_qs
        ]

        payload = {
            'total_headcount': total_headcount,
            'active_employees': active_employees,
            'payroll_cost_current_month': payroll_cost,
            'overtime_cost_current_month': overtime_cost,
            'absenteeism_rate': absenteeism_rate,
            'late_rate': late_rate,
            'leave_utilization_rate': leave_utilization_rate,
            'cost_by_department': cost_by_department,
        }
        serializer = ExecutiveDashboardSerializer(payload)
        return Response(serializer.data)
