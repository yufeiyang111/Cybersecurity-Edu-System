"""Scanner registry for current and future language adapters."""
from app.services.scanners.base import BaseLanguageScanner, ProjectProfile, RawFinding
from app.services.scanners.python_scanner import PythonScanner


def get_scanners() -> list[BaseLanguageScanner]:
    return [PythonScanner()]


__all__ = ["BaseLanguageScanner", "ProjectProfile", "RawFinding", "PythonScanner", "get_scanners"]
