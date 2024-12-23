__all__ = ['load']

import atexit
import json
import os
import signal
import sys
from typing import Any
from weakref import WeakSet, finalize, ref

# Keep track of all active databases to check at exit
_active_dbs = WeakSet()
_finalizers = set()

def _save_db(db_ref):
    db = db_ref()
    if db is not None:
        db.save()

def _save_all_dbs():
    for db in _active_dbs:
        try:
            db.save()
        except:
            pass

def _signal_handler(signum, frame):
    _save_all_dbs()
    signal.signal(signum, signal.default_int_handler)
    sys.exit(1)

# Register the cleanup functions
atexit.register(_save_all_dbs)
signal.signal(signal.SIGINT, _signal_handler)   # Handle Ctrl-C
if hasattr(signal, 'SIGTERM'):  # SIGTERM doesn't exist on Windows
    signal.signal(signal.SIGTERM, _signal_handler)  # Handle termination

class Database:
    def __init__(self, filename):
        self._filename = filename
        self._data = None
        self._original = None

        if os.path.exists(filename):
            with open(filename, 'r') as f:
                self._data = json.load(f)
                self._original = json.dumps(self._data, sort_keys=True)

        _active_dbs.add(self)
        _finalizers.add(finalize(self, _save_db, ref(self)))

    def __str__(self):
        return str(self._data) if self._data is not None else "[}"

    def __repr__(self):
        return repr(self._data) if self._data is not None else "[}"

    def __getattr__(self, name):
        """Delegate unknown attributes/methods to the underlying container."""
        if self._data is None:
            possible_types = [typ for typ in [dict, list] if getattr(typ, name, None) is not None]
            if len(possible_types) == 1:
                self._data = possible_types[0]()

        return getattr(self._data, name)

    def save(self):
        if self._data is None:
            return

        current = json.dumps(self._data, sort_keys=True)
        if current != self._original:
            temp_filename = self._filename + '.tmp'
            try:
                with open(temp_filename, 'w') as f:
                    json.dump(self._data, f, indent=2)
                os.replace(temp_filename, self._filename)
                self._original = current
            except Exception as e:
                raise type(e)(f"{str(e)} (temporary file at {temp_filename})")

def load(filename):
    return Database(filename)
