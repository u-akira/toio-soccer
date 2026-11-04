"""Load implementation modules from either split sources or release bundle."""

import importlib
import os
from pathlib import Path
import sys
import types
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
_release_module = None


def load_target(module_name):
    global _release_module
    if os.environ.get("TOIO_TEST_TARGET", "debug") != "release":
        fake_bleio = types.SimpleNamespace(UUID=lambda value: value)
        with patch.dict(sys.modules, {"_bleio": fake_bleio}):
            return importlib.import_module("lib." + module_name)

    if _release_module is None:
        bundle_path = ROOT / "upload" / "release" / "code.py"
        source = bundle_path.read_text(encoding="utf-8")
        compile(source, str(bundle_path), "exec")
        marker = "# --- APPLICATION ENTRYPOINT ---"
        library_source = source.split(marker, 1)[0]
        _release_module = types.ModuleType("release_bundle")
        fake_bleio = types.SimpleNamespace(UUID=lambda value: value)
        with patch.dict(sys.modules, {"_bleio": fake_bleio}):
            exec(compile(library_source, str(bundle_path), "exec"),
                 _release_module.__dict__)
    return _release_module
