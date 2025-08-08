from django import template

register = template.Library()

@register.filter(name='endswith')
def endswith(value, arg):
    """检查字符串是否以指定后缀结尾"""
    if isinstance(value, str):
        return value.endswith(arg)
    return False

@register.filter(name='get_item')
def get_item(dictionary, key):
    """从字典中获取指定键的值"""
    return dictionary.get(key)
    