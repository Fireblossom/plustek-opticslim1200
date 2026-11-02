#!/bin/bash
# Run in the project's Cygwin environment. Source is the pinned upstream tarball.
set -euo pipefail
export PATH=/usr/bin:/bin
script_path="$(cygpath -au "$0")"
script_dir="$(cd "$(dirname "$script_path")" && pwd)"
archive="$(cygpath -au "${1:?Usage: build-cygwin.sh /path/to/backends-1.4.0.tar.gz}")"
echo '9c50ee76e35d98d7ae0cbb97d4c2a3c15663a78fdd74b0ed2bf2fe8e1a73f63a  '"$archive" | sha256sum -c -
mkdir -p /tmp/opticslim-build
tar -xzf "$archive" -C /tmp/opticslim-build
cd /tmp/opticslim-build/backends-1.4.0
patch -p1 < "$script_dir/compat.patch"
printf '1.4.0\n' > .tarball-version
./autogen.sh
# USB-only build: upstream's legacy Windows SCSI path stores HANDLE in int.
# Disable those unused headers instead of enabling a broken 64-bit SCSI path.
ac_cv_header_ntddscsi_h=no ac_cv_header_ddk_ntddscsi_h=no \
./configure --prefix=/tmp/opticslim-runtime \
  BACKENDS='gt68xx test' PRELOADABLE_BACKENDS='gt68xx test' \
  --enable-static --disable-shared --disable-dynamic \
  --disable-locking --without-avahi --without-snmp \
  --without-gphoto2 --without-v4l --disable-nls
# Building all documentation helpers triggers an unrelated upstream tools issue.
# Build the USB engine and CLI required by this package explicitly.
make -j4 -C lib
make -j4 -C sanei
make -j4 -C backend
make -j4 -C frontend scanimage.exe
mkdir -p /tmp/opticslim-runtime/bin
cp frontend/scanimage.exe /tmp/opticslim-runtime/bin/
