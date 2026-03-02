from django.db import migrations


def update_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    group, created = Group.objects.get_or_create(name='grpo')
    permissions = Permission.objects.filter(content_type__app_label='grpo')
    group.permissions.set(permissions)


def reverse_update(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    try:
        group = Group.objects.get(name='grpo')
        # Remove only attachment permissions on reverse
        attachment_perms = Permission.objects.filter(
            content_type__app_label='grpo',
            codename__contains='grpoattachment'
        )
        group.permissions.remove(*attachment_perms)
    except Group.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('grpo', '0008_grpoattachment'),
    ]

    operations = [
        migrations.RunPython(update_group, reverse_update),
    ]
