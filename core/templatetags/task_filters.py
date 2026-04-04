from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Look up a dictionary value by key in templates. Returns None for non-dict inputs."""
    if dictionary is None or not hasattr(dictionary, 'get'):
        return None
    return dictionary.get(key)
