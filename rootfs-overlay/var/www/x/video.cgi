#!/bin/sh

. /var/www/x/auth.sh
require_auth

path="${QUERY_STRING#*path=}"
path="${path%%&*}"
case "$path" in
	/mnt/mmcblk0p1/raptor/*.mp4) ;;
	*) printf 'Status: 400 Bad Request\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nbad path\n'; exit 0 ;;
esac
case "$path" in
	*..*) printf 'Status: 400 Bad Request\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nbad path\n'; exit 0 ;;
esac
if [ ! -f "$path" ]; then
	printf 'Status: 404 Not Found\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nnot found\n'
	exit 0
fi

size=$(stat -c%s "$path" 2>/dev/null) || size=0
[ "$size" -gt 0 ] || { printf 'Status: 404 Not Found\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nempty\n'; exit 0; }

range="${HTTP_RANGE#bytes=}"
if [ "$range" = "$HTTP_RANGE" ] || [ -z "$HTTP_RANGE" ]; then
	start=0
	end=$((size - 1))
	partial=0
else
	start="${range%%-*}"
	end="${range##*-}"
	case "$start" in ''|*[!0-9]*) start=0 ;; esac
	case "$end" in ''|*[!0-9]*) end=$((size - 1)) ;; esac
	[ "$start" -lt "$size" ] || { printf 'Status: 416 Range Not Satisfiable\r\nContent-Range: bytes */%s\r\nConnection: close\r\n\r\n' "$size"; exit 0; }
	[ "$end" -lt "$size" ] || end=$((size - 1))
	partial=1
fi

len=$((end - start + 1))

if [ "$partial" -eq 1 ]; then
	printf 'Status: 206 Partial Content\r\n'
	printf 'Content-Type: video/mp4\r\n'
	printf 'Accept-Ranges: bytes\r\n'
	printf 'Content-Range: bytes %s-%s/%s\r\n' "$start" "$end" "$size"
	printf 'Content-Length: %s\r\n' "$len"
	printf 'Cache-Control: no-store\r\n'
	printf 'Connection: close\r\n'
	printf '\r\n'
else
	printf 'Status: 200 OK\r\n'
	printf 'Content-Type: video/mp4\r\n'
	printf 'Accept-Ranges: bytes\r\n'
	printf 'Content-Length: %s\r\n' "$size"
	printf 'Cache-Control: no-store\r\n'
	printf 'Connection: close\r\n'
	printf '\r\n'
fi

tail -c +$((start + 1)) "$path" | head -c "$len"
exit 0
