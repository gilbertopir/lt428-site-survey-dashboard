from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Allow dict lookup with a key that contains spaces or special chars."""
    if isinstance(dictionary, dict):
        return dictionary.get(key, '')
    return ''
