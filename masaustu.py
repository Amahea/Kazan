# -*- coding: utf-8 -*-
"""Kazan — masaüstü sürümü: yayındaki siteyi kendi penceresinde açar.

Önemli: bu program AYRI BİR VERİTABANI TUTMAZ. Doğrudan yayındaki siteye (SITE)
bağlanır; yani ekrandaki her şey sunucudaki tek defterden gelir. Böylece
masaüstünde girilen veri anında sitede de görünür, hava ve diğer canlı veriler
sunucudan olduğu gibi gelir. Ayrı bir kopya/eşitleme derdi yoktur.

İnternet gerektirir (tasarım gereği; çevrimdışı çalışma istenmedi).

Çalıştırmak için:
    python masaustu.py                 # yayındaki siteyi açar
    python masaustu.py http://localhost:8000   # yereldeki kopyayı açar (deneme)

pywebview kurulu değilse varsayılan tarayıcıda açar (yine de çalışır).
Tek dosyalık bir .exe yapmak için dosyanın altındaki "PAKETLEME" notuna bak.
"""
import sys
import webbrowser

# Yayındaki site. Başka bir adrese taşırsan yalnızca burayı değiştir.
SITE = "https://esnaf.duckdns.org"
BASLIK = "Kazan — Dükkan Takip"


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else SITE
    try:
        import webview   # pywebview
    except ImportError:
        print("pywebview kurulu degil; site varsayilan tarayicida aciliyor.")
        print("Masaustu penceresi icin once:  pip install pywebview")
        webbrowser.open(url)
        return
    # Kendi penceresi: tarayici cubugu yok, program gibi durur.
    webview.create_window(BASLIK, url, width=1200, height=820,
                          min_size=(900, 600))
    webview.start()


if __name__ == "__main__":
    main()


# ------------------------------------------------------------------ PAKETLEME
# Windows'ta tek dosyalik bir .exe yapmak icin (komut satirinda, bu klasorde):
#
#     pip install pywebview pyinstaller
#     pyinstaller --noconsole --onefile --name "Kazan" --icon simge.ico masaustu.py
#
# Olusan dosya:  dist\Kazan.exe  -- cift tiklayinca program penceresi acilir,
# masaustunde ve gorev cubugunda simge.ico gorunur.
# simge.ico yoksa once:  python simge_yap.py   (uretir). --icon'u atlarsan
# varsayilan simge kullanilir.
# (Windows 10/11'de pywebview Edge WebView2'yi kullanir; genelde zaten kurulu.)
