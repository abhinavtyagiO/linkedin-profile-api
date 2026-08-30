"""LinkedIn profile API package."""

from .flight import FlightDecodeError, FlightLimits, FlightStream

__version__ = "0.1.0"

__all__ = ["FlightDecodeError", "FlightLimits", "FlightStream", "__version__"]
