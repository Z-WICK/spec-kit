#!/usr/bin/env bash

# Find unfilled placeholders in .claude/ directory
#
# Usage: ./find-placeholders.sh
#
# Returns: List of files with unfilled placeholders

set -euo pipefail

grep -r '\[.*_.*\]' .claude/ --include='*.md' | grep -v '<!--' | grep -v 'example'
