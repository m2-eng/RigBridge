#!/usr/bin/env python3
"""
RigBridge Test Suite Runner

Zentrale Python-Schnittstelle für alle Tests.
Plattformunabhängig (Windows, Linux, macOS).

Verwendung:
    python run_tests.py                    # Alle Tests (inkl. Real Hardware)
    python run_tests.py --level pr         # PR-Modus (ohne Real Hardware)
    python run_tests.py --level protocol   # Nur Stufe 1
    python run_tests.py --level full-hierarchy  # Alle Stufen mit Fortschritt
    python run_tests.py --help             # Hilfe
"""

import subprocess
import sys
import argparse
from pathlib import Path


class Colors:
    """ANSI Farben für Terminal-Output."""
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

    @staticmethod
    def disable_on_windows():
        """Deaktiviere Farben auf Windows."""
        if sys.platform == 'win32':
            for attr in dir(Colors):
                if not attr.startswith('_'):
                    setattr(Colors, attr, '')


def print_header():
    """Drucke Header."""
    print(f"{Colors.BLUE}╔════════════════════════════════════════════════════════════════╗{Colors.RESET}")
    print(f"{Colors.BLUE}║         RigBridge Test Suite                                  ║{Colors.RESET}")
    print(f"{Colors.BLUE}╚════════════════════════════════════════════════════════════════╝{Colors.RESET}")
    print()


def run_pytest(level, verbose=False, fail_fast=False, coverage=False):
    """Führe pytest mit verschiedenen Levels aus."""

    pytest_args = []

    # Verbosity
    if verbose:
        pytest_args.append('-vv')
        pytest_args.append('--tb=long')
    else:
        pytest_args.append('-v')
        pytest_args.append('--tb=short')

    # Fail Fast
    if fail_fast:
        pytest_args.append('-x')

    # Coverage
    if coverage:
        pytest_args.extend(['--cov=src', '--cov-report=html', '--cov-report=term', '--cov-report=xml'])

    # Verschiedene Test-Level
    test_configs = {
        'protocol': {
            'description': 'Stufe 1 - YAML-Protokoll Parser Tests',
            'paths': ['tests/backend/test_1_protocol/'],
            'markers': 'protocol'
        },
        'commands': {
            'description': 'Stufe 1 & 2 - Protokoll + Befehlsaufbau Tests',
            'paths': ['tests/backend/test_1_protocol/', 'tests/backend/test_2_commands/'],
            'markers': 'protocol or commands'
        },
        'simulation': {
            'description': 'Stufe 1, 2, 3 - Bis USB-Simulation',
            'paths': ['tests/backend/test_1_protocol/', 'tests/backend/test_2_commands/', 'tests/backend/test_3_usb_simulation/'],
            'markers': 'not usb_real'
        },
        'integration': {
            'description': 'Komponenten-Integration Tests',
            'paths': ['tests/backend/test_integration.py'],
            'markers': 'integration'
        },
        'real': {
            'description': 'UUID Real-Hardware Tests (IC-905 erforderlich)',
            'paths': ['tests/backend/test_4_usb_real_hardware/'],
            'markers': 'usb_real or manual'
        },
        'all': {
            'description': 'Alle Tests (inkl. Real Hardware)',
            'paths': ['tests/backend/'],
            'markers': ''
        },
        'pr': {
            'description': 'PR-Tests (ohne Real Hardware)',
            'paths': ['tests/backend/'],
            'markers': 'not usb_real'
        },
    }

    if level == 'full-hierarchy':
        # Hierarchische Ausführung mit Zwischenergebnissen
        print(f"{Colors.YELLOW}Starte: VOLLSTÄNDIGE Test-Hierarchie (ohne Real Hardware){Colors.RESET}\n")

        levels_to_run = ['protocol', 'commands', 'simulation', 'integration']

        for test_level in levels_to_run:
            config = test_configs[test_level]
            print(f"{Colors.BLUE}  → {config['description']}...{Colors.RESET}")

            cmd = ['python', '-m', 'pytest'] + config['paths']
            if config.get('markers'):
                cmd += ['-m', config['markers']]
            cmd += pytest_args
            result = subprocess.run(cmd)

            if result.returncode != 0:
                print(f"\n{Colors.RED}✗ Tests fehlgeschlagen{Colors.RESET}")
                return False

            print()

        print(f"{Colors.GREEN}✓ Alle Test-Stufen erfolgreich!{Colors.RESET}")
        return True

    else:
        # Standard-Ausführung
        if level not in test_configs:
            print(f"{Colors.RED}❌ Unbekanntes Test-Level: {level}{Colors.RESET}")
            return False

        config = test_configs[level]
        print(f"{Colors.YELLOW}Starte: {config['description']}{Colors.RESET}\n")

        cmd = ['python', '-m', 'pytest'] + config['paths']
        if config.get('markers'):
            cmd += ['-m', config['markers']]
        cmd += pytest_args
        result = subprocess.run(cmd)

        return result.returncode == 0


def main():
    """Hauptfunktion."""
    parser = argparse.ArgumentParser(
        description='RigBridge Test Suite Runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Beispiele:
    python run_tests.py                    # Alle Tests (inkl. Real Hardware)
    python run_tests.py -l pr              # PR-Tests (ohne Real Hardware)
  python run_tests.py -l protocol        # Nur Stufe 1
  python run_tests.py -l full-hierarchy  # Alle Stufen der Reihe nach
  python run_tests.py -l real            # Real Hardware Tests (IC-905 erforderlich)
  python run_tests.py -l all -v          # Alle Tests mit Verbose Output
  python run_tests.py -l protocol --coverage  # Mit Coverage Report
        '''
    )

    parser.add_argument(
        '-l', '--level',
        choices=['protocol', 'commands', 'simulation', 'integration', 'real', 'all', 'pr', 'full-hierarchy'],
        default='all',
        help='Test-Level (default: all)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose Output'
    )
    parser.add_argument(
        '-f', '--fail-fast',
        action='store_true',
        help='Stoppe bei erstem Fehler'
    )
    parser.add_argument(
        '-c', '--coverage',
        action='store_true',
        help='Erzeuge Coverage Report'
    )

    args = parser.parse_args()

    # Farben auf Windows deaktivieren (optional)
    if sys.platform == 'win32' and not sys.stdout.isatty():
        Colors.disable_on_windows()

    print_header()

    success = run_pytest(
        level=args.level,
        verbose=args.verbose,
        fail_fast=args.fail_fast,
        coverage=args.coverage
    )

    print()
    if success:
        print(f"{Colors.GREEN}✓ Tests erfolgreich!{Colors.RESET}")
        return 0
    else:
        print(f"{Colors.RED}✗ Tests fehlgeschlagen{Colors.RESET}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
