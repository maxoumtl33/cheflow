# Dans livraison/templatetags/livraison_filters.py

from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Récupère un item d'un dictionnaire par sa clé"""
    if dictionary is None:
        return None
    return dictionary.get(key)