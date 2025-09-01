#!/usr/bin/env bash
set -Eeuo pipefail

BASE="${BASE:-http://127.0.0.1:8000}"
: "${TOKEN:?TOKEN is required}"
AUTHZ="Authorization: Bearer ${TOKEN}"

IMAGES=(
  "/static/demo/img_1_1.jpg"
  "/static/demo/img_4_5.jpg"
  "/static/demo/img_9_16.jpg"
)

TITLE="Demo"
PRICE="19.90€"
OLDP="29.90€"
CTA="ΑΓΟΡΑ ΤΩΡΑ"
LOGO="/static/demo/logo.png"

# CSV headers
echo "ratio,preview_status,commit_status,preview_url,committed_url,err" > smoke_images.csv
echo "status,frame_count,sheet_url,first_frame_url,commit_status,committed_url,err" > smoke_carousel.csv
echo "status,mode,mp4_url,poster_url,commit_status,committed_url,err" > smoke_video.csv
echo "kind,status,detail" > smoke_all.csv

jqshort='-r'

render_one () {
  local ratio="$1" img="$2"
  local payload
  payload=$(jq -nc \
    --arg ratio "$ratio" \
    --arg img "$img" \
    --arg title "$TITLE" \
    --arg price "$PRICE" \
    --arg oldp "$OLDP" \
    --arg cta "$CTA" \
    --arg logo "$LOGO" '
    {
      use_renderer:true,
      ratio:$ratio,
      mode:"normal",
      image_url:$img,
      mapping:{
        title:$title,
        price:$price,
        old_price:$oldp,
        cta:$cta,
        logo_url:$logo,
        discount_badge:true
      }
    }')
  local R J PURL PID CSTAT CURL STAT ERR
  R=$(curl -s -X POST "$BASE/previews/render" -H "$AUTHZ" -H "Content-Type: application/json" -d "$payload")
  J=$(echo "$R" | jq $jqshort '.status?, .preview_url?')
  STAT=$(echo "$R" | jq -r '.status // "ok"')
  PURL=$(echo "$R" | jq -r '.preview_url // ""')
  if [ -n "$PURL" ] && [ "$PURL" != "null" ]; then
    PID=$(echo "$PURL" | sed -E 's#^.*/(prev_[0-9]+).*#\1#')
    CSTAT=$(curl -s -X POST "$BASE/previews/commit" -H "$AUTHZ" -H "Content-Type: application/json" \
      -d "{\"preview_id\":\"$PID\"}")
    CURL=$(echo "$CSTAT" | jq -r '.committed_url // ""')
    if [ -n "$CURL" ] && [ "$CURL" != "null" ]; then
      echo "$ratio,ok,ok,$PURL,$CURL," >> smoke_images.csv
      echo "image,ok,$ratio" >> smoke_all.csv
      return 0
    else
      ERR=$(echo "$CSTAT" | jq -r '.detail // .error // ""')
      echo "$ratio,ok,ERR,$PURL,,$ERR" >> smoke_images.csv
      echo "image,ERR,commit fail $ratio" >> smoke_all.csv
      return 1
    fi
  else
    ERR=$(echo "$R" | jq -r '.detail // .error // ""')
    echo "$ratio,ERR,,,$ERR" >> smoke_images.csv
    echo "image,ERR,render fail $ratio" >> smoke_all.csv
    return 1
  fi
}

# 1:1, 4:5, 9:16
render_one "1:1"   "${IMAGES[0]}" || true
render_one "4:5"   "${IMAGES[1]}" || true
render_one "9:16"  "${IMAGES[2]}" || true

# Carousel (3 frames)
CAR_PAYLOAD=$(jq -nc --arg a "${IMAGES[0]}" --arg b "${IMAGES[1]}" --arg c "${IMAGES[2]}" '
{ mode:"carousel", images:[{image:$a},{image:$b},{image:$c}] }')
RC=$(curl -s -X POST "$BASE/previews/render" -H "$AUTHZ" -H "Content-Type: application/json" -d "$CAR_PAYLOAD")
CS=$(echo "$RC" | jq -r '.status // "ok"')
SHEET=$(echo "$RC" | jq -r '.sheet_url // .preview_url // ""')
FF=$(echo "$RC" | jq -r '.frames[0] // ""')
if [ -n "$SHEET" ]; then
  PID=$(echo "$SHEET" | sed -E 's#^.*/(prev_[0-9]+).*#\1#')
  CC=$(curl -s -X POST "$BASE/previews/commit" -H "$AUTHZ" -H "Content-Type: application/json" \
    -d "{\"preview_id\":\"$PID\"}")
  CURL=$(echo "$CC" | jq -r '.committed_url // ""')
  if [ -n "$CURL" ]; then
    echo "ok,3,$SHEET,$FF,ok,$CURL," >> smoke_carousel.csv
    echo "carousel,ok,$CURL" >> smoke_all.csv
  else
    ERR=$(echo "$CC" | jq -r '.detail // .error // ""')
    echo "ok,3,$SHEET,$FF,ERR,,$ERR" >> smoke_carousel.csv
    echo "carousel,ERR,commit fail" >> smoke_all.csv
  fi
else
  ERR=$(echo "$RC" | jq -r '.detail // .error // ""')
  echo "ERR,0,, ,ERR,,$ERR" >> smoke_carousel.csv
  echo "carousel,ERR,render fail" >> smoke_all.csv
fi

# Video (6s @30fps)
VID_PAYLOAD=$(jq -nc --arg a "${IMAGES[0]}" --arg b "${IMAGES[1]}" '
{ mode:"video", ratio:"4:5", images:[{image:$a},{image:$b}], meta:{fps:30, duration_sec:6} }')
RV=$(curl -s -X POST "$BASE/previews/render" -H "$AUTHZ" -H "Content-Type: application/json" -d "$VID_PAYLOAD")
VS=$(echo "$RV" | jq -r '.status // "ok"')
MP4=$(echo "$RV" | jq -r '.preview_url // .mp4_url // ""')
if [ -n "$MP4" ]; then
  PID=$(echo "$MP4" | sed -E 's#^.*/(prev_[0-9]+).*#\1#')
  VC=$(curl -s -X POST "$BASE/previews/commit" -H "$AUTHZ" -H "Content-Type: application/json" \
    -d "{\"preview_id\":\"$PID\"}")
  CURL=$(echo "$VC" | jq -r '.committed_url // ""')
  if [ -n "$CURL" ]; then
    echo "ok,video,$MP4,,ok,$CURL," >> smoke_video.csv
    echo "video,ok,$CURL" >> smoke_all.csv
  else
    ERR=$(echo "$VC" | jq -r '.detail // .error // ""')
    echo "ok,video,$MP4,,ERR,,$ERR" >> smoke_video.csv
    echo "video,ERR,commit fail" >> smoke_all.csv
  fi
else
  ERR=$(echo "$RV" | jq -r '.detail // .error // ""')
  echo "ERR,video,, ,ERR,,$ERR" >> smoke_video.csv
  echo "video,ERR,render fail" >> smoke_all.csv
fi

# Τερματικό output
echo "== IMAGES ==";   column -s, -t smoke_images.csv   | sed -n '1,20p'
echo "== CAROUSEL =="; column -s, -t smoke_carousel.csv | sed -n '1,20p'
echo "== VIDEO ==";    column -s, -t smoke_video.csv    | sed -n '1,20p'
echo "== ALL ==";      column -s, -t smoke_all.csv      | sed -n '1,50p'
