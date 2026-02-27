"""Bean lifecycle management and decorators."""

def post_construct(func):
    """Decorator to mark a method to be called after bean initialization."""
    func._is_post_construct = True
    return func

def pre_destroy(func):
    """Decorator to mark a method to be called before bean destruction."""
    func._is_pre_destroy = True
    return func
