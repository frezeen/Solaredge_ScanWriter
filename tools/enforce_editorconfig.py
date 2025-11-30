#!/usr/bin/env python3
import os
import sys
import argparse
import fnmatch

# Configuration based on .editorconfig
CONFIG = {
    '*': {
        'end_of_line': '\n',  # lf
        'charset': 'utf-8',
        'trim_trailing_whitespace': True,
        'insert_final_newline': True
    },
    '*.py': {
        'indent_style': 'space',
        'indent_size': 4
    },
    '*.yaml': {
        'indent_style': 'space',
        'indent_size': 2
    },
    '*.yml': {
        'indent_style': 'space',
        'indent_size': 2
    },
    '*.md': {
        'trim_trailing_whitespace': False
    }
}

IGNORE_DIRS = {
    '.git', '__pycache__', '.vscode', 'venv', 'node_modules',
    '.idea', 'build', 'dist', 'egg-info', '.mypy_cache', '.pytest_cache',
    'logs', 'backups', 'cache', 'storage' # Project specific ignores
}

IGNORE_FILES = {
    'package-lock.json', 'yarn.lock', '*.png', '*.jpg', '*.jpeg', '*.gif',
    '*.ico', '*.pdf', '*.zip', '*.tar.gz', '*.whl', '*.pyc', '*.exe', '*.dll'
}

def is_ignored(path):
    parts = path.split(os.sep)
    for part in parts:
        if part in IGNORE_DIRS:
            return True

    filename = os.path.basename(path)
    for pattern in IGNORE_FILES:
        if fnmatch.fnmatch(filename, pattern):
            return True
    return False

def get_config_for_file(filename):
    # Start with default '*' config
    file_config = CONFIG['*'].copy()

    # Apply specific overrides
    for pattern, rules in CONFIG.items():
        if pattern == '*': continue
        if fnmatch.fnmatch(filename, pattern):
            file_config.update(rules)

    return file_config

def check_file(filepath, fix=False):
    filename = os.path.basename(filepath)
    config = get_config_for_file(filename)

    issues = []
    modified = False

    try:
        with open(filepath, 'rb') as f:
            content_bytes = f.read()

        # Check encoding (simplified: try decoding as utf-8)
        try:
            content = content_bytes.decode('utf-8')
        except UnicodeDecodeError:
            return [f"[X] Encoding is not UTF-8"]

        original_content = content
        new_lines = []

        # Split lines preserving endings to detect EOL
        # But for processing we want to work with universal newlines
        lines = content.splitlines(keepends=True)

        # 1. Check EOL and Trailing Whitespace
        for i, line in enumerate(lines):
            original_line = line
            stripped_line = line.rstrip('\r\n')

            # Check EOL
            if '\r\n' in line:
                if not fix: issues.append(f"Line {i+1}: CRLF line ending found")

            # Check Trailing Whitespace
            if config.get('trim_trailing_whitespace'):
                if stripped_line != stripped_line.rstrip():
                    if not fix: issues.append(f"Line {i+1}: Trailing whitespace found")
                    stripped_line = stripped_line.rstrip()

            # Reconstruct line with correct EOL
            new_line = stripped_line + config['end_of_line']
            new_lines.append(new_line)

        # 2. Check Final Newline
        if config.get('insert_final_newline'):
            if not content.endswith('\n') and not content.endswith('\r\n'):
                 if not fix: issues.append("Missing final newline")
                 # If the last line didn't have a newline, the loop above added one to the last element
                 # But if the file was empty or just text without newline, we ensure it
                 if not new_lines or not new_lines[-1].endswith(config['end_of_line']):
                     if new_lines:
                         new_lines[-1] = new_lines[-1].rstrip('\r\n') + config['end_of_line']
                     else:
                         new_lines.append(config['end_of_line'])

        # 3. Check Indentation (Basic check: look at leading spaces)
        indent_size = config.get('indent_size')
        indent_style = config.get('indent_style')

        if indent_style == 'space' and indent_size:
            for i, line in enumerate(new_lines):
                stripped = line.lstrip()
                if not stripped: continue # Skip empty lines

                leading_spaces = len(line) - len(stripped)
                if leading_spaces > 0:
                    if leading_spaces % indent_size != 0:
                         # This is a soft check, hard to fix automatically without breaking logic
                         # So we just warn even in fix mode usually, but here we report
                         issues.append(f"Line {i+1}: Indentation {leading_spaces} is not a multiple of {indent_size}")

        # Apply Fixes
        if fix:
            new_content = "".join(new_lines)
            if new_content != original_content:
                with open(filepath, 'w', encoding='utf-8', newline='') as f:
                    f.write(new_content)
                return [f"[OK] Fixed {filepath}"]
            return []

    except Exception as e:
        return [f"[X] Error processing file: {str(e)}"]

    return issues

def main():
    parser = argparse.ArgumentParser(description='Enforce .editorconfig rules')
    parser.add_argument('--fix', action='store_true', help='Automatically fix issues')
    parser.add_argument('--path', default='.', help='Root directory to scan')
    args = parser.parse_args()

    print(f"Scanning {os.path.abspath(args.path)}...")
    print(f"Mode: {'FIX' if args.fix else 'CHECK'}")

    total_issues = 0
    files_checked = 0

    for root, dirs, files in os.walk(args.path):
        # Filter directories in-place
        dirs[:] = [d for d in dirs if not is_ignored(os.path.join(root, d))]

        for file in files:
            filepath = os.path.join(root, file)
            if is_ignored(filepath):
                continue

            files_checked += 1
            issues = check_file(filepath, fix=args.fix)

            if issues:
                print(f"\n[FILE] {filepath}")
                for issue in issues:
                    print(f"  {issue}")
                    if not args.fix: total_issues += 1

    print(f"\nSummary:")
    print(f"Files checked: {files_checked}")
    if args.fix:
        print("Fixes applied.")
    else:
        print(f"Issues found: {total_issues}")
        if total_issues > 0:
            sys.exit(1)

if __name__ == '__main__':
    main()
