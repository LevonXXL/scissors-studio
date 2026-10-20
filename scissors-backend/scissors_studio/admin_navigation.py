"""Group Scissors models in the Unfold admin without changing their registrations."""

from django.contrib import admin
from django.urls import reverse


SCISSORS_MODELS = (
    ('salons', 'Salon', 'Салоны'),
    ('masters', 'Master', 'Мастера'),
    ('services', 'ServiceCategory', 'Категории услуг'),
    ('services', 'Service', 'Услуги и цены'),
)


def group_apps(apps):
    labels = {(app_label, model_name): title for app_label, model_name, title in SCISSORS_MODELS}
    scissors_models = {}
    other_apps = []

    for app in apps:
        remaining_models = []
        for model in app['models']:
            key = (app['app_label'], model['object_name'])
            if key in labels:
                scissors_models[key] = {**model, 'name': labels[key]}
            else:
                remaining_models.append(model)
        if remaining_models:
            other_apps.append({**app, 'models': remaining_models})

    ordered_models = [
        scissors_models[(app_label, model_name)]
        for app_label, model_name, _ in SCISSORS_MODELS
        if (app_label, model_name) in scissors_models
    ]
    return ordered_models, other_apps


def sidebar_navigation(request):
    scissors_models, other_apps = group_apps(admin.site.get_app_list(request))
    groups = []

    if scissors_models:
        groups.append({'title': 'Scissors', 'items': [
            {'title': model['name'], 'link': model.get('admin_url') or model.get('add_url')}
            for model in scissors_models
            if model.get('admin_url') or model.get('add_url')
        ]})

    for app in other_apps:
        items = [
            {'title': model['name'], 'link': model.get('admin_url') or model.get('add_url')}
            for model in app['models']
            if model.get('admin_url') or model.get('add_url')
        ]
        if items:
            groups.append({'title': app['name'], 'items': items})
    if request.user.is_staff:
        groups.append({'title': 'Уведомления', 'items': [
            {'title': 'Мои настройки', 'link': reverse('admin-push-settings')},
        ]})
    return groups


def dashboard_callback(request, context):
    scissors_models, other_apps = group_apps(context['app_list'])
    if scissors_models:
        first_link = next(
            (model.get('admin_url') or model.get('add_url') for model in scissors_models
             if model.get('admin_url') or model.get('add_url')),
            reverse('admin:index'),
        )
        context['app_list'] = [{
            'app_label': 'scissors',
            'name': 'Scissors',
            'app_url': first_link,
            'models': scissors_models,
        }, *other_apps]
    return context
