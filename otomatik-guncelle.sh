#!/usr/bin/env bash
# Kazan - otomatik guncelleme.
#
# Sunucuda cron bunu birkac dakikada bir calistirir. GitHub'da yeni bir surum
# varsa ceker ve servisi yeniden baslatir; yoksa hicbir sey yapmadan cikar.
# Boylece "git push" yeterli olur, sunucuya elle girip pull/restart yapmaya
# gerek kalmaz.
#
# Guvenli: internet yoksa ya da cekme (pull) basarisiz olursa servise
# DOKUNMAZ; site eski, calisan haliyle ayakta kalir. Her islem
# ~/kazan-guncelleme.log dosyasina yazilir.
#
# Kurulum (sunucuda bir kez) icin GUNCELLEME.md'deki "Otomatik guncelleme"
# bolumune bak.

cd "$(dirname "$0")" || exit 0

git fetch --quiet origin 2>/dev/null || exit 0
YEREL=$(git rev-parse @ 2>/dev/null) || exit 0
UZAK=$(git rev-parse '@{u}' 2>/dev/null) || exit 0

# Yeni bir sey yoksa sessizce cik.
[ "$YEREL" = "$UZAK" ] && exit 0

if git pull --quiet --ff-only; then
    sudo systemctl restart kazan
    echo "$(date '+%F %H:%M') guncellendi -> ${UZAK:0:9}" >> "$HOME/kazan-guncelleme.log"
else
    echo "$(date '+%F %H:%M') PULL HATASI - servise dokunulmadi" >> "$HOME/kazan-guncelleme.log"
fi
