# JawaDB

A simple persistent JSON database for Python that acts like a regular dictionary or list.

## Installation

```bash
pip install jawadb
```

## Usage

```python
import jawadb

# Use as dictionary
db = jawadb.load("mydata.json")
db["key"] = "value"
db["nested"] = {"foo": "bar"}
# File is automatically saved when db is garbage collected

# Use as list
db = jawadb.load("mylist.json")
db += ["item1", "item2"]
db.append("item3")
# File is automatically saved
```

## Features

- Automatic persistence to JSON file
- Use as either dictionary or list (type is determined by first operation)
- Handles nested structures
- Atomic file writes
- Saves on program exit, Ctrl-C, and garbage collection
- Type hints included

## License

MIT License