#!/bin/bash
echo "=== SAFETY CHECK ==="
echo ""
echo "1. Git Status:"
git status --short
echo ""
echo "2. gerald_bridge.py syntax check:"
python3 -m py_compile gerald_bridge.py && echo "✅ gerald_bridge.py compiles successfully" || echo "❌ gerald_bridge.py has syntax errors"
echo ""
echo "3. Gerald service status:"
systemctl status gerald.service --no-pager | head -20
echo ""
echo "4. gerald_bridge.py file integrity:"
wc -l gerald_bridge.py
tail -5 gerald_bridge.py
