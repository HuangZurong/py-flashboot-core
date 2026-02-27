"""Core IoC container decorators."""

def component(cls=None, name: str = None):
    """
    Marks a class as a component, making it eligible for component scanning
    and dependency injection.
    """
    def wrap(c):
        c._is_component = True
        c._component_name = name or c.__name__.lower()
        return c

    return wrap(cls) if cls else wrap

def inject(cls):
    """
    Marks a constructor parameter for dependency injection.
    (This is often implicit in Python and may evolve to be more for type-based
    autowiring configuration).
    """
    # Placeholder for future autowiring logic
    return cls
