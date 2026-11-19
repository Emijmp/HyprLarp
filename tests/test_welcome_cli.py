"""Opening the assistant also works when standalone settings already exist."""

import importlib.machinery
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class WelcomeCliTests(unittest.TestCase):
  def setUp(self):
    loader = importlib.machinery.SourceFileLoader('hyprlarp_welcome_cli_test', str(ROOT / 'bin/hyprlarp'))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    self.cli = importlib.util.module_from_spec(spec)
    loader.exec_module(self.cli)

  def test_existing_standalone_window_receives_the_requested_view(self):
    for command in ['welcome', 'settings']:
      calls = []
      def invoke(argv, **options):
        calls.append(argv)
        # Simulate a running standalone app and no shell instance. Spawning
        # --no-duplicate again would lose the requested change of view.
        return SimpleNamespace(returncode=0 if argv[2] == str(ROOT / 'settings.qml') else 1,
          stderr='no shell instance', stdout='')
      with self.subTest(command=command), patch('sys.argv', ['hyprlarp', command]), \
          patch.object(self.cli, 'runtime', return_value='qs'), \
          patch('backend.icons.choose_icon_theme', return_value=''), \
          patch.object(self.cli.subprocess, 'run', side_effect=invoke), \
          patch.object(self.cli.os, 'execvpe') as execute:
        self.assertEqual(self.cli.main(), 0)
        execute.assert_not_called()
        self.assertEqual([argv[2] for argv in calls], [str(ROOT / 'shell.qml'), str(ROOT / 'settings.qml')])
        self.assertTrue(all(argv[-1] == command for argv in calls))

  def test_standalone_fallback_sets_the_requested_initial_view(self):
    for command in ['welcome', 'settings']:
      with self.subTest(command=command), patch('sys.argv', ['hyprlarp', command]), \
          patch.object(self.cli, 'runtime', return_value='qs'), \
          patch('backend.icons.choose_icon_theme', return_value=''), \
          patch.object(self.cli, 'ipc', return_value=False), \
          patch.dict(os.environ, {'HYPRLARP_WELCOME_ONLY': '1'}), \
          patch.object(self.cli.os, 'execvpe') as execute:
        self.assertEqual(self.cli.main(), 0)
        arguments, environment = execute.call_args.args[1:]
        self.assertEqual(arguments, ['qs', '--path', str(ROOT / 'settings.qml'), '--no-duplicate'])
        self.assertEqual(environment['HYPRLARP_SETTINGS_ONLY'], '1')
        self.assertEqual(environment.get('HYPRLARP_WELCOME_ONLY'), '1' if command == 'welcome' else None)
