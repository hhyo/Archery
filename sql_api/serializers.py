from sql.models import SqlWorkflow, Instance
from rest_framework import serializers

class SqlWorkflowListSerilizer(serializers.ModelSerializer):
    class Meta:
        model = SqlWorkflow
        fields = ('id', 'workflow_name', 'status', 'engineer', 'engineer_display',
            'create_time', 'instance_name', 'db_name', 'is_backup'
        )

class SqlWorkflowDetailSerilizer(serializers.ModelSerializer):
    class Meta:
        model = SqlWorkflow
        fields = ('__all__')

class InstanceSerilizer(serializers.ModelSerializer):
    class Meta:
        model = Instance
        fields = ('id', 'instance_name', 'type', 'db_type')