__all__ = ['load']

import json
import os
import builtins
import atexit
import signal
import sys
from typing import Any, Dict, List, Union, Optional
from weakref import WeakSet, ref, finalize

# Keep track of all active databases to ensure they're saved at exit
_active_dbs = WeakSet()
_finalizers = set()  # Keep finalizers alive until program exit

def _save_db(db_ref):
    """Save a database using its weak reference."""
    db = db_ref()
    if db is not None and db._modified:
        db.save()

def _save_all_dbs():
    """Save all active databases during interpreter shutdown."""
    for db in _active_dbs:
        try:
            db.save()
        except:
            pass

def _signal_handler(signum, frame):
    """Handle interrupts by saving all databases before exiting."""
    _save_all_dbs()
    # Reset to default handler and re-raise
    signal.signal(signum, signal.default_int_handler)
    sys.exit(1)

# Register the cleanup functions
atexit.register(_save_all_dbs)
signal.signal(signal.SIGINT, _signal_handler)   # Handle Ctrl-C
if hasattr(signal, 'SIGTERM'):  # SIGTERM doesn't exist on Windows
    signal.signal(signal.SIGTERM, _signal_handler)  # Handle termination

class _JsonDict(dict):
    """A dictionary subclass that notifies its parent database of changes."""

    def __init__(self, parent_db: 'Database', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._parent_db = parent_db

    def __setitem__(self, key: str, value: Any):
        # Convert nested dicts to _JsonDict
        if isinstance(value, dict) and not isinstance(value, _JsonDict):
            value = _JsonDict(self._parent_db, value)
        elif isinstance(value, list):
            value = _JsonList(self._parent_db, value)
        super().__setitem__(key, value)
        self._parent_db._mark_modified()

    def __delitem__(self, key: str):
        super().__delitem__(key)
        self._parent_db._mark_modified()

class _JsonList(list):
    """A list subclass that notifies its parent database of changes."""

    def __init__(self, parent_db: 'Database', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._parent_db = parent_db
        # Convert any existing nested structures
        for i, value in enumerate(self):
            if isinstance(value, dict):
                self[i] = _JsonDict(parent_db, value)
            elif isinstance(value, list):
                self[i] = _JsonList(parent_db, value)

    def _wrap_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            return _JsonDict(self._parent_db, value)
        elif isinstance(value, list):
            return _JsonList(self._parent_db, value)
        return value

    def append(self, value: Any):
        super().append(self._wrap_value(value))
        self._parent_db._mark_modified()

    def extend(self, values: List[Any]):
        super().extend([self._wrap_value(v) for v in values])
        self._parent_db._mark_modified()

    def __setitem__(self, index: Union[int, slice], value: Any):
        super().__setitem__(index, self._wrap_value(value))
        self._parent_db._mark_modified()

    def __delitem__(self, index: Union[int, slice]):
        super().__delitem__(index)
        self._parent_db._mark_modified()

    def __iadd__(self, other: List[Any]):
        self.extend(other)
        return self

class Database:
    """Main database class that handles file operations and change tracking."""

    def __init__(self, filename: str):
        self._filename = filename
        self._modified = False
        self._inner_container: Optional[Union[_JsonDict, _JsonList]] = None

        # Load existing data or create new
        if os.path.exists(filename):
            with builtins.open(filename, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self._inner_container = _JsonDict(self, data)
                elif isinstance(data, list):
                    self._inner_container = _JsonList(self, data)

        # Register this database instance
        _active_dbs.add(self)
        # Create a finalizer that will be called before module teardown
        _finalizers.add(finalize(self, _save_db, ref(self)))

    def _determine_type(self, operation: str, value: Any = None):
        """Determine and set the type based on first operation."""
        if self._inner_container is not None:
            return

        if operation in ('setitem', 'getitem', 'delitem'):
            self._inner_container = _JsonDict(self, {})
        elif operation in ('append', 'extend', 'iadd'):
            self._inner_container = _JsonList(self, [])

    def _ensure_dict(self):
        if not isinstance(self._inner_container, _JsonDict):
            raise TypeError("This database was initialized as a list and cannot be used as a dictionary")

    def _ensure_list(self):
        if not isinstance(self._inner_container, _JsonList):
            raise TypeError("This database was initialized as a dictionary and cannot be used as a list")

    def __getitem__(self, key):
        self._determine_type('getitem')
        self._ensure_dict()
        return self._inner_container[key]

    def __setitem__(self, key, value):
        self._determine_type('setitem')
        self._ensure_dict()
        self._inner_container[key] = value

    def __delitem__(self, key):
        self._determine_type('delitem')
        self._ensure_dict()
        del self._inner_container[key]

    def append(self, value):
        self._determine_type('append')
        self._ensure_list()
        self._inner_container.append(value)

    def extend(self, values):
        self._determine_type('extend')
        self._ensure_list()
        self._inner_container.extend(values)

    def __iadd__(self, other):
        self._determine_type('iadd')
        self._ensure_list()
        self._inner_container += other
        return self

    def _mark_modified(self):
        """Mark the database as modified."""
        self._modified = True

    def save(self):
        """Explicitly save the database to disk."""
        if self._modified and self._inner_container is not None:
            # Create a temporary file first to avoid corrupting the database
            temp_filename = self._filename + '.tmp'
            try:
                with builtins.open(temp_filename, 'w') as f:
                    json.dump(self._inner_container, f, indent=2)
                # If the write succeeded, rename the temp file to the actual file
                os.replace(temp_filename, self._filename)
                self._modified = False
            except:
                # If anything goes wrong, try to clean up the temp file
                try:
                    os.unlink(temp_filename)
                except:
                    pass
                raise

    # No __del__ method - we use finalizers instead

    def __str__(self) -> str:
        """Delegate string representation to the inner container."""
        if self._inner_container is None:
            return "{}" if self._determine_type('getitem') else "[]"
        return str(self._inner_container)

    def __repr__(self) -> str:
        """Delegate detailed string representation to the inner container."""
        if self._inner_container is None:
            return "{}" if self._determine_type('getitem') else "[]"
        return repr(self._inner_container)

def load(filename: str) -> Database:
    """Open a database file or create a new one."""
    return Database(filename)
