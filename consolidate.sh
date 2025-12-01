#!/bin/bash
set -e  # Exit on error

echo "=== Starting Consolidation (Flat Structure) ==="

# 1. Create Backup (Outside project root)
echo "[1/5] Creating backup..."
mkdir -p ../claude_sdk_workflow_backup
cp -r . ../claude_sdk_workflow_backup/
echo "Backup created at ../claude_sdk_workflow_backup/"

# 2. Archive Deprecated Mailbox System
echo "[2/5] Archiving deprecated mailbox system..."
mkdir -p archive/mailbox
# Move files if they exist (ignoring errors if already moved)
mv core/mailbox.py archive/mailbox/ 2>/dev/null || true
mv core/mailbox_integration.py archive/mailbox/ 2>/dev/null || true
mv core/mailbox_protocol.py archive/mailbox/ 2>/dev/null || true
mv communication/mailbox_events.py archive/mailbox/ 2>/dev/null || true
mv communication/progress_mailbox.py archive/mailbox/ 2>/dev/null || true
mv communication/session_mailbox.py archive/mailbox/ 2>/dev/null || true

# 3. Promote Production-Ready Examples
echo "[3/5] Upgrading core files from examples..."
# Overwrite core files with the _example.py versions
cp core/config_example.py core/config.py
cp core/agent_client_example.py core/agent_client.py
cp core/type_example.py core/types.py

# 4. Remove Deprecated Executors
echo "[4/5] Removing deprecated executors..."
rm -f executors/oneshot.py
rm -f executors/oneshot_orchestrator.py

# 5. Organize Examples
echo "[5/5] Moving example files to examples/ directory..."
mkdir -p examples
# Move the source examples we just promoted (and others)
mv core/config_example.py examples/ 2>/dev/null || true
mv core/agent_client_example.py examples/ 2>/dev/null || true
mv core/type_example.py examples/ 2>/dev/null || true
mv executors/oneshot_example.py examples/ 2>/dev/null || true
mv executors/orchestrator_example.py examples/ 2>/dev/null || true
mv executors/streaming_example.py examples/ 2>/dev/null || true
mv lib/executor_integration_example.py examples/ 2>/dev/null || true

echo "=== Consolidation Complete ==="
echo "Verifying changes:"
if grep -q "ModelTier" core/config.py; then
    echo "✅ core/config.py successfully upgraded."
else
    echo "❌ core/config.py upgrade failed."
fi

if [ ! -f executors/oneshot.py ]; then
    echo "✅ Deprecated executors removed."
else
    echo "❌ executors/oneshot.py still exists."
fi