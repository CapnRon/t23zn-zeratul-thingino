#!/bin/sh

. /var/www/x/auth.sh
[ "${REQUEST_METHOD:-GET}" = "POST" ] && require_auth

now=$(date +%s)
cutoff=$((now - 5))

entry=$(find /dev/shm/raptor /mnt/mmcblk0p1/raptor -type f -name '*.mp4' -exec stat -c '%Y|%n|%s' {} + 2>/dev/null |
	awk -F'|' -v cutoff="$cutoff" '$1 <= cutoff { print }' |
	sort -t'|' -k1,1nr | head -1)

if [ -z "$entry" ]; then
	entry=$(find /dev/shm/raptor /mnt/mmcblk0p1/raptor -type f -name '*.mp4' -exec stat -c '%Y|%n|%s' {} + 2>/dev/null |
		sort -t'|' -k1,1nr | head -1)
fi

printf 'Content-Type: application/json\r\n'
printf 'Cache-Control: no-store\r\n'
printf 'Connection: close\r\n'
printf '\r\n'

if [ -z "$entry" ]; then
	printf '{"error":"no recording"}\n'
	exit 0
fi

mtime=${entry%%|*}
rest=${entry#*|}
path=${rest%|*}
size=${rest##*|}

printf '{"path":"%s","mtime":%s,"size":%s}\n' "$path" "$mtime" "$size"
exit 0
