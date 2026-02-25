# utilities/ini_parser.py

"""
Author: Andriy Nych (nych.andriy@gmail.com)
Version: 733341.4155741782200
Translated to Python by Ricardo Rocha

INI = ini2dict(filename)

This function parses an INI file and returns it as a nested Python dictionary with section names and keys as fields.

- Sections are returned as dictionary keys.
- Keys within each section are lowercased and sanitized.
- Lines starting with ';' or '#' are ignored.
- Orphan key-value pairs (before any section header) are placed at the root level.
"""

import re

def ini2dict(filename):
    result = {}
    current_section = None

    def clean_key(key):
        return re.sub(r'\W|^(?=\d)', '_', key.strip().lower())

    def clean_value(val):
        return val.strip().lstrip('=').strip()

    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(';') or line.startswith('#'):
                continue
            if line.startswith('[') and line.endswith(']'):
                section_name = clean_key(line[1:-1])
                result[section_name] = {}
                current_section = section_name
            else:
                if '=' in line:
                    key, val = line.split('=', 1)
                    key = clean_key(key)
                    val = clean_value(val)
                    if current_section:
                        result[current_section][key] = val
                    else:
                        result[clean_key(key)] = val
    return result
