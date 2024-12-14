from django import template
register = template.Library()
NAV_ITEMS = [
    {'name': 'dashboard', 'icon': 'home', 'url_name': "app_webapp:dashboard"},
    {'name': 'campaigns', 'icon': 'paper-plane', 'url_name': 'app_webapp:campaigns'},
    {'name': 'contacts', 'icon': 'users', 'url_name': 'app_webapp:contacts'},
    {'name': 'conversations', 'icon': 'comments', 'url_name': 'app_webapp:conversations'},
]
@register.inclusion_tag('webapp/fragments/sidebar.html', takes_context=True)
def main_navigation(context):
    return {
        'nav_items': NAV_ITEMS,
        'current_page': context.get('current_page', ''),
        "user": context["user"],
    }