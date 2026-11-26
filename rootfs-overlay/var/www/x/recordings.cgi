#!/bin/sh

. /var/www/x/auth.sh
[ "${REQUEST_METHOD:-GET}" = "POST" ] && require_auth

now=$(date +%s)
local_day=$(date +%F)

z=$(date +%z 2>/dev/null)
case "$z" in
	[+-][0-9][0-9][0-9][0-9])
		sign=$(printf '%s' "$z" | cut -c1)
		hh=$(printf '%s' "$z" | cut -c2-3)
		mm=$(printf '%s' "$z" | cut -c4-5)
		offset=$((10#$hh * 3600 + 10#$mm * 60))
		[ "$sign" = "-" ] && offset=$((-offset))
		;;
	*) offset=0 ;;
esac

printf 'Content-Type: application/json\r\n'
printf 'Cache-Control: no-store\r\n'
printf 'Connection: close\r\n'
printf '\r\n'
printf '{"day":"%s","offset":%s,"segments":[' "$local_day" "$offset"

first=1
find /dev/shm/raptor /mnt/mmcblk0p1/raptor -mindepth 2 -maxdepth 2 -type f -name '*.mp4' -exec stat -c '%n|%s' {} + 2>/dev/null |
	LC_ALL=C sort | while IFS='|' read -r path size; do
		dir=${path%/*}
		day=${dir##*/}
		case "$day" in [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) ;; *) continue ;; esac
		name=${path##*/}
		time=${name%.mp4}
		hh=${time%%-*}
		rest=${time#*-}
		mm=${rest%%-*}
		ss=${rest##*-}
		case "$hh$mm$ss" in ''|*[!0-9]*) continue ;; esac
		utc=$(date -u -d "$day $hh:$mm:$ss" +%s 2>/dev/null)
		[ -n "$utc" ] || continue
		if [ "$first" -eq 0 ]; then printf ','; fi
		first=0
		printf '{"path":"%s","utc":%s,"date":"%s","time":"%s","size":%s}' \
			"$path" "$utc" "$day" "$time" "$size"
	done
printf ']}\n'
exit 0
