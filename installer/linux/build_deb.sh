#!/bin/bash
# PrivacyBox Linux Package Builder
# Produces .deb + optional .rpm / AppImage from the PyInstaller build
#
# Prerequisites:
#   - fpm (gem install fpm) or apt-get install ruby ruby-dev && gem install fpm
#   - PyInstaller build must exist in dist/PrivacyBox/
#
# Usage:
#   bash installer/linux/build_deb.sh
#   VERSION=0.2.0 bash installer/linux/build_deb.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
VERSION="${VERSION:-$(python3 -c "import sys; sys.path.insert(0, '$PROJECT_DIR'); from privacybox import __version__; print(__version__)" 2>/dev/null || echo "0.1.0")}"

BUILD_DIR="$PROJECT_DIR/installer/linux/build"
OUTPUT_DIR="$PROJECT_DIR/installer/linux/output"
PKG_NAME="privacybox"
DESCRIPTION="Natural language self-deployment engine"
MAINTAINER="PrivacyBox Team <team@privacybox.dev>"
URL="https://privacybox.dev"

mkdir -p "$BUILD_DIR" "$OUTPUT_DIR"

# Verify PyInstaller build exists
if [ ! -d "$PROJECT_DIR/dist/PrivacyBox" ] && [ ! -f "$PROJECT_DIR/dist/PrivacyBox" ]; then
    echo "ERROR: No PyInstaller build found in dist/. Run 'python build.py' first."
    exit 1
fi

# Prepare package root
PKG_ROOT="$BUILD_DIR/pkg-root"
rm -rf "$PKG_ROOT"
mkdir -p "$PKG_ROOT/usr/lib/privacybox"
mkdir -p "$PKG_ROOT/usr/bin"

# Copy PyInstaller build
if [ -d "$PROJECT_DIR/dist/PrivacyBox" ]; then
    cp -r "$PROJECT_DIR/dist/PrivacyBox"/* "$PKG_ROOT/usr/lib/privacybox/"
elif [ -f "$PROJECT_DIR/dist/PrivacyBox" ]; then
    cp "$PROJECT_DIR/dist/PrivacyBox" "$PKG_ROOT/usr/lib/privacybox/PrivacyBox"
fi

chmod +x "$PKG_ROOT/usr/lib/privacybox/PrivacyBox"

# Create wrapper script for PATH
cat > "$PKG_ROOT/usr/bin/privacybox" <<'WRAPPER'
#!/bin/bash
exec /usr/lib/privacybox/PrivacyBox "$@"
WRAPPER
chmod +x "$PKG_ROOT/usr/bin/privacybox"

# Create postinst script
cat > "$BUILD_DIR/postinst" <<'POSTINST'
#!/bin/bash
set -e

# Write install.json for this user
for HOME_DIR in /root /home/*; do
    USER="$(basename "$HOME_DIR")"
    [ "$USER" = "*" ] && continue
    [ "$USER" = "." ] && continue
    [ "$USER" = ".." ] && continue

    XDG_CONFIG="${XDG_CONFIG_HOME:-$HOME_DIR/.config}"
    INSTALL_JSON_DIR="$XDG_CONFIG/privacybox"
    mkdir -p "$INSTALL_JSON_DIR"

    cat > "$INSTALL_JSON_DIR/install.json" <<JSON
{
  "install_path": "/usr/lib/privacybox",
  "data_dir": "$HOME_DIR/.local/share/privacybox",
  "install_version": "${VERSION:-0.1.0}"
}
JSON
    mkdir -p "$HOME_DIR/.local/share/privacybox"
done

echo "PrivacyBox installed. Run 'privacybox --help' to get started."
POSTINST
chmod +x "$BUILD_DIR/postinst"

# Create prerm script
cat > "$BUILD_DIR/prerm" <<'PRERM'
#!/bin/bash
set -e
echo "Removing PrivacyBox configuration..."
# Don't remove data directory — user data is precious
PRERM
chmod +x "$BUILD_DIR/prerm"

# Build .deb with fpm
echo "Building .deb package..."
fpm \
    --input-type dir \
    --output-type deb \
    --name "$PKG_NAME" \
    --version "$VERSION" \
    --description "$DESCRIPTION" \
    --maintainer "$MAINTAINER" \
    --url "$URL" \
    --license "MIT" \
    --vendor "PrivacyBox Team" \
    --depends "docker-ce" \
    --deb-no-default-config-files \
    --after-install "$BUILD_DIR/postinst" \
    --before-remove "$BUILD_DIR/prerm" \
    --package "$OUTPUT_DIR/privacybox_${VERSION}_amd64.deb" \
    -C "$PKG_ROOT" \
    .

echo ""
echo "Building .rpm package..."
fpm \
    --input-type dir \
    --output-type rpm \
    --name "$PKG_NAME" \
    --version "$VERSION" \
    --description "$DESCRIPTION" \
    --maintainer "$MAINTAINER" \
    --url "$URL" \
    --license "MIT" \
    --vendor "PrivacyBox Team" \
    --depends "docker" \
    --after-install "$BUILD_DIR/postinst" \
    --before-remove "$BUILD_DIR/prerm" \
    --package "$OUTPUT_DIR/privacybox-${VERSION}-1.x86_64.rpm" \
    -C "$PKG_ROOT" \
    .

echo ""
echo "Linux packages created:"
ls -lh "$OUTPUT_DIR"/*.deb "$OUTPUT_DIR"/*.rpm 2>/dev/null || true
echo ""
echo "To install the .deb package:"
echo "  sudo dpkg -i $OUTPUT_DIR/privacybox_${VERSION}_amd64.deb"
