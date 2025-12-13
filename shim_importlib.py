import sys
if sys.version_info < (3, 10):
    import importlib.metadata
    if not hasattr(importlib.metadata, "packages_distributions"):
        # Monkey patch for Python 3.9
        def packages_distributions():
            # Minimal implementation for langchain/google check
            return {}
        importlib.metadata.packages_distributions = packages_distributions
