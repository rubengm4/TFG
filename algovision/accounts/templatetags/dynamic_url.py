from django import template
from django.urls import reverse, NoReverseMatch

register = template.Library()


@register.filter
def to_url_name(value):
    """
    Transforma 'fv-analysis' o 'FV Analysis' en 'fv_analysis_home'.
    Cambia guiones y espacios a guion bajo, pasa a minúsculas y añade '_home'.
    """
    if not isinstance(value, str):
        return ''
    value = value.lower().replace('-', '_').replace(' ', '_')
    return f"{value}"


@register.simple_tag
def dynamic_url(name):
    try:
        return reverse(to_url_name(name))
    except NoReverseMatch:
        return '#'
