import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('production_execution', '0002_create_production_execution_group'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ResourceElectricity
        migrations.CreateModel(
            name='ResourceElectricity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(blank=True, default='', max_length=200)),
                ('units_consumed', models.DecimalField(decimal_places=3, max_digits=12)),
                ('rate_per_unit', models.DecimalField(decimal_places=4, max_digits=12)),
                ('total_cost', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='electricity_entries', to=settings.AUTH_USER_MODEL)),
                ('production_run', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='electricity_usage', to='production_execution.productionrun')),
            ],
            options={
                'verbose_name': 'Electricity Usage',
                'verbose_name_plural': 'Electricity Usages',
                'ordering': ['-created_at'],
            },
        ),
        # ResourceWater
        migrations.CreateModel(
            name='ResourceWater',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(blank=True, default='', max_length=200)),
                ('volume_consumed', models.DecimalField(decimal_places=3, max_digits=12)),
                ('rate_per_unit', models.DecimalField(decimal_places=4, max_digits=12)),
                ('total_cost', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='water_entries', to=settings.AUTH_USER_MODEL)),
                ('production_run', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='water_usage', to='production_execution.productionrun')),
            ],
            options={
                'verbose_name': 'Water Usage',
                'verbose_name_plural': 'Water Usages',
                'ordering': ['-created_at'],
            },
        ),
        # ResourceGas
        migrations.CreateModel(
            name='ResourceGas',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(blank=True, default='', max_length=200)),
                ('qty_consumed', models.DecimalField(decimal_places=3, max_digits=12)),
                ('rate_per_unit', models.DecimalField(decimal_places=4, max_digits=12)),
                ('total_cost', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='gas_entries', to=settings.AUTH_USER_MODEL)),
                ('production_run', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gas_usage', to='production_execution.productionrun')),
            ],
            options={
                'verbose_name': 'Gas Usage',
                'verbose_name_plural': 'Gas Usages',
                'ordering': ['-created_at'],
            },
        ),
        # ResourceCompressedAir
        migrations.CreateModel(
            name='ResourceCompressedAir',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(blank=True, default='', max_length=200)),
                ('units_consumed', models.DecimalField(decimal_places=3, max_digits=12)),
                ('rate_per_unit', models.DecimalField(decimal_places=4, max_digits=12)),
                ('total_cost', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='compressed_air_entries', to=settings.AUTH_USER_MODEL)),
                ('production_run', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='compressed_air_usage', to='production_execution.productionrun')),
            ],
            options={
                'verbose_name': 'Compressed Air Usage',
                'verbose_name_plural': 'Compressed Air Usages',
                'ordering': ['-created_at'],
            },
        ),
        # ResourceLabour
        migrations.CreateModel(
            name='ResourceLabour',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('worker_name', models.CharField(max_length=200)),
                ('hours_worked', models.DecimalField(decimal_places=2, max_digits=8)),
                ('rate_per_hour', models.DecimalField(decimal_places=4, max_digits=12)),
                ('total_cost', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='labour_entries_created', to=settings.AUTH_USER_MODEL)),
                ('production_run', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='labour_entries', to='production_execution.productionrun')),
            ],
            options={
                'verbose_name': 'Labour Entry',
                'verbose_name_plural': 'Labour Entries',
                'ordering': ['-created_at'],
            },
        ),
        # ResourceMachineCost
        migrations.CreateModel(
            name='ResourceMachineCost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('machine_name', models.CharField(max_length=200)),
                ('hours_used', models.DecimalField(decimal_places=2, max_digits=8)),
                ('rate_per_hour', models.DecimalField(decimal_places=4, max_digits=12)),
                ('total_cost', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='machine_cost_entries_created', to=settings.AUTH_USER_MODEL)),
                ('production_run', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='machine_cost_entries', to='production_execution.productionrun')),
            ],
            options={
                'verbose_name': 'Machine Cost Entry',
                'verbose_name_plural': 'Machine Cost Entries',
                'ordering': ['-created_at'],
            },
        ),
        # ResourceOverhead
        migrations.CreateModel(
            name='ResourceOverhead',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('expense_name', models.CharField(max_length=200)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='overhead_entries_created', to=settings.AUTH_USER_MODEL)),
                ('production_run', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='overhead_entries', to='production_execution.productionrun')),
            ],
            options={
                'verbose_name': 'Overhead Entry',
                'verbose_name_plural': 'Overhead Entries',
                'ordering': ['-created_at'],
            },
        ),
        # ProductionRunCost
        migrations.CreateModel(
            name='ProductionRunCost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('raw_material_cost', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('labour_cost', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('machine_cost', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('electricity_cost', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('water_cost', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('gas_cost', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('compressed_air_cost', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('overhead_cost', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('total_cost', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('produced_qty', models.DecimalField(decimal_places=3, default=0, max_digits=15)),
                ('per_unit_cost', models.DecimalField(decimal_places=4, default=0, max_digits=15)),
                ('calculated_at', models.DateTimeField(auto_now=True)),
                ('production_run', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='cost_summary', to='production_execution.productionrun')),
            ],
            options={
                'verbose_name': 'Production Run Cost',
                'verbose_name_plural': 'Production Run Costs',
            },
        ),
        # InProcessQCCheck
        migrations.CreateModel(
            name='InProcessQCCheck',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('checked_at', models.DateTimeField()),
                ('parameter', models.CharField(max_length=200)),
                ('acceptable_min', models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True)),
                ('acceptable_max', models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True)),
                ('actual_value', models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True)),
                ('result', models.CharField(choices=[('PASS', 'Pass'), ('FAIL', 'Fail'), ('NA', 'N/A')], default='NA', max_length=10)),
                ('remarks', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('checked_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inprocess_qc_checks', to=settings.AUTH_USER_MODEL)),
                ('production_run', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inprocess_qc_checks', to='production_execution.productionrun')),
            ],
            options={
                'verbose_name': 'In-Process QC Check',
                'verbose_name_plural': 'In-Process QC Checks',
                'ordering': ['checked_at'],
            },
        ),
        # FinalQCCheck
        migrations.CreateModel(
            name='FinalQCCheck',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('checked_at', models.DateTimeField()),
                ('overall_result', models.CharField(choices=[('PASS', 'Pass'), ('FAIL', 'Fail'), ('CONDITIONAL', 'Conditional')], default='PASS', max_length=15)),
                ('parameters', models.JSONField(default=list, help_text='List of {name, expected, actual, result} dicts')),
                ('remarks', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('checked_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='final_qc_checks', to=settings.AUTH_USER_MODEL)),
                ('production_run', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='final_qc', to='production_execution.productionrun')),
            ],
            options={
                'verbose_name': 'Final QC Check',
                'verbose_name_plural': 'Final QC Checks',
            },
        ),
    ]
