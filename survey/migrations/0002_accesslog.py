from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccessLog',
            fields=[
                ('id',         models.BigAutoField(auto_created=True, primary_key=True)),
                ('timestamp',  models.DateTimeField(auto_now_add=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('path',       models.CharField(max_length=500)),
                ('route_id',   models.CharField(blank=True, max_length=50, null=True)),
                ('page',       models.CharField(blank=True, max_length=100)),
                ('user_agent', models.CharField(blank=True, max_length=300)),
                ('method',     models.CharField(default='GET', max_length=10)),
            ],
            options={
                'verbose_name':        'Access Log',
                'verbose_name_plural': 'Access Logs',
                'ordering':            ['-timestamp'],
            },
        ),
    ]
