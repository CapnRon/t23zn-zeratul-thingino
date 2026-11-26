#!/bin/sh
# Assemble a rootfs staging tree from a thingino target rootfs plus repo overlay.
#
#   build_rootfs_staging.sh THINGINO_ROOTFS STAGING [RAPTOR_V5] [KERNEL_MODULES]
#
# THINGINO_ROOTFS  buildroot target rootfs directory (must contain /bin, /etc)
# STAGING          destination directory (recreated)
# RAPTOR_V5        directory with rvd/rsd/rhd (default: artifacts/raptor-v5)
# KERNEL_MODULES   optional modules tree to copy into /usr/lib/modules
#
# Boot-critical details handled here:
#   - /lib may be a symlink to usr/lib; overlay must merge into real target
#   - stale modules.dep must not be copied from overlay
#   - onvif webapp is trimmed to keep 5 MiB rootfs container fit
set -eu

if [ "$#" -lt 2 ]; then
	echo "usage: $0 THINGINO_ROOTFS STAGING [RAPTOR_V5] [KERNEL_MODULES]" >&2
	exit 2
fi

SRC=$1
DST=$2
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
RAPTOR=${3:-$ROOT/artifacts/raptor-v5}
MODULES=${4:-}

[ -d "$SRC" ] || { echo "ERROR: missing thingino rootfs: $SRC" >&2; exit 1; }
[ -d "$ROOT/rootfs-overlay" ] || { echo "ERROR: missing rootfs-overlay" >&2; exit 1; }

rm -rf "$DST"
mkdir -p "$DST"
cp -a "$SRC"/. "$DST"/

if [ -L "$DST/lib" ]; then
	LIBTARGET=$(readlink -f "$DST/lib" 2>/dev/null || true)
	case "$LIBTARGET" in
		"$DST"/usr/lib|*/"$DST"/usr/lib) LIBDIR="$DST/usr/lib" ;;
		*) LIBDIR="$LIBTARGET" ;;
	esac
else
	LIBDIR="$DST/lib"
fi
mkdir -p "$LIBDIR"

# Copy overlay except /lib and credentials; merge /lib into real libdir.
rsync -a --exclude 'etc/wpa_supplicant.conf' --exclude 'lib' "$ROOT/rootfs-overlay/" "$DST"/
if [ -d "$ROOT/rootfs-overlay/lib" ]; then
	rsync -a "$ROOT/rootfs-overlay/lib/" "$LIBDIR"/
fi

# Prebuilt Raptor v5 binaries.
if [ -d "$RAPTOR" ]; then
	mkdir -p "$DST/usr/bin"
	for bin in rvd rsd rhd; do
		[ -f "$RAPTOR/$bin" ] || continue
		cp -f "$RAPTOR/$bin" "$DST/usr/bin/$bin"
		chmod +x "$DST/usr/bin/$bin"
	done
fi

# Optional kernel modules (keeps depmod output from kernel tree if supplied).
if [ -n "$MODULES" ]; then
	[ -d "$MODULES" ] || { echo "ERROR: missing modules dir: $MODULES" >&2; exit 1; }
	mkdir -p "$DST/usr/lib/modules"
	cp -a "$MODULES"/. "$DST/usr/lib/modules"/
fi

# Keep container below 5 MiB partition.
rm -rf "$DST/var/www/onvif"

echo "staging: $DST"
echo "  source: $SRC"
echo "  raptor: $RAPTOR"
if [ -n "$MODULES" ]; then echo "  modules: $MODULES"; fi
