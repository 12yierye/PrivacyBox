#!/bin/bash
# PrivacyBox macOS Package Builder
# Produces a .pkg installer with customizable install & data directories
#
# Prerequisites:
#   - PyInstaller build must exist in dist/PrivacyBox.app or dist/PrivacyBox/
#   - macOS with pkgbuild and productbuild (included with Xcode cmdline tools)
#
# Usage:
#   bash installer/macos/build_pkg.sh
#   INSTALL_PATH=/Applications DATA_PATH="$HOME/PrivacyBoxData" bash installer/macos/build_pkg.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
VERSION="${VERSION:-$(python3 -c "import sys; sys.path.insert(0, '$PROJECT_DIR'); from privacybox import __version__; print(__version__)" 2>/dev/null || echo "0.1.0")}"
IDENTIFIER="dev.privacybox.pkg"
INSTALL_PATH="${INSTALL_PATH:-/Applications}"
DATA_PATH="${DATA_PATH:-$HOME/Library/Application Support/PrivacyBox}"

BUILD_DIR="$PROJECT_DIR/installer/macos/build"
PKG_OUTPUT="$PROJECT_DIR/installer/macos/output/PrivacyBox-$VERSION.pkg"
POSTINSTALL_SCRIPT="$BUILD_DIR/postinstall"
APP_BUNDLE="$PROJECT_DIR/dist/PrivacyBox.app"

mkdir -p "$BUILD_DIR"
mkdir -p "$(dirname "$PKG_OUTPUT")"

# Verify source exists
if [ ! -d "$APP_BUNDLE" ] && [ ! -f "$PROJECT_DIR/dist/PrivacyBox" ]; then
    # Fallback to the standard PyInstaller dist layout
    if [ -d "$PROJECT_DIR/dist/PrivacyBox" ]; then
        echo "Creating .app bundle from dist/PrivacyBox..."
        APP_BUNDLE="$BUILD_DIR/PrivacyBox.app"
        mkdir -p "$APP_BUNDLE/Contents/MacOS"
        mkdir -p "$APP_BUNDLE/Contents/Resources"
        cp -r "$PROJECT_DIR/dist/PrivacyBox"/* "$APP_BUNDLE/Contents/MacOS/"
        cat > "$APP_BUNDLE/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>PrivacyBox</string>
    <key>CFBundleIdentifier</key>
    <string>dev.privacybox</string>
    <key>CFBundleName</key>
    <string>PrivacyBox</string>
    <key>CFBundleVersion</key>
    <string>$VERSION</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>11.0</string>
</dict>
</plist>
PLIST
        chmod +x "$APP_BUNDLE/Contents/MacOS/PrivacyBox"
    else
        echo "ERROR: No PyInstaller build found in dist/. Run 'python build.py' first."
        exit 1
    fi
fi

# Create postinstall script that writes install.json
cat > "$POSTINSTALL_SCRIPT" <<'POSTINSTALL'
#!/bin/bash
# PrivacyBox postinstall — writes install-time configuration
set -euo

INSTALL_PATH="$2"
DATA_PATH="${DATA_PATH:-$HOME/Library/Application Support/PrivacyBox}"

# Write install.json
INSTALL_JSON_DIR="$HOME/Library/Application Support/privacybox"
mkdir -p "$INSTALL_JSON_DIR"

cat > "$INSTALL_JSON_DIR/install.json" <<JSON
{
  "install_path": "$INSTALL_PATH",
  "data_dir": "$DATA_PATH",
  "install_version": "${VERSION:-0.1.0}"
}
JSON

# Create data directory if it doesn't exist
mkdir -p "$DATA_PATH"

# Symlink the binary into PATH-friendly location
mkdir -p "$HOME/.local/bin"
ln -sf "$INSTALL_PATH/PrivacyBox.app/Contents/MacOS/PrivacyBox" "$HOME/.local/bin/privacybox"

echo "PrivacyBox installed successfully."
echo "  Install path: $INSTALL_PATH"
echo "  Data directory: $DATA_PATH"
echo "  Binary linked: ~/.local/bin/privacybox"
POSTINSTALL
chmod +x "$POSTINSTALL_SCRIPT"

# Build the component package
echo "Building component package..."
pkgbuild \
    --root "$APP_BUNDLE" \
    --install-location "$INSTALL_PATH/PrivacyBox.app" \
    --scripts "$BUILD_DIR" \
    --identifier "$IDENTIFIER" \
    --version "$VERSION" \
    --ownership recommended \
    "$PKG_OUTPUT"

echo "macOS package created: $PKG_OUTPUT"
echo ""
echo "To install interactively with custom data directory:"
echo "  open '$PKG_OUTPUT'"
echo ""
echo "To install silently:"
echo "  sudo installer -pkg '$PKG_OUTPUT' -target /"
