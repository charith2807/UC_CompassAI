"""One-way receipt for the single complete held-out test invocation."""
import json
import os
from pathlib import Path

REQUIRED_BASELINES = ('B0', 'B1', 'B2', 'B3')


def require_full_test(baselines):
    if len(baselines) != len(REQUIRED_BASELINES) or set(baselines) != set(REQUIRED_BASELINES):
        raise ValueError('Final test must include B0, B1, B2, and B3 exactly once in one run')


def assert_unused(receipt_path):
    if Path(receipt_path).exists():
        raise FileExistsError('Held-out test receipt already exists; never retry a reserved run')


def reserve(receipt_path, payload):
    path = Path(receipt_path)
    assert_unused(path)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump({**payload, 'status': 'RESERVED'}, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        # A reservation remains used even if writing its details fails.
        raise


def finish(receipt_path, status, **details):
    if status not in ('COMPLETED', 'FAILED'):
        raise ValueError('Receipt status must be COMPLETED or FAILED')
    path = Path(receipt_path)
    receipt = json.loads(path.read_text())
    if receipt.get('status') != 'RESERVED':
        raise ValueError('Only a reserved receipt may be finalized')
    receipt.update(details, status=status)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(receipt, indent=2) + '\n')
    os.replace(temporary, path)
