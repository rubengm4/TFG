from django import template
from django.urls import reverse, NoReverseMatch  # type: ignore

register = template.Library()


@register.filter
def to_url_name(value: str):
    """
    Transforma 'pv-analysis' o 'PV Analysis' en 'pv_analysis_home'.
    Cambia guiones y espacios a guion bajo, pasa a minúsculas y añade '_home'.
    """
    value = value.lower().replace('-', '_').replace(' ', '_')
    return f"{value}"


@register.simple_tag
def dynamic_url(name: str):
    try:
        return reverse(to_url_name(name))
    except NoReverseMatch:
        return '#'
