"""Offline syntax and translation parity checks; not HA runtime tests."""

import ast
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).parent.parent / "custom_components" / "tuliprox"
PYTHON_FILES = (
    "__init__.py",
    "api.py",
    "config_flow.py",
    "const.py",
    "coordinator.py",
    "sensor.py",
)


class StructureTests(unittest.TestCase):
    def test_active_stream_sensor_reads_endpoint_count(self):
        # Exercise the real property in isolation; this is not an HA runtime test.
        tree = ast.parse((ROOT / "sensor.py").read_text())
        sensor = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "TuliproxSensor"
        )
        native_value = next(
            node
            for node in sensor.body
            if isinstance(node, ast.FunctionDef) and node.name == "native_value"
        )
        native_value.decorator_list = []
        namespace: dict[str, Any] = {"Any": object}
        exec(  # noqa: S102 - execute only the local sensor property under test
            compile(
                ast.Module(body=[native_value], type_ignores=[]), "sensor.py", "exec"
            ),
            namespace,
        )
        entity = SimpleNamespace(
            coordinator=SimpleNamespace(last_update_success=True, data={}),
            entity_description=SimpleNamespace(key="active_user_streams"),
            _username=None,
        )
        for count in (0, 1, None):
            entity.coordinator.data = {"stream_count": count, "active_user_streams": []}
            self.assertEqual(namespace["native_value"](entity), count)
        entity.coordinator.last_update_success = False
        entity.coordinator.data["stream_count"] = 1
        self.assertIsNone(namespace["native_value"](entity))

    def test_python_syntax(self):
        for name in PYTHON_FILES:
            with self.subTest(file=name):
                compile((ROOT / name).read_text(), str(ROOT / name), "exec")

    def test_manifest_and_translations(self):
        manifest = json.loads((ROOT / "manifest.json").read_text())
        self.assertEqual(manifest["domain"], "tuliprox")
        self.assertTrue(manifest["config_flow"])
        strings = json.loads((ROOT / "strings.json").read_text())
        english = json.loads((ROOT / "translations/en.json").read_text())
        danish = json.loads((ROOT / "translations/da.json").read_text())
        self.assertEqual(strings, english)

        def keys(value):
            return {
                key: keys(item) if isinstance(item, dict) else None
                for key, item in value.items()
            }

        self.assertEqual(keys(strings), keys(danish))
        for step in ("user", "reconfigure", "reauth_confirm"):
            self.assertEqual(
                set(strings["config"]["step"][step]["data"]),
                {"url", "username", "password"},
            )

    def test_server_attribute_contract(self):
        tree = ast.parse((ROOT / "sensor.py").read_text())
        attributes = next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "SERVER_ATTRIBUTES"
                for target in node.targets
            )
        )
        self.assertEqual(
            set(attributes),
            {
                "status",
                "version",
                "uptime_secs",
                "cache",
                "active_users",
                "active_user_connections",
                "stream_count",
                "streams",
                "updated_at",
            },
        )
