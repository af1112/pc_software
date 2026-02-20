from rest_framework import serializers

from apps.hrms.models import (
    AttendanceLog,
    Employee,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
    PayrollPeriod,
    PayrollOvertimeEntry,
    PayrollResult,
    SalaryStructure,
    ShiftTemplate,
    ShiftVersion,
    Timesheet,
    WorkCalendar,
)


class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = [
            'id',
            'tenant',
            'personnel_employee',
            'user',
            'employee_code',
            'first_name',
            'last_name',
            'nationality',
            'hire_date',
            'employment_type',
            'basic_salary',
            'ai_risk_score',
            'ai_attrition_risk_score',
            'is_active',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class WorkCalendarSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkCalendar
        fields = '__all__'


class ShiftTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftTemplate
        fields = '__all__'


class ShiftVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftVersion
        fields = '__all__'


class AttendanceLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceLog
        fields = '__all__'


class TimesheetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Timesheet
        fields = '__all__'


class PayrollOvertimeEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollOvertimeEntry
        fields = '__all__'


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = '__all__'


class LeaveBalanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveBalance
        fields = '__all__'


class LeaveRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveRequest
        fields = '__all__'
        read_only_fields = ['id', 'tenant', 'employee', 'total_days', 'approved_by', 'approved_at', 'created_at']

    def validate(self, attrs):
        if attrs.get('end_date') and attrs.get('start_date') and attrs['end_date'] < attrs['start_date']:
            raise serializers.ValidationError({'end_date': 'end_date cannot be earlier than start_date.'})
        return attrs


class PayrollPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollPeriod
        fields = '__all__'


class SalaryStructureSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalaryStructure
        fields = '__all__'


class PayrollResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollResult
        fields = '__all__'


class ESSLeaveRequestCreateSerializer(serializers.Serializer):
    leave_type_id = serializers.UUIDField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    reason = serializers.CharField(required=False, allow_blank=True)
    attachment = serializers.FileField(required=False)


class ESSAttendancePunchSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['in', 'out'])
    device_id = serializers.CharField(required=False, allow_blank=True)
    lat = serializers.DecimalField(max_digits=9, decimal_places=6, required=False)
    lng = serializers.DecimalField(max_digits=9, decimal_places=6, required=False)


class ExecutiveDashboardSerializer(serializers.Serializer):
    total_headcount = serializers.IntegerField()
    active_employees = serializers.IntegerField()
    payroll_cost_current_month = serializers.DecimalField(max_digits=18, decimal_places=3)
    overtime_cost_current_month = serializers.DecimalField(max_digits=18, decimal_places=3)
    absenteeism_rate = serializers.DecimalField(max_digits=8, decimal_places=2)
    late_rate = serializers.DecimalField(max_digits=8, decimal_places=2)
    leave_utilization_rate = serializers.DecimalField(max_digits=8, decimal_places=2)
    cost_by_department = serializers.ListField(child=serializers.DictField())
