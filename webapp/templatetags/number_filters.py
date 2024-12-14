from django import template
from django.template.defaultfilters import floatformat
register = template.Library()

@register.filter
def add_commas(value):
    try:
        value = int(value)
        return "{:,}".format(value)
    except (ValueError, TypeError):
        return value
    
@register.filter
def format_number(value):
    """
    Format numbers to K (thousands) or M (millions) format
    Examples:
        1234 -> 1.2K
        12345 -> 12.3K
        123456 -> 123.4K
        1234567 -> 1.2M
    """
    if not isinstance(value, (int, float)):
        return value
    
    value = float(value)
    
    if value >= 1000000:
        formatted = floatformat(value/1000000, 1)
        return f"{formatted}M"
    elif value >= 1000:
        formatted = floatformat(value/1000, 1)
        return f"{formatted}K"
    else:
        return str(int(value))