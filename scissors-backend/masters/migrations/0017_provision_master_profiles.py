from django.contrib.auth.hashers import make_password
from django.db import migrations
from django.db.models import F, Max, Q


EXISTING_USERS = {
    '763752': 'StetsMikhail',  # Михаил Стець
    '12824204': 'Gadeliia',  # Гаделия Котелова
}


def provision_master_profiles(apps, schema_editor):
    Master = apps.get_model('masters', 'Master')
    Page = apps.get_model('pages', 'Page')
    User = apps.get_model('auth', 'User')
    db = schema_editor.connection.alias

    masters = Master.objects.using(db).filter(is_system=False,
                                              is_booking_placeholder=False).filter(
        Q(is_active=True) | Q(yclients_user_id='12824204')
    ).order_by('pk')
    if not masters.exists():
        return

    team = Page.objects.using(db).filter(url_path='team', parent_id__isnull=True).first()
    if team is None:
        tree_id = (Page.objects.using(db).aggregate(value=Max('tree_id'))['value'] or 0) + 1
        team = Page.objects.using(db).create(
            title='Команда', url='team', url_path='team', content='',
            tree_id=tree_id, lft=1, rght=2, level=0,
        )
    for master in masters:
        if not master.slug:
            master.slug = f'master-{master.pk}'
            master.save(using=db, update_fields=['slug'])
        if master.page_id:
            page = Page.objects.using(db).get(pk=master.page_id)
            if page.parent_id != team.pk:
                raise RuntimeError(f'Страница мастера #{master.pk} не находится под team.')
        else:
            path = f'team/{master.slug}'
            page = Page.objects.using(db).filter(url_path=path).first()
            if page is not None:
                if page.parent_id != team.pk or Master.objects.using(db).filter(page_id=page.pk).exclude(
                        pk=master.pk).exists():
                    raise RuntimeError(f'Страница {path} уже занята другой записью.')
            else:
                team.refresh_from_db(using=db)
                right = team.rght
                tree = Page.objects.using(db).filter(tree_id=team.tree_id)
                tree.filter(rght__gte=right).update(rght=F('rght') + 2)
                tree.filter(lft__gt=right).update(lft=F('lft') + 2)
                page = Page.objects.using(db).create(
                    title=master.name, url=master.slug, url_path=path,
                    parent_id=team.pk, tree_id=team.tree_id,
                    lft=right, rght=right + 1, level=team.level + 1,
                )
            master.page_id = page.pk
            master.save(using=db, update_fields=['page'])

        username = EXISTING_USERS.get(master.yclients_user_id)
        if master.user_id:
            user = User.objects.using(db).get(pk=master.user_id)
            username = user.username
        elif username:
            user = User.objects.using(db).filter(username=username).first()
            if user is None:
                user = User.objects.using(db).create(
                    username=username, password=make_password(None),
                    is_staff=True, is_active=True, is_superuser=False,
                )
        else:
            username = f'master_{master.pk}'
            user = User.objects.using(db).filter(username=username).first()
            if user is None:
                user = User.objects.using(db).create(
                    username=username, password=make_password(None),
                    is_staff=True, is_active=True, is_superuser=False,
                )
            elif master.user_id != user.pk:
                raise RuntimeError(f'Имя пользователя {username} уже занято.')

        if Master.objects.using(db).filter(user_id=user.pk).exclude(pk=master.pk).exists():
            raise RuntimeError(f'Учётная запись {username} уже связана с другим мастером.')
        if master.user_id != user.pk:
            master.user_id = user.pk
            master.save(using=db, update_fields=['user'])
        if not user.is_staff or user.is_superuser:
            User.objects.using(db).filter(pk=user.pk).update(is_staff=True, is_superuser=False)


class Migration(migrations.Migration):
    dependencies = [
        ('masters', '0016_master_user'),
    ]

    operations = [
        migrations.RunPython(provision_master_profiles, migrations.RunPython.noop),
    ]
