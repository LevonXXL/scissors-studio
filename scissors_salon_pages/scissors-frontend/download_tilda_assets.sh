#!/usr/bin/env bash
# Скачивает все картинки, найденные в дампе сайта на static.tildacdn.com,
# в папку ./tilda_assets — с сохранением исходных имён файлов (по хэшу
# tild-папки, чтобы не было коллизий одинаковых имён вроде "1.png").
#
# Запускать на своей машине (у песочницы Claude нет доступа к tildacdn.com).
# Нужен: логотип и favicon — 2 самых важных файла, они первые в списке.

set -e
OUT_DIR="./tilda_assets"
mkdir -p "$OUT_DIR"

while IFS= read -r url; do
  [ -z "$url" ] && continue
  # Папка = tild-хэш из пути (уникален для каждого файла в Tilda CDN)
  hash_dir=$(echo "$url" | sed -E 's#https://static\.tildacdn\.com/([^/]+)/.*#\1#')
  filename=$(basename "$url")
  mkdir -p "$OUT_DIR/$hash_dir"
  echo "Скачиваю: $filename"
  curl -sL "$url" -o "$OUT_DIR/$hash_dir/$filename"
done < tilda_assets_urls.txt

echo "Готово. Файлы — в $OUT_DIR/"
