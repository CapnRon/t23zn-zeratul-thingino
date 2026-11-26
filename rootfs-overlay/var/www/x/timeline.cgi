#!/bin/sh

. /var/www/x/auth.sh
[ "${REQUEST_METHOD:-GET}" = "POST" ] && require_auth

TZ_FILE=/data/root/etc/clock/timezone
DEFAULT_OFFSET=28800
OFFSET="$DEFAULT_OFFSET"
[ -r "$TZ_FILE" ] && OFFSET=$(cat "$TZ_FILE" 2>/dev/null)
case "$OFFSET" in
	''|*[!0-9-]*) OFFSET="$DEFAULT_OFFSET" ;;
esac

if [ "$REQUEST_METHOD" = "POST" ]; then
	tz="${QUERY_STRING#*tz=}"
	tz="${tz%%&*}"
	case "$tz" in
		''|*[!0-9-]*) ;;
		*)
			if [ "$tz" -ge -50400 ] && [ "$tz" -le 50400 ]; then
				mkdir -p /data/root/etc/clock
				printf '%s\n' "$tz" > "$TZ_FILE"
				OFFSET="$tz"
			fi
			;;
	esac
fi

printf 'Content-Type: application/json\r\n'
printf 'Cache-Control: no-store\r\n'
printf 'Pragma: no-cache\r\n'
printf 'Connection: close\r\n'
printf '\r\n'
printf '{"offset":%s,"segments":[' "$OFFSET"

# One find, one sort, one awk: no per-file fork, no per-file stat.
find /dev/shm/raptor /mnt/mmcblk0p1/raptor -type f -name '*.mp4' -exec stat -c '%n|%s' {} + 2>/dev/null |
	LC_ALL=C sort |
	awk -F '|' '
	BEGIN { first = 1 }
	{
		file = $1
		size = $2
		n = split(file, p, "/")
		day = p[n-1]
		name = p[n]
		time = name
		sub(/\.mp4$/, "", time)
		if (day !~ /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]$/) next
		if (day == "1970-01-01") next
		if (time !~ /^[0-9][0-9]-[0-9][0-9]-[0-9][0-9]$/) next
		gsub(/\\/, "\\\\", file)
		gsub(/"/, "\\\"", file)
		if (!first) printf ","
		first = 0
		printf "{\"path\":\"%s\",\"date\":\"%s\",\"time\":\"%s\",\"size\":%s}", file, day, time, size
	}
	END { }
	'
printf ']}\n'
exit 0
