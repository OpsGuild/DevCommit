from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("devcommit")
except PackageNotFoundError:
    # Fallback if package is not installed (e.g. during dev)
    __version__ = "0.0.0-dev"
