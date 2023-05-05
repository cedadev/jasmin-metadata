# Generated by Django 3.2.12 on 2022-02-07 13:59

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("jasmin_metadata", "0002_auto_20170125_1755"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="choicefieldbase",
            options={"base_manager_name": "objects"},
        ),
        migrations.AlterModelOptions(
            name="textfieldbase",
            options={"base_manager_name": "objects"},
        ),
        migrations.AlterField(
            model_name="field",
            name="id",
            field=models.AutoField(primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name="form",
            name="id",
            field=models.AutoField(primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name="metadatum",
            name="id",
            field=models.AutoField(primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name="userchoice",
            name="id",
            field=models.AutoField(primary_key=True, serialize=False),
        ),
    ]
