"""Cutoff command line. Argument errors and acquisition failures have clean exits."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from cutoff import pipeline
from cutoff.contracts import RUN_MODES
from cutoff.data.s1_pairs import NoValidPair


def coordinates(value, count=4):
    try:
        parts = tuple(float(x.strip()) for x in value.split(','))
        if len(parts) != count:
            raise ValueError
        return parts
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected {count} comma-separated coordinates") from exc


def load_dotenv(path=Path('.env')):
    """Load non-executing KEY=value assignments without overriding environment values."""
    if path.is_file():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            if key.replace('_', '').isalnum():
                os.environ.setdefault(key, value.strip().strip('\"\''))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    load_dotenv()
    # Delegation preserves P2's native command arguments.
    if argv and argv[0] == 'train':
        return subprocess.call([sys.executable, '-m', 'cutoff.ml.train', *argv[1:]])
    if argv and argv[0] == 'eval-kuro':
        native = argv[1:]
        if '--checkpoint' in native:
            native[native.index('--checkpoint')] = '--models'
        if '--strata' in native:
            index = native.index('--strata')
            if index + 1 >= len(native) or native[index + 1] != 'slope':
                print('eval-kuro supports --strata slope (included automatically)', file=sys.stderr)
                return 2
            del native[index:index + 2]
        script = Path(__file__).resolve().parents[2] / 'eval' / 'kuro_eval.py'
        if not script.exists():
            print('eval-kuro requires the repository checkout (eval/kuro_eval.py)', file=sys.stderr)
            return 2
        return subprocess.call([sys.executable, str(script.resolve()), *native])
    parser = argparse.ArgumentParser(description='Flood exposure and access mapping. Educational prototype.')
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('run', help='Create a fresh run folder; report partial runs explicitly')
    run.add_argument('--bbox', required=True, type=coordinates)
    run.add_argument('--event', required=True)
    run.add_argument('--mode', choices=RUN_MODES, default='cached')
    run.add_argument('--model', default='b0')
    run.add_argument('--osm-snapshot')
    run.add_argument('--out', default='outputs')
    run.add_argument('--run-id')
    run.add_argument('--stages', help='Comma-separated dependency-complete subset')
    run.add_argument('--config', type=Path)
    run.add_argument('--cache-dir', type=Path)
    run.add_argument('--flowpath', type=lambda x: coordinates(x, 2))
    mock = sub.add_parser('mock', help='Generate synthetic development data')
    mock.add_argument('out', nargs='?', default='outputs/demo_mock')
    sub.add_parser('train', help='Delegate to cutoff.ml.train')
    sub.add_parser('eval-kuro', help='Delegate to P2 evaluation; use --help for native arguments')
    args = parser.parse_args(argv)
    try:
        if args.command == 'mock':
            from cutoff.mock import make_mock_run
            root = make_mock_run(args.out)
            try:
                from cutoff.report.schema import Results
                pipeline.render_report(Results.model_validate_json((root / 'results.json').read_text()), root)
            except ImportError:
                pass
        else:
            root = pipeline.run(bbox=args.bbox, event_datetime=args.event, mode=args.mode,
                model=args.model, osm_snapshot=args.osm_snapshot, out_root=args.out, run_id=args.run_id,
                stages=args.stages.split(',') if args.stages else None, config=args.config,
                cache_dir=args.cache_dir, flowpath=args.flowpath)
        print(root)
        return 0
    except NoValidPair as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
