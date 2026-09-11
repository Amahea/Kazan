# -*- coding: utf-8 -*-
"""Dukkan takip programi - web arayuzu.

Calistirmak icin: python uygulama.py
Sonra tarayicida http://localhost:8000 adresini ac.
Ayni wifi'daki telefondan da acilabilir; adres baslangicta ekrana yazilir.

Program dondurmaciya, pastaneye, firina ya da restorana gore degismez.
Butun urunler, malzemeler, receteler ve fiyatlar ekrandan girilir; ilk
acilista bir dukkan sablonu secilir ve oradan devam edilir.
"""

import datetime
import html
import os
import socket
import threading
import time
import traceback
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import grafik
import guvenlik
import hava
import hesap
import hesaplar
import menuler
import tahmin as tahmin_modulu
import takvim
import veritabani
from veritabani import ayar, ayar_yaz, sayi

# Bulut servisleri dinlenecek portu PORT degiskeniyle bildirir. Bu degiskenin
# varligi ayni zamanda "bir sunucuda calisiyoruz" demektir: orada tarayici
# acmanin ya da yerel ag adresi yazdirmanin anlami yok.
PORT = int(os.environ.get("PORT") or 8000)
SUNUCUDA = "PORT" in os.environ

# Istegi karsilayan is parcaciginin kendine ait bilgileri. Program birden
# fazla dukkana hizmet ettigi icin bunlar ORTAK olamaz: iki dukkan ayni anda
# kullanirken, ortak bir degiskene yazilan para birimi otekinin ekranina
# dusebilirdi. threading.local her is parcacigina ayri bir kopya verir.
_istek = threading.local()


def para_birimi():
    return getattr(_istek, "para", "TL")


# ---------------------------------------------------------------- bicimlendirme

def tl(deger):
    """1234.5 -> '1.234,50'"""
    metin = f"{abs(deger):,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")
    return ("-" if deger < 0 else "") + metin


def para(deger):
    return f"{tl(deger)} {para_birimi()}"


def mik(deger, basamak=2):
    """Miktari gereksiz sifirlar olmadan yazar: 3.0 -> '3', 0.5 -> '0,5'"""
    metin = f"{deger:,.{basamak}f}".replace(",", "#").replace(".", ",").replace("#", ".")
    if "," in metin:
        metin = metin.rstrip("0").rstrip(",")
    return metin or "0"


def kacir(metin):
    return html.escape(str(metin), quote=True)


def sayi_alani(ad, deger="", **ek):
    ozellikler = "".join(f' {anahtar}="{kacir(dgr)}"' for anahtar, dgr in ek.items())
    return (f'<input type="number" step="any" inputmode="decimal" name="{ad}"'
            f' value="{deger}"{ozellikler}>')


def secim(ad, secenekler, secili=None, ek=""):
    """secenekler: [(deger, etiket), ...]"""
    govde = "".join(
        f'<option value="{kacir(deger)}"'
        f'{" selected" if str(deger) == str(secili) else ""}>{kacir(etiket)}</option>'
        for deger, etiket in secenekler
    )
    return f'<select name="{ad}" {ek}>{govde}</select>'


def alan_kimligi(anahtar, onek):
    """'adet_12' -> 12. Beklenmedik bir alan adi gelirse None doner.

    Form alanlarinin adina kalem numarasi gomulu; bozuk bir ad yuzunden
    butun sayfanin coksmesi yerine o alan sessizce atlanir.
    """
    if not anahtar.startswith(onek):
        return None
    try:
        return int(anahtar[len(onek):])
    except ValueError:
        return None


def gruplu_secim(ad, gruplar, secili=None):
    """Tur basliklarina gore ayrilmis acilir liste.

    gruplar: [(baslik, [(deger, etiket), ...]), ...]
    """
    govde = ""
    for baslik, secenekler in gruplar:
        icerik = "".join(
            f'<option value="{kacir(deger)}"'
            f'{" selected" if str(deger) == str(secili) else ""}>{kacir(etiket)}</option>'
            for deger, etiket in secenekler
        )
        govde += f'<optgroup label="{kacir(baslik)}">{icerik}</optgroup>'
    return f'<select name="{ad}">{govde}</select>'


def tur_alani(baglanti, deger="", liste_adi="turler"):
    """Tur kutusu: yazarak yeni baslik acilir, mevcutlar oneri olarak gelir."""
    secenekler = "".join(f'<option value="{kacir(tur)}">' for tur in hesap.turler(baglanti))
    return (f'<input type="text" name="tur" list="{liste_adi}" value="{kacir(deger)}"'
            f' placeholder="Hammadde"><datalist id="{liste_adi}">{secenekler}</datalist>')


# Programda baska hicbir yerde betik yok; burada zorunlu, cunku bir alanin
# gizli mi acik mi olacagini HTML tek basina degistiremiyor. Kutu, kendi
# formundaki butun sifre alanlarini birden acar - "sifre" ve "sifre tekrar"
# ayri ayri isaretlenmek zorunda kalmasin.
#
# Dinleyici sayfanin tamamina bir kere baglanir; boylece kac tane sifre formu
# olursa olsun tek betik yetiyor. Betik calismazsa alanlar gizli kalir, yani
# en kotu ihtimalde ozellik yok - sifre acikta kalmaz.
SIFRE_BETIGI = """<script>
document.addEventListener('change', function (olay) {
  var kutu = olay.target;
  if (!kutu.classList || !kutu.classList.contains('sifre-goster')) return;
  var form = kutu.form;
  if (!form) return;
  var alanlar = form.querySelectorAll('input[data-sifre]');
  for (var i = 0; i < alanlar.length; i++) {
    alanlar[i].type = kutu.checked ? 'text' : 'password';
  }
});
</script>"""

SIFRE_GOSTER = ('<label class="goster"><input type="checkbox" class="sifre-goster">'
                'Şifreyi göster</label>')


def sifre_alani(ad, etiket, otomatik="new-password", odak=False):
    """Etiketiyle birlikte bir sifre alani.

    data-sifre isareti, "goster" kutusunun hangi alanlari acacagini bilmesi
    icin. Sadece isaretli alanlar aciliyor; kullanici adi gibi baska alanlara
    dokunulmuyor.
    """
    return (f'<label>{kacir(etiket)}</label>'
            f'<input type="password" data-sifre name="{ad}"'
            f' autocomplete="{otomatik}"{" autofocus" if odak else ""}>')


def kutucuk(ad, isaretli, etiket):
    return (f'<label style="display:flex;align-items:center;gap:8px;font-size:15px;'
            f'color:#1c2733;margin:0"><input type="checkbox" name="{ad}" value="1"'
            f' style="width:22px;height:22px"{" checked" if isaretli else ""}>'
            f'{kacir(etiket)}</label>')


# ---------------------------------------------------------------- sayfa iskeleti

STIL = """
* { box-sizing: border-box; }
body { margin:0; font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif;
       background:#f4f6f8; color:#1c2733; font-size:16px; }
/* Ust seritler ekranin tamamini kaplar ama icleri govdeyle ayni hizada durur. */
header { background:#0f4c75; color:#fff; padding:14px max(16px, calc((100% - 1400px) / 2)); }
header h1 { margin:0; font-size:19px; font-weight:600; }
nav { display:flex; gap:4px; overflow-x:auto; background:#123f5e;
      padding:0 max(8px, calc((100% - 1400px) / 2)); }
nav a { color:#cfe3f2; text-decoration:none; padding:12px 14px; white-space:nowrap; font-size:15px; }
nav a.aktif { color:#fff; border-bottom:3px solid #ffb703; font-weight:600; }
/* Simgeler yaziyi okumadan tanimayi kolaylastirir; dar ekranda da kaybolmaz. */
.simge { margin-right:6px; font-size:15px; font-style:normal; }
nav button { background:none; color:#cfe3f2; padding:12px 14px; font-size:15px;
             font-weight:400; margin-left:auto; white-space:nowrap; }
main { padding:16px; max-width:1400px; margin:0 auto; }

/* Kartlar genis ekranda iki sutuna dizilir, dar ekranda alt alta iner.
   Tablolar okunakli kalsin diye ikiden fazla sutun yapilmiyor. */
/* minmax(0,1fr): genis bir tablo kartin icinde kaysin, sayfayi yana kaydirmasin. */
.icerik { display:grid; gap:16px; align-items:start; grid-template-columns:minmax(0, 1fr); }
@media (min-width:1100px) { .icerik { grid-template-columns:repeat(2, minmax(0, 1fr)); } }
/* Ana menude sol sutun yer kapladigi icin ikili dizilim daha genis ekranda baslar. */
@media (max-width:1439px) { .ana-duzen > .icerik { grid-template-columns:minmax(0, 1fr); } }
.icerik > .kart, .icerik > .kutular { margin-bottom:0; }
.icerik > .kutular, .icerik > .sekmeler { grid-column:1 / -1; }
/* Sayfa ici sekmeler: satis sayfasinin iki yontemi arasinda gecis. */
.sekmeler { display:flex; gap:6px; background:#fff; border-radius:10px; padding:6px;
            box-shadow:0 1px 3px rgba(0,0,0,.08); max-width:520px; }
.sekmeler a { flex:1; text-align:center; padding:11px 14px; border-radius:7px;
              text-decoration:none; color:#33475b; font-weight:600; font-size:15px; }
.sekmeler a.aktif { background:#0f4c75; color:#fff; }
/* Sayfada tek kart varsa yarim ekranda durmasin, genisligi kaplasin. */
.icerik > .kart:only-child,
.icerik > .sekmeler + .kart:last-child { grid-column:1 / -1; }
/* Uzun giris listeleri genis ekranda yan yana kolonlara boluner. */
.giris-liste { display:grid; gap:0 22px;
               grid-template-columns:repeat(auto-fill, minmax(min(100%, 300px), 1fr)); }

/* Ana menu: solda tahmin sutunu, sagda gunun kartlari. */
.ana-duzen { display:grid; gap:16px; align-items:start; grid-template-columns:minmax(0, 1fr); }
.yan { display:grid; gap:16px; align-items:start; grid-template-columns:minmax(0, 1fr); }
.yan .kart { margin-bottom:0; padding:14px; }
.yan .kart h2 { font-size:15px; }
.yan-satir { display:flex; justify-content:space-between; align-items:baseline;
             gap:10px; padding:7px 0; border-bottom:1px solid #f0f3f6; font-size:14px; }
.yan-satir:last-child { border-bottom:0; }
.yan-satir .sag { text-align:right; white-space:nowrap; }
@media (min-width:1000px) {
  .ana-duzen { grid-template-columns:320px minmax(0, 1fr); }
  .ana-duzen > .yan { grid-column:1; grid-row:1; }
  .ana-duzen > .icerik { grid-column:2; grid-row:1; }
}
.kart { background:#fff; border-radius:10px; padding:16px; margin-bottom:16px;
        box-shadow:0 1px 3px rgba(0,0,0,.08); }
.kart h2 { margin:0 0 12px; font-size:17px; }
.kart h3 { margin:18px 0 8px; font-size:15px; color:#0f4c75; }
/* auto-fill: kutu sayisi az oldugunda kutular kocaman gerilmez, boyu sabit kalir. */
.kutular { display:grid; gap:12px; margin-bottom:16px;
           grid-template-columns:repeat(auto-fill,minmax(min(100%, 210px),1fr)); }
.kutu { background:#fff; border-radius:10px; padding:14px; box-shadow:0 1px 3px rgba(0,0,0,.08); }
.kutu .etiket { font-size:13px; color:#6b7c8f; margin-bottom:6px; }
.kutu .deger { font-size:22px; font-weight:700; }
/* Ustune tiklanabilen kutu: ayrintiyi acar, digerlerinden farki el imleci ve ok. */
a.kutu { display:block; text-decoration:none; color:inherit; }
a.kutu:hover { box-shadow:0 2px 10px rgba(15,76,117,.22); }
a.kutu .etiket .ok { float:right; font-weight:700; }
/* Genis ekranda iki sutuna bolunmeyip tam genisligi kaplayan kartlar. */
.icerik > .tam { grid-column:1 / -1; }
/* Rapor basligi: ortada donem adi, iki yaninda ileri geri oklari. */
.donem-ust { display:flex; align-items:center; gap:10px; }
.donem-ust h2 { margin:0; flex:1; text-align:center; }
.ok-dugme { text-decoration:none; background:#e6ebf0; color:#33475b; border-radius:7px;
            padding:9px 13px; font-weight:600; white-space:nowrap; }
.ok-dugme:hover { background:#d5dee6; }
/* Para akisi: yukaridan asagi okunan hesap. Ara sonuclar koyu ve zeminli. */
.akis td { padding:10px 6px; }
.akis .isaret { width:22px; text-align:center; color:#8494a5; font-weight:700; }
.akis .sonuc td { font-weight:700; background:#f5f8fa; }
.akis .aciklama { display:block; font-size:13px; color:#6b7c8f; font-weight:400; }
/* Acilir bolum. Baglanti degil <details> oldugu icin sayfa yeniden yuklenmez;
   tiklayinca yalnizca o bolum asagi dogru acilir, ekran yerinden oynamaz. */
details.acilir { margin-top:12px; border-top:1px solid #e6ebf0; }
details.acilir > summary { cursor:pointer; color:#0f4c75; font-weight:600;
                           padding:10px 2px; list-style:none; }
details.acilir > summary::-webkit-details-marker { display:none; }
details.acilir > summary::before { content:"\u25b8\u00a0"; }
details.acilir[open] > summary::before { content:"\u25be\u00a0"; }
details.acilir > summary:hover { text-decoration:underline; }
details.acilir .ic { padding-bottom:4px; }
details.acilir h3:first-child { margin-top:4px; }
/* Sutun genisligi icerige gore degil colgroup'a gore belirlensin: bir tablo
   ikiye bolundugunde iki parcanin sutunlari ayni hizada dursun. */
table.sabit { table-layout:fixed; }
table.sabit td { overflow-wrap:anywhere; }

/* ---- grafikler ------------------------------------------------------------
   Renkler grafik.py'de duruyor, burasi sadece bicim. Isaretler ince, izgarayla
   eksen geri planda: sayfada koyu olan tek sey verinin kendisi. */
.serit { position:relative; display:flex; gap:2px; height:22px; margin:2px 0 12px; }
.serit-parca { display:flex; align-items:center; justify-content:center; min-width:0; }
/* Serit soldan basliyor: sol ucu duz, veri ucu olan sag ucu yuvarlak. */
.serit-parca:last-child { border-radius:0 4px 4px 0; }
.serit-parca:hover { filter:brightness(1.08); }
.serit-ic { font-size:12px; font-weight:700; white-space:nowrap; }
/* Gider ciroyu asinca cironun nerede bittigini gosteren cizgi. */
.serit-isaret { position:absolute; top:-5px; bottom:-5px; width:2px; background:#1c2733; }
.anahtar { display:flex; flex-wrap:wrap; gap:6px 18px; list-style:none;
           margin:0; padding:0; font-size:14px; color:#4a5b6e; }
.anahtar li { display:flex; align-items:center; gap:6px; }
.anahtar b { color:#1c2733; font-weight:600; }
.anahtar-nokta { width:11px; height:11px; border-radius:3px; flex:none; }

.cubuklar { margin-top:4px; }
.cubuk-satir { margin-bottom:13px; }
.cubuk-satir:last-child { margin-bottom:2px; }
.cubuk-ust { display:flex; justify-content:space-between; gap:14px;
             font-size:15px; margin-bottom:5px; }
.cubuk-ust span { overflow-wrap:anywhere; }
.cubuk-ust b { white-space:nowrap; font-weight:600; }
.cubuk-yol { height:10px; background:#eef2f5; border-radius:0 5px 5px 0; }
.cubuk-dolgu { display:block; height:100%; border-radius:0 4px 4px 0; }
.cubuk-satir:hover .cubuk-dolgu { filter:brightness(1.08); }

.sutun-grafik { position:relative; padding-top:18px; margin-top:4px; }
/* Tavan cizgisi en yuksek sutunun boyu; yanindaki sayi olcegi verir. */
.sutun-tavan { position:absolute; left:0; right:0; top:18px; border-top:1px solid #e6ebf0; }
.sutun-tavan span { position:absolute; top:-17px; left:0; font-size:12px; color:#6b7c8f; }
.sutun-sira { display:flex; gap:2px; height:150px; border-bottom:1px solid #cfd8e0; }
.sutun { flex:1 1 0; min-width:0; display:flex; align-items:flex-end;
         justify-content:center; text-decoration:none; }
/* Sutun bandi doldurulmuyor: kalan bosluk grafigi ferah tutuyor. */
.sutun-cubuk { display:block; width:100%; max-width:24px; border-radius:4px 4px 0 0; }
.sutun:hover .sutun-cubuk { filter:brightness(1.08); }
.sutun-etiketler { display:flex; gap:2px; margin-top:7px; }
.sutun-etiketler span { flex:1 1 0; min-width:0; text-align:center;
                        font-size:12px; color:#6b7c8f; white-space:nowrap; }
.sutun-etiketler span.secili { color:#1c2733; font-weight:600; }
/* Uclardaki yazi sutunun ortasina gore degil kartin icine hizalanir; yoksa
   '17 Ağu' gibi uzun bir yazi son sutunda kartin disina tasiyor. */
.sutun-etiketler span:first-child { text-align:left; }
.sutun-etiketler span:last-child { text-align:right; }
.grafik-alt { margin:10px 0 0; font-size:14px; color:#4a5b6e; }
.grafik-alt b { color:#1c2733; }
/* Raporun uc buyuk rakami: az sayida olduklari icin seridi paylasarak doldururlar. */
.kutular.baslik { grid-template-columns:repeat(auto-fit, minmax(min(100%, 260px), 1fr)); }
.hava-simge { margin-right:6px; }
.yesil { color:#1b7f4f; } .kirmizi { color:#c1392b; } .mavi { color:#0f4c75; } .gri { color:#6b7c8f; }
table { width:100%; border-collapse:collapse; font-size:15px; }
th, td { text-align:left; padding:9px 6px; border-bottom:1px solid #e6ebf0; }
th { font-size:13px; color:#6b7c8f; font-weight:600; }
td.sag, th.sag { text-align:right; }
input, select, button { font-size:16px; font-family:inherit; }
input[type=text], input[type=number], input[type=date], input[type=password], select {
    width:100%; padding:10px; border:1px solid #cfd8e0; border-radius:7px; background:#fff; }
label { display:block; font-size:13px; color:#6b7c8f; margin:0 0 4px; }
/* "Sifreyi goster" kutusu: alanin hemen altinda, kucuk ve sade. */
label.goster { display:flex; align-items:center; gap:7px; margin:7px 0 0;
               font-size:13px; color:#6b7c8f; cursor:pointer; }
label.goster input { width:16px; height:16px; }
.satir { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; margin-bottom:12px; }
.roller { display:flex; flex-wrap:wrap; gap:16px; margin:10px 0 14px; }
button { background:#0f4c75; color:#fff; border:0; border-radius:7px; padding:12px 20px;
         font-weight:600; cursor:pointer; }
button.ikincil { background:#e6ebf0; color:#33475b; }
button.sil { background:none; color:#c1392b; padding:4px 8px; font-weight:400; font-size:14px; }
button.mini { background:none; color:#33475b; padding:4px 8px; font-weight:400; font-size:14px;
              text-decoration:underline; }
.mesaj { background:#dff3e6; border-left:4px solid #1b7f4f; padding:12px 14px; border-radius:7px;
         margin-bottom:16px; }
.mesaj.hata { background:#fde8e6; border-left-color:#c1392b; }
.uyari { padding:12px 14px; border-radius:7px; margin-bottom:10px; border-left:4px solid; }
.uyari.bitti { background:#fde8e6; border-color:#c1392b; }
.uyari.acil  { background:#fff1de; border-color:#e07b00; }
.uyari.yakin { background:#eef4fa; border-color:#5b8db8; }
.uyari.mevsim { background:#eef7f1; border-color:#2f8f5b; }
.uyari.mevsim .detay { margin-top:5px; }
.uyari b { font-size:16px; }
.uyari .detay { font-size:14px; color:#4a5b6e; margin-top:3px; }
.bos { color:#6b7c8f; font-size:15px; }
.giris-satir { display:flex; align-items:center; gap:12px; padding:8px 0; border-bottom:1px solid #f0f3f6; }
.giris-satir .ad { flex:1; }
.giris-satir .fiyat { font-size:13px; color:#6b7c8f; }
.giris-satir input { width:90px; text-align:center; }
.rozet { display:inline-block; font-size:12px; padding:2px 8px; border-radius:20px;
         background:#e6ebf0; color:#33475b; margin-right:4px; }
.rozet.al { background:#e3eefa; color:#1c5f96; }
.rozet.ur { background:#e6f3ec; color:#1b7f4f; }
.rozet.sat { background:#fdf0d8; color:#8a5a00; }
.sablon { display:block; border:2px solid #e6ebf0; border-radius:10px; padding:14px;
          margin-bottom:10px; text-decoration:none; color:inherit; }
.sablon b { display:block; font-size:17px; margin-bottom:4px; color:#0f4c75; }
"""


# Ust menu gunun akisini izler: bak - sat - uret - stoga bak - parayi gir -
# raporla - ayarla. Ucuncu sutun, menude gorunmeyen ama o baslige ait olan
# sayfalar; o sayfalardayken de baslik isaretli kalir.
MENU = [
    ("/", "Ana Menü", "🏠", ()),
    ("/satis", "Satış", "🍦", ("/satis-giris",)),
    ("/uretim", "Üretim", "🥛", ()),
    ("/stok", "Stok", "📦", ()),
    ("/para", "Alım / Gider", "💰", ("/calisanlar",)),
    ("/ozet", "Raporlar", "📊", ("/tahmin", "/ozel-gunler")),
    ("/ayarlar", "Ayarlar", "⚙️", ("/kalemler", "/kalem", "/menuler")),
]


def menu_ogeleri(baglanti):
    return MENU


def sayfa(baglanti, yol, baslik, icerik, mesaj=""):
    menu = "".join(
        f'<a href="{adres}" class="'
        f'{"aktif" if yol == adres or yol in alt else ""}">'
        f'<span class="simge">{simge}</span>{ad}</a>'
        for adres, ad, simge, alt in menu_ogeleri(baglanti)
    )
    # Cikis ancak girilmis bir hesap varsa anlamli. Dukkan icinde, defterde
    # hic kullanici yokken program dogrudan aciliyor; orada cikis anlamsiz.
    if getattr(_istek, "kullanici", None):
        menu += ('<form method="post" action="/cikis" style="display:contents">'
                 '<button><span class="simge">🚪</span>Çıkış</button></form>')
    # Basinda '!' olan mesaj bir uyaridir; yesil degil kirmizi kutuda gosterilir.
    mesaj_html = ""
    if mesaj:
        hata = mesaj.startswith("!")
        mesaj_html = (f'<div class="mesaj{" hata" if hata else ""}">'
                      f'{kacir(mesaj[1:] if hata else mesaj)}</div>')
    dukkan = kacir(ayar(baglanti, "dukkan_adi", "Dükkanım"))

    # Ana menude tahmin sutunu solda durur. Icerik HTML'de once yazilir ki
    # telefonda once gunun kartlari, altinda tahmin gorunsun.
    govde = f'<div class="icerik">{icerik}</div>'
    yan = yan_panel(baglanti) if yol == "/" else ""
    if yan:
        govde = f'<div class="ana-duzen">{govde}<aside class="yan">{yan}</aside></div>'

    return f"""<!DOCTYPE html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{kacir(baslik)} - {dukkan}</title><style>{STIL}</style></head>
<body><header><h1>{dukkan}</h1></header><nav>{menu}</nav>
<main>{mesaj_html}{govde}</main>{SIFRE_BETIGI}</body></html>"""


def _yan_hava_satirlari(baglanti, gun_sayisi=7):
    """Sol sutun icin dar, tek satirlik hava listesi."""
    bugun = datetime.date.today()
    satirlar = ""
    for kaydirma in range(gun_sayisi):
        tarih = (bugun + datetime.timedelta(days=kaydirma)).strftime("%Y-%m-%d")
        gun = hava.gun(baglanti, tarih)
        if gun is None or gun["en_yuksek"] is None:
            continue
        gun_adi = ("Bugün" if kaydirma == 0 else
                   "Yarın" if kaydirma == 1 else
                   tahmin_modulu.GUN_ADLARI[(bugun + datetime.timedelta(days=kaydirma)).weekday()])
        alt = kacir(hava.hadise_metni(gun["hadise"])
                    or ("yağışlı" if gun["yagmurlu"] else ""))
        oran = hava.ihtimal(gun)
        if oran is not None:
            alt += f'{" · " if alt else ""}☔ %{oran}'
        satirlar += (f'<div class="yan-satir"><div><b>{kacir(gun_adi)}</b>'
                     f'<div class="bos" style="font-size:12px">{alt}</div></div>'
                     f'<div class="sag"><b>{hava.simge(gun)} '
                     f'{gun["en_yuksek"]:.0f}°</b></div></div>')
    return satirlar


def yan_panel(baglanti):
    """Ana menunun solundaki sutun: yedi gunluk hava ve kisa uretim onerisi.
    Ciro tahmini burada degil, /tahmin sayfasinda. Tahmin kapaliysa sutun
    hic cizilmez."""
    if ayar(baglanti, "tahmin_acik", "1") != "1":
        return ""

    if not hava.sehir_secili_mi(baglanti):
        return ('<div class="kart"><h2>Tahmin</h2>'
                '<p class="bos">Hava ve satış tahmini için '
                '<a href="/ayarlar">Ayarlar</a> sayfasından ilini seç.</p></div>')

    sehir = kacir(ayar(baglanti, "sehir", ""))
    model, _gunler, uretimler = tahmin_modulu.ileri_tahmin(baglanti, 7)

    # Ana menude sadece hava gorunur. Ciro tahmini kalabalik yaptigi icin
    # burada gosterilmiyor; rakamlar /tahmin sayfasinda duruyor.
    govde = _yan_hava_satirlari(baglanti)
    if not govde:
        govde = f'<p class="bos">{kacir(tahmin_modulu.durum_metni(model))}</p>'

    panel = (f'<div class="kart"><h2>{sehir} — hava</h2>{govde}'
             f'<p class="bos" style="margin-top:10px">'
             f'<a href="/tahmin">Tahmin sayfasını aç</a></p></div>')

    uretme = menuler.uretilmeyecekler(menuler.oneri(baglanti))
    acik_olanlar = [oneri for oneri in uretimler
                    if oneri["acik"] > 0 and oneri["kalem"]["id"] not in uretme][:5]
    if acik_olanlar:
        satirlar = "".join(
            f'<div class="yan-satir"><div>{kacir(oneri["kalem"]["ad"])}'
            f'<div class="bos" style="font-size:13px">{mik(oneri["acik"], 1)} '
            f'{kacir(oneri["kalem"]["birim"])} açık</div></div>'
            f'<div class="sag"><b>{oneri["parti"]} '
            f'{kacir(oneri["parti_ad"])}</b></div></div>'
            for oneri in acik_olanlar
        )
        panel += (f'<div class="kart"><h2>Ne üretmeli</h2>{satirlar}'
                  f'<p class="bos" style="margin-top:10px">Tahmine göre eldeki '
                  f'stok bu kadar yetmiyor. Kazan tam çırpıldığı için öneri '
                  f'her zaman tam sayıdır.</p></div>')

    return panel


# Giris ve kayit ekranlarinin kendi stili. Programin geri kalani ust serit +
# menu + kartlar duzeninde; giris ekraninda bunlarin hicbiri yok, cunku daha
# hangi dukkana bakildigi bilinmiyor. Ekranda tek bir is var: kim oldugunu
# soylemek. O yuzden sayfa ortada tek karttan ibaret.
KAPAK_STIL = """
body.kapak { min-height:100vh; margin:0; display:flex; align-items:center;
    justify-content:center; padding:24px 16px;
    background:linear-gradient(160deg, #14567f 0%, #0f4c75 45%, #0a3350 100%); }
.kapak-govde { width:100%; max-width:400px; }
/* Marka: kartin ustunde, koyu zeminin uzerinde. */
.marka { text-align:center; margin:0 0 22px; }
.marka .isaret { display:inline-flex; align-items:center; justify-content:center;
    width:52px; height:52px; border-radius:14px; background:rgba(255,255,255,.12);
    border:1px solid rgba(255,255,255,.18); font-size:26px; margin-bottom:12px; }
.marka h1 { margin:0; color:#fff; font-size:21px; font-weight:600; letter-spacing:.2px; }
.marka p { margin:5px 0 0; color:#a8c8e0; font-size:14px; }

.kapak-kart { background:#fff; border-radius:14px; padding:26px 24px;
    box-shadow:0 18px 45px rgba(0,0,0,.28); }
.kapak-kart h2 { margin:0 0 4px; font-size:19px; }
.kapak-kart .alt-baslik { margin:0 0 20px; font-size:14px; color:#6b7c8f; }
/* Alanlar arasi bosluk tek yerden yonetilsin diye her alan bir 'oge' icinde. */
.oge { margin-bottom:14px; }
.kapak-kart input[type=text], .kapak-kart input[type=password] { padding:11px 12px; }
/* Odaklanan alan belli olsun - klavyeyle gezen icin de sart. */
.kapak-kart input:focus { outline:none; border-color:#0f4c75;
    box-shadow:0 0 0 3px rgba(15,76,117,.14); }
.kapak-kart button { width:100%; padding:13px; font-size:16px; margin-top:6px; }
.kapak-kart button:hover { background:#0d4165; }
/* Hata kutusu: kirmizi ama bagirmayan. */
.kapak-hata { background:#fdecea; border:1px solid #f5c6c2; color:#9d2f24;
    border-radius:8px; padding:10px 12px; margin-bottom:16px; font-size:14px; }
/* Kartin altindaki gecis baglantisi. */
.kapak-alt { text-align:center; margin:18px 0 0; font-size:14px; color:#a8c8e0; }
.kapak-alt a { color:#fff; font-weight:600; }
.kapak-ayrac { border:0; border-top:1px solid #e6ebf0; margin:20px 0 0; }
"""


def _kapak(baslik, icerik, alt="", genislik=400):
    """Giris/kayit ekranlarinin ortak cercevesi: menusuz, ortada tek kart.

    Bu ekranlar herhangi bir dukkanin verisine daha bakmadan cizilir - kimin
    girdigi henuz bilinmiyor, dolayisiyla dukkan adi da bilinmiyor. Basliktaki
    "Dükkan Takip" bu yuzden sabit.
    """
    return f"""<!DOCTYPE html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{kacir(baslik)} - Dükkan Takip</title>
<style>{STIL}{KAPAK_STIL}</style></head>
<body class="kapak">
<div class="kapak-govde" style="max-width:{genislik}px">
<div class="marka"><div class="isaret">🏪</div>
<h1>Dükkan Takip</h1><p>Kasa, stok ve satış tek yerde</p></div>
<div class="kapak-kart">{icerik}</div>
{f'<p class="kapak-alt">{alt}</p>' if alt else ''}
</div>{SIFRE_BETIGI}</body></html>"""


def giris_sayfasi(hata="", eposta=""):
    """Giris ekrani. Giris yapmadan hicbir sayfa gorunmez."""
    uyari = f'<div class="kapak-hata">{kacir(hata)}</div>' if hata else ""
    return _kapak("Giriş", f"""
<h2>Giriş yap</h2>
<p class="alt-baslik">Dükkanının kayıtlarına ulaşmak için.</p>{uyari}
<form method="post" action="/giris">
<div class="oge"><label>Kullanıcı adı</label>
<input type="text" name="eposta" value="{kacir(eposta)}" autofocus autocomplete="username"></div>
<div class="oge">{sifre_alani("sifre", "Şifre", "current-password")}
{SIFRE_GOSTER}</div>
<button>Gir</button></form>""",
        alt='Dükkanın burada kayıtlı değil mi? <a href="/kayit">Yeni dükkan aç</a>')


def kayit_sayfasi(hata="", d=None):
    """Yeni dukkan acma ekrani.

    Kaydolan kisi hem dukkani kurar hem onun sahibi olur. Dukkanin verisi
    kendi dosyasinda acilir; baska hicbir dukkanla ortak yeri yoktur.
    """
    d = d or {}
    uyari = f'<div class="kapak-hata">{kacir(hata)}</div>' if hata else ""

    def deger(ad):
        return kacir(d.get(ad, [""])[0] if isinstance(d.get(ad), list) else d.get(ad, ""))

    return _kapak("Yeni dükkan", f"""
<h2>Yeni dükkan aç</h2>
<p class="alt-baslik">Kayıtların kendi dosyasında tutulur; başka hiçbir dükkan
onları göremez.</p>{uyari}
<form method="post" action="/kayit">
<div class="oge"><label>Dükkanın adı</label>
<input type="text" name="dukkan_adi" value="{deger('dukkan_adi')}" autofocus></div>
<div class="oge"><label>Adın soyadın</label>
<input type="text" name="ad" value="{deger('ad')}"></div>
<div class="oge"><label>Kullanıcı adı (girişte bunu yazacaksın)</label>
<input type="text" name="eposta" value="{deger('eposta')}" autocomplete="username"></div>
<div class="oge">
{sifre_alani("sifre", f"Şifre (en az {hesaplar.EN_KISA_SIFRE} karakter)")}</div>
<div class="oge">{sifre_alani("sifre2", "Şifre (tekrar)")}
{SIFRE_GOSTER}</div>
<button>Dükkanı aç</button></form>""",
        alt='Hesabın zaten var mı? <a href="/giris">Giriş yap</a>', genislik=430)


def kutu(etiket, deger, renk="mavi", alt="", adres="", ok=""):
    """adres verilirse kutunun tamami tiklanabilir bir baglanti olur."""
    alt_html = f'<div class="etiket" style="margin:4px 0 0">{alt}</div>' if alt else ""
    ok_html = f'<span class="ok">{ok}</span>' if ok else ""
    etiket_html = f'<div class="etiket">{ok_html}{kacir(etiket)}</div>'
    govde = f'{etiket_html}<div class="deger {renk}">{deger}</div>{alt_html}'
    if adres:
        return f'<a class="kutu" href="{adres}">{govde}</a>'
    return f'<div class="kutu">{govde}</div>'


def tarih_alani(tarih):
    return f'<label>Tarih</label><input type="date" name="tarih" value="{kacir(tarih)}">'


AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
         "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


def gun_yaz(metin, gun_adiyla=True):
    """'2026-03-20' -> '20 Mart 2026 Cuma'. Bozuk tarihi oldugu gibi birakir."""
    try:
        gun = datetime.date.fromisoformat(metin)
    except (ValueError, TypeError):
        return metin
    yazi = f"{gun.day} {AYLAR[gun.month - 1]} {gun.year}"
    if gun_adiyla:
        yazi += f" {tahmin_modulu.GUN_ADLARI[gun.weekday()]}"
    return yazi


def rozetler(kalem):
    yazi = ""
    if kalem["alinir"]:
        yazi += '<span class="rozet al">alınır</span>'
    if kalem["uretilir"]:
        yazi += '<span class="rozet ur">üretilir</span>'
    if kalem["satilir"]:
        yazi += '<span class="rozet sat">satılır</span>'
    if not kalem["takip"]:
        yazi += '<span class="rozet">stok tutulmaz</span>'
    if "mevsim_disi" in kalem.keys() and kalem["mevsim_disi"]:
        yazi += '<span class="rozet">mevsim dışı</span>'
    return yazi or '<span class="rozet">rolsüz</span>'


# ---------------------------------------------------------------- kurulum

def sayfa_kurulum(baglanti, sorgu):
    kartlar = ""
    for anahtar, sablon in veritabani.SABLONLAR.items():
        kartlar += (
            f'<form method="post" action="/kurulum">'
            f'<input type="hidden" name="sablon" value="{anahtar}">'
            f'<button class="sablon" style="width:100%;text-align:left;cursor:pointer">'
            f'<b>{kacir(sablon["ad"])}</b>'
            f'<span class="bos">{kacir(sablon["aciklama"])}</span></button></form>'
        )
    return f"""
<div class="kart"><h2>Hoş geldin — dükkanını seç</h2>
<p class="bos">Seçtiğin şablon sana hazır bir malzeme, ürün ve reçete listesi verir.
Hepsi örnektir: sonradan <b>Ürün &amp; Malzeme</b> sayfasından silebilir, değiştirebilir,
yenisini ekleyebilirsin. Program hiçbir ürünü özel olarak tanımaz.</p>
{kartlar}</div>"""


def islem_kurulum(baglanti, veri):
    anahtar = veri.get("sablon", [""])[0]
    if veritabani.sablon_uygula(baglanti, anahtar):
        return "/", f"{veritabani.SABLONLAR[anahtar]['ad']} şablonu yüklendi."
    return "/kurulum", "Şablon bulunamadı."


# ---------------------------------------------------------------- bugun

def sayfa_bugun(baglanti, sorgu):
    tarih = hesap.bugun()
    ozet = hesap.gun_ozeti(baglanti, tarih)

    kutular = (
        kutu("Kasadaki nakit", para(hesap.kasa(baglanti)), "yesil")
        + kutu("Tedarikçilere borç", para(hesap.borc(baglanti)), "kirmizi")
        + kutu("Bugünün cirosu", para(ozet["ciro"]), "mavi")
        + kutu("Bugünün net kârı", para(ozet["net_kar"]),
               "yesil" if ozet["net_kar"] >= 0 else "kirmizi")
    )

    stoklu = [
        k for k in hesap.kalem_listesi(baglanti)
        if k["uretilir"] and k["takip"]
    ]
    for kalem in stoklu[:2]:
        alt = ""
        if kalem["koli_adet"] > 0:
            alt = (f'yaklaşık {mik(kalem["stok"] / kalem["koli_adet"], 1)} '
                   f'{kacir(kalem["koli_ad"])}')
        kutular += kutu(f'Hazır {kalem["ad"]}',
                        f'{mik(kalem["stok"], 1)} {kacir(kalem["birim"])}', "mavi", alt)

    plan = menuler.oneri(baglanti)
    # Gecis yaklasirken kapanacak cesit icin "1 kazan uret" demek, gecisten
    # sonra dolapta satilamayacak dondurma biriktirmek olur.
    uretme = menuler.uretilmeyecekler(plan)
    liste = [satir for satir in hesap.oneriler(baglanti)
             if not (satir["parti"] and satir["kalem"]["id"] in uretme)]
    gecis_uyarisi = _gecis_ozeti(plan) if plan else ""
    if liste or gecis_uyarisi:
        uyarilar = gecis_uyarisi
        for satir in liste:
            kalem = satir["kalem"]
            if satir["seviye"] == "bitti":
                basli = f"{kalem['ad']} BİTTİ"
            elif satir["kalan_gun"] is not None:
                basli = (f"{kalem['ad']} bitmek üzere — yaklaşık "
                         f"{mik(satir['kalan_gun'], 1)} günlük kaldı")
            else:
                basli = f"{kalem['ad']} kritik seviyenin altında"
            detay = f"Elde {mik(satir['stok'])} {kacir(kalem['birim'])}"
            if satir["gunluk"] > 0:
                detay += (f" · günde ortalama {mik(satir['gunluk'])} "
                          f"{kacir(kalem['birim'])} gidiyor")
            if satir["parti"]:
                # Uretilenler tam kazanla: "1 kazan üret (122 kg çıkar)".
                p = satir["parti"]
                detay += (f" · <b>{p['sayi']} {kacir(p['parti_ad'])} üret</b> "
                          f"({mik(p['cikacak'], 1)} {kacir(kalem['birim'])} çıkar, "
                          f"yaklaşık {para(satir['tutar'])})")
            elif satir["onerilen"] > 0:
                detay += (f" · <b>{mik(satir['onerilen'])} {kacir(kalem['birim'])} "
                          f"{satir['eylem']}</b> (yaklaşık {para(satir['tutar'])})")
            if kalem["tedarikci"]:
                detay += f" · {kacir(kalem['tedarikci'])}"
            uyarilar += (f'<div class="uyari {satir["seviye"]}"><b>{kacir(basli)}</b>'
                         f'<div class="detay">{detay}</div></div>')
        oneri_karti = f'<div class="kart"><h2>Yapman gerekenler</h2>{uyarilar}</div>'
    else:
        oneri_karti = ('<div class="kart"><h2>Yapman gerekenler</h2>'
                       '<p class="bos">Şu an acil bir şey yok, stoklar yeterli.</p></div>')

    satislar = baglanti.execute(
        "SELECT k.ad, k.birim, SUM(s.miktar) AS miktar, SUM(s.tutar) AS tutar"
        " FROM satislar s JOIN kalemler k ON k.id = s.kalem_id"
        " WHERE s.tarih = ? GROUP BY k.id ORDER BY k.sira, k.ad", (tarih,)
    ).fetchall()
    if satislar:
        satirlar = "".join(
            f"<tr><td>{kacir(s['ad'])}</td>"
            f"<td class='sag'>{mik(s['miktar'])} {kacir(s['birim'])}</td>"
            f"<td class='sag'>{para(s['tutar'])}</td></tr>" for s in satislar
        )
        satis_karti = (f'<div class="kart"><h2>Bugün girilen satışlar</h2><table>'
                       f"<tr><th>Ürün</th><th class='sag'>Miktar</th>"
                       f"<th class='sag'>Tutar</th></tr>{satirlar}</table></div>")
    else:
        satis_karti = ('<div class="kart"><h2>Bugün girilen satışlar</h2>'
                       '<p class="bos">Henüz giriş yapılmadı.</p></div>')

    return f'<div class="kutular">{kutular}</div>{oneri_karti}{satis_karti}'


# ---------------------------------------------------------------- satis

def sayfa_satis_merkezi(baglanti, sorgu):
    """Satisin iki yolu tek sayfada: rafta kalani say ya da tek tek gir.
    Ayarlardaki tercih ikisinden birini sectiyse sekme hic gorunmez."""
    mod = ayar(baglanti, "satis_girisi", "ikisi")
    yontem = sorgu.get("yontem", [""])[0]
    if mod in ("sayim", "dogrudan"):
        yontem = mod
    elif yontem not in ("sayim", "dogrudan"):
        yontem = "sayim"

    sekmeler = ""
    if mod == "ikisi":
        tarih = sorgu.get("tarih", [""])[0]
        ek = f"&tarih={urllib.parse.quote(tarih)}" if tarih else ""
        sekmeler = '<div class="sekmeler">' + "".join(
            f'<a href="/satis?yontem={anahtar}{ek}" '
            f'class="{"aktif" if anahtar == yontem else ""}">{etiket}</a>'
            for anahtar, etiket in (("sayim", "Rafta kalanı say"),
                                    ("dogrudan", "Tek tek gir"))
        ) + "</div>"

    if yontem == "sayim":
        return sekmeler + sayfa_satis(baglanti, sorgu)
    return sekmeler + sayfa_satis_giris(baglanti, sorgu)


def _dogrudan_adres(tarih):
    """Dogrudan giris sekmesinin, tarihi koruyan adresi."""
    return f"/satis?yontem=dogrudan&tarih={urllib.parse.quote(tarih)}"


def sayfa_satis_dogrudan(baglanti, sorgu):
    """Eski /satis-giris adresi; sekmeli sayfayi dogrudan giris kisminda acar."""
    return sayfa_satis_merkezi(baglanti, dict(sorgu, yontem=["dogrudan"]))


# ---------------------------------------------------------------- gun sonu sayimi

def _sayim_alani(kalem, onceki):
    """Bir kalem icin 'koli + adet' giris satiri."""
    koli_kutusu = ""
    if kalem["koli_adet"] > 0:
        koli_kutusu = (
            f'<input type="number" step="any" min="0" inputmode="decimal" '
            f'name="koli_{kalem["id"]}" value="{mik(onceki["koli"])}" placeholder="0" '
            f'style="width:70px" title="{kacir(kalem["koli_ad"])}"> '
            f'<span class="fiyat">{kacir(kalem["koli_ad"])} +</span> '
        )
    ek = (f' · 1 {kacir(kalem["koli_ad"])} = {mik(kalem["koli_adet"])}'
          if kalem["koli_adet"] > 0 else "")
    return (
        f'<div class="giris-satir"><div class="ad"><b>{kacir(kalem["ad"])}</b>'
        f'<div class="fiyat">rafta olması gereken: {mik(onceki["stok"])} '
        f'{kacir(kalem["birim"])}{ek}</div></div>'
        f'<div style="white-space:nowrap">{koli_kutusu}'
        f'<input type="number" step="any" min="0" inputmode="decimal" '
        f'name="adet_{kalem["id"]}" value="{mik(onceki["adet"])}" placeholder="0" '
        f'style="width:80px" title="{kacir(kalem["birim"])}"></div></div>'
    )


def _bitti_alani(kalem, stok, isaretli):
    """Tek tek sayilmayan kalemler icin 'bir koli bitti' kutucugu."""
    kalan_koli = (stok / kalem["koli_adet"]) if kalem["koli_adet"] > 0 else 0
    return (
        f'<div class="giris-satir"><div class="ad"><b>{kacir(kalem["ad"])}</b>'
        f'<div class="fiyat">elde yaklaşık {mik(kalan_koli, 1)} {kacir(kalem["koli_ad"])} '
        f'({mik(stok)} {kacir(kalem["birim"])})</div></div>'
        f'{kutucuk("bitti_" + str(kalem["id"]), isaretli, "bir " + kalem["koli_ad"] + " bitti")}'
        f'</div>'
    )


def sayfa_satis(baglanti, sorgu):
    tarih = sorgu.get("tarih", [hesap.bugun()])[0]
    sayim = hesap.sayim_getir(baglanti, tarih)

    # Daha once bu tarihe sayim girildiyse kutulari onceki degerlerle doldur.
    onceki_girisler, tuketimler = {}, {}
    if sayim:
        for satir in hesap.sayim_satirlari(baglanti, sayim["id"]):
            onceki_girisler[satir["kalem_id"]] = {"koli": satir["koli"], "adet": satir["adet"]}
            tuketimler[satir["kalem_id"]] = satir["tuketim"]

    stok = hesap.stoklar(baglanti)
    gruplar = hesap.sayilacaklar(baglanti)

    satilan_html, diger_html = "", ""
    for kalem in gruplar["say"]:
        varsayilan = dict(onceki_girisler.get(kalem["id"], {"koli": 0, "adet": 0}))
        # Sayim girilmisse o gunun basindaki stok, girilmemisse su anki stok gosterilir.
        varsayilan["stok"] = stok.get(kalem["id"], 0.0) + tuketimler.get(kalem["id"], 0.0)
        if kalem["satilir"]:
            satilan_html += _sayim_alani(kalem, varsayilan)
        else:
            diger_html += _sayim_alani(kalem, varsayilan)

    sarf_html = ""
    for kalem in gruplar["koli"]:
        mevcut = stok.get(kalem["id"], 0.0) + tuketimler.get(kalem["id"], 0.0)
        sarf_html += _bitti_alani(kalem, mevcut, tuketimler.get(kalem["id"], 0.0) > 0)

    elle_html = ""
    for kalem in gruplar["elle"]:
        mevcut = baglanti.execute(
            "SELECT COALESCE(SUM(miktar), 0) FROM satislar WHERE tarih = ? AND kalem_id = ?",
            (tarih, kalem["id"]),
        ).fetchone()[0]
        elle_html += (
            f'<div class="giris-satir"><div class="ad"><b>{kacir(kalem["ad"])}</b>'
            f'<div class="fiyat">{para(kalem["fiyat"])} / {kacir(kalem["birim"])}</div></div>'
            f'<input type="number" step="any" min="0" inputmode="decimal" '
            f'name="elle_{kalem["id"]}" value="{mik(mevcut) if mevcut else ""}" '
            f'placeholder="0"></div>'
        )

    def liste(icerik):
        """Giris satirlarini genis ekranda sutunlara bolen sarmalayici."""
        return f'<div class="giris-liste">{icerik}</div>'

    bolumler = ""
    if satilan_html:
        bolumler += f"<h3>Satılan ürünler — rafta kalanı yaz</h3>{liste(satilan_html)}"
    if elle_html:
        bolumler += ('<h3>Miktarı elle girilenler</h3><p class="bos">Bunlar sayımdan '
                     'bulunamaz, kaç sattığını sen yazarsın.</p>' + liste(elle_html))
    if diger_html:
        bolumler += ('<h3>Diğer sayılanlar</h3><p class="bos">Bunlar satılmıyor ama '
                     'stokları gerçeğe eşitlensin diye sayılıyor; fark fire yazılır.</p>'
                     + liste(diger_html))
    if sarf_html:
        bolumler += ('<h3>Verilen malzemeler</h3><p class="bos">Bunlar tek tek sayılmıyor. '
                     'O gün bir kolisi bittiyse işaretle; program bir koli düşer ve '
                     'tutarını günün satışlarına paylaştırır.</p>' + liste(sarf_html))
    if not bolumler:
        bolumler = ('<p class="bos">Sayılacak kalem yok. <b>Ürün &amp; Malzeme</b> '
                    'sayfasından kalemlerin "gün sonu sayımı" ayarını doldur.</p>')

    return f"""
<div class="kart"><h2>Gün sonu sayımı</h2>
<p class="bos">Kapanışta rafta ne kaldığını yaz. Program kaç sattığını, ciroyu ve kârı
kendisi hesaplar. Malzeme aldıysan <b>önce</b> Alım sayfasından gir, sonra buradan say.</p>
<form method="post" action="/satis">
<div style="max-width:320px;margin-bottom:14px">{tarih_alani(tarih)}</div>
{bolumler}
<div style="margin-top:20px"><button>Sayımı kaydet ve hesapla</button></div>
</form></div>
{_sayim_sonucu(baglanti, tarih, sayim)}"""


def _sayim_sonucu(baglanti, tarih, sayim):
    """Sayim kaydedildiyse ne hesaplandigini gosteren kart."""
    if not sayim:
        return ""
    kayitlar = baglanti.execute(
        "SELECT s.miktar, s.tutar, s.maliyet, k.ad, k.birim FROM satislar s"
        " JOIN kalemler k ON k.id = s.kalem_id WHERE s.sayim_id = ? ORDER BY s.tutar DESC",
        (sayim["id"],),
    ).fetchall()
    satirlar = "".join(
        f"<tr><td>{kacir(k['ad'])}</td>"
        f"<td class='sag'>{mik(k['miktar'])} {kacir(k['birim'])}</td>"
        f"<td class='sag'>{para(k['tutar'])}</td>"
        f"<td class='sag'>{para(k['tutar'] - k['maliyet'])}</td></tr>"
        for k in kayitlar
    ) or "<tr><td class='bos' colspan='4'>Hiçbir şey satılmamış görünüyor.</td></tr>"
    ozet = hesap.gun_ozeti(baglanti, tarih)

    # Buyuk bir stok farki sessizce fire yazilmamali, gozune sokulmali.
    uyarilar = ""
    for fark in baglanti.execute(
        "SELECT h.miktar, k.ad, k.birim, k.koli_adet FROM stok_hareketleri h"
        " JOIN kalemler k ON k.id = h.kalem_id"
        " WHERE h.kaynak_tur = 'sayim' AND h.kaynak_id = ? AND h.sebep = 'Sayım farkı'",
        (sayim["id"],),
    ).fetchall():
        buyuk = fark["koli_adet"] or 1
        if abs(fark["miktar"]) < buyuk * 0.1:
            continue
        miktar = mik(abs(fark["miktar"]), 1)
        if fark["miktar"] < 0:
            uyarilar += (
                f'<div class="uyari acil"><b>{kacir(fark["ad"])} sayımı {miktar} '
                f'{kacir(fark["birim"])} eksik çıktı</b><div class="detay">Bu miktar fire '
                f'olarak yazıldı ve kâra yansımadı. Fire, ikram ya da kaplara fazla '
                f'konulmuş olabilir. Sürekli aynı yönde çıkıyorsa reçetedeki miktarı '
                f'düzelt.</div></div>')
        else:
            uyarilar += (
                f'<div class="uyari yakin"><b>{kacir(fark["ad"])} sayımı {miktar} '
                f'{kacir(fark["birim"])} fazla çıktı</b><div class="detay">Kayıtta '
                f'olması gerekenden fazla var. Üretim ya da alım girmeyi unutmuş '
                f'olabilirsin.</div></div>')

    sarf_notu = ""
    if ozet["sarf_maliyeti"] > 0:
        sarf_notu = (f'<p class="bos" style="margin-top:12px">Satılmayan malzemeler için '
                     f'{para(ozet["sarf_maliyeti"])} harcanmış; bu tutar yukarıdaki '
                     f'kârlardan düşülmüş durumda.</p>')

    return f"""
<div class="kart"><h2>{kacir(tarih)} — sayımdan hesaplananlar</h2>{uyarilar}<table>
<tr><th>Ürün</th><th class='sag'>Satılan</th><th class='sag'>Ciro</th><th class='sag'>Kâr</th></tr>
{satirlar}
<tr><th>TOPLAM</th><th></th><th class='sag'>{para(ozet['ciro'])}</th>
<th class='sag'>{para(ozet['brut_kar'])}</th></tr>
</table>{sarf_notu}
<form method="post" action="/sayim-sil" style="margin-top:10px">
<input type="hidden" name="tarih" value="{kacir(tarih)}">
<button class="sil">Bu günün sayımını sil ve baştan gir</button></form></div>"""


# ---------------------------------------------------------------- dogrudan satis

def sayfa_satis_giris(baglanti, sorgu):
    tarih = sorgu.get("tarih", [hesap.bugun()])[0]
    urunler = hesap.kalemler(baglanti, "satilir")
    stok = hesap.stoklar(baglanti)

    satirlar = ""
    for kalem in urunler:
        stok_notu = ""
        if kalem["takip"]:
            stok_notu = f' · elde {mik(stok.get(kalem["id"], 0.0))} {kacir(kalem["birim"])}'
        satirlar += (
            f'<div class="giris-satir"><div class="ad"><b>{kacir(kalem["ad"])}</b>'
            f'<div class="fiyat">{para(kalem["fiyat"])} / {kacir(kalem["birim"])}'
            f'{stok_notu}</div></div>'
            f'<input type="number" step="any" min="0" inputmode="decimal" '
            f'name="miktar_{kalem["id"]}" placeholder="0"></div>'
        )
    if satirlar:
        satirlar = f'<div class="giris-liste">{satirlar}</div>'
    else:
        satirlar = ('<p class="bos">Satılacak ürün yok. <b>Ürün &amp; Malzeme</b> '
                    'sayfasından bir kaleme "satılır" işareti koy.</p>')

    gunun = baglanti.execute(
        "SELECT s.id, s.miktar, s.tutar, s.maliyet, k.ad, k.birim FROM satislar s"
        " JOIN kalemler k ON k.id = s.kalem_id WHERE s.tarih = ? ORDER BY s.id DESC",
        (tarih,),
    ).fetchall()
    kayit_satirlari = "".join(
        f"<tr><td>{kacir(s['ad'])}</td>"
        f"<td class='sag'>{mik(s['miktar'])} {kacir(s['birim'])}</td>"
        f"<td class='sag'>{para(s['tutar'])}</td>"
        f"<td class='sag'>{para(s['tutar'] - s['maliyet'])}</td>"
        f"<td class='sag'>{_sil_dugmesi('satis', s['id'], _dogrudan_adres(tarih))}</td></tr>"
        for s in gunun
    ) or "<tr><td class='bos' colspan='5'>Bu tarihe satış girilmemiş.</td></tr>"

    return f"""
<div class="kart"><h2>Satış girişi</h2>
<p class="bos">Sattığın kadarını yaz — tek tek de girebilirsin, gün sonunda toplu da.
Ürünün reçetesi varsa malzemeler stoktan otomatik düşer.</p>
<form method="post" action="/satis-giris">
<div style="max-width:320px;margin-bottom:14px">{tarih_alani(tarih)}</div>
{satirlar}
<div style="margin-top:20px"><button>Satışları kaydet</button></div></form></div>

<div class="kart"><h2>{kacir(tarih)} satışları</h2><table>
<tr><th>Ürün</th><th class='sag'>Miktar</th><th class='sag'>Tutar</th>
<th class='sag'>Kâr</th><th></th></tr>
{kayit_satirlari}</table></div>"""


def _sil_dugmesi(tur, kayit_id, donus):
    return (f"<form method='post' action='/sil' style='display:inline'>"
            f"<input type='hidden' name='tur' value='{tur}'>"
            f"<input type='hidden' name='id' value='{kayit_id}'>"
            f"<input type='hidden' name='donus' value='{kacir(donus)}'>"
            f"<button class='sil'>sil</button></form>")


# ---------------------------------------------------------------- uretim

def sayfa_uretim(baglanti, sorgu):
    tarih = sorgu.get("tarih", [hesap.bugun()])[0]
    receteler = baglanti.execute(
        "SELECT r.*, k.ad AS urun_ad, k.birim FROM receteler r"
        " JOIN kalemler k ON k.id = r.urun_id"
        " WHERE r.aktif = 1 AND k.aktif = 1 AND k.uretilir = 1 ORDER BY k.ad, r.sira, r.id"
    ).fetchall()
    # Her recete icin eldeki stokla kac parti cikacagi bir kere hesaplanir;
    # hem secenek yazisinda hem asagidaki tabloda kullanilir.
    kapasiteler = {r["id"]: hesap.uretim_kapasitesi(baglanti, r["id"]) for r in receteler}
    secenekler = []
    for r in receteler:
        parti = kapasiteler[r["id"]]["parti"]
        durum = ""
        if parti is not None:
            durum = (" — MALZEME YOK" if parti < 1
                     else f" — en fazla {mik(parti, 1)} parti")
        secenekler.append((
            r["id"],
            f"{r['urun_ad']}{' - ' + r['ad'] if r['ad'] else ''}"
            f" (1 {r['parti_ad']} = {mik(r['verim'])} {r['birim']}){durum}"))

    if not secenekler:
        giris = ('<p class="bos">Üretilen ürün yok. <b>Ürün &amp; Malzeme</b> sayfasından '
                 'bir kaleme "üretilir" işareti koyup reçetesini yaz.</p>')
    else:
        giris = f"""
<form method="post" action="/uretim">
<div class="satir">
  <div>{tarih_alani(tarih)}</div>
  <div><label>Ne üretildi</label>{secim("recete_id", secenekler)}</div>
  <div><label>Kaç parti</label>{sayi_alani("adet", "1", min="0")}</div>
</div>
<button>Üretimi kaydet</button></form>"""

    kayitlar = baglanti.execute(
        "SELECT u.id, u.sayi, u.miktar, u.maliyet, k.ad AS urun_ad, k.birim,"
        " r.ad AS recete_ad, r.parti_ad FROM uretimler u"
        " JOIN kalemler k ON k.id = u.kalem_id"
        " LEFT JOIN receteler r ON r.id = u.recete_id"
        " WHERE u.tarih = ? ORDER BY u.id DESC", (tarih,)
    ).fetchall()
    if kayitlar:
        satirlar = "".join(
            f"<tr><td>{kacir(k['urun_ad'])}"
            f"{' - ' + kacir(k['recete_ad']) if k['recete_ad'] else ''}</td>"
            f"<td class='sag'>{mik(k['sayi'])} {kacir(k['parti_ad'] or 'parti')}</td>"
            f"<td class='sag'>{mik(k['miktar'], 1)} {kacir(k['birim'])}</td>"
            f"<td class='sag'>{para(k['maliyet'])}</td>"
            f"<td class='sag'>{_sil_dugmesi('uretim', k['id'], '/uretim?tarih=' + tarih)}</td></tr>"
            for k in kayitlar
        )
        kayit_karti = (f'<div class="kart"><h2>{kacir(tarih)} üretimi</h2><table>'
                       f"<tr><th>Ürün</th><th class='sag'>Kaç parti</th>"
                       f"<th class='sag'>Çıkan</th><th class='sag'>Malzeme maliyeti</th>"
                       f"<th></th></tr>{satirlar}</table></div>")
    else:
        kayit_karti = (f'<div class="kart"><h2>{kacir(tarih)} üretimi</h2>'
                       '<p class="bos">Bu tarihe üretim girilmemiş.</p></div>')

    return f"""
<div class="kart"><h2>Üretim girişi</h2>
<p class="bos">Kaç parti yaptığını yaz; reçetedeki malzemeler stoktan otomatik düşer,
çıkan ürün stoğa girer. Malzeme yetmiyorsa program üretimi kaydetmez.</p>{giris}</div>
{_kapasite_karti(baglanti, receteler, kapasiteler)}
{kayit_karti}"""


def _kapasite_karti(baglanti, receteler, kapasiteler):
    """Eldeki malzemeyle neyin kac parti uretilebilecegi ve neyin bittigi."""
    if not receteler:
        return ""

    satirlar, bitenler = "", 0
    for recete in receteler:
        kapasite = kapasiteler[recete["id"]]
        parti = kapasite["parti"]
        ad = f"{recete['urun_ad']}{' - ' + recete['ad'] if recete['ad'] else ''}"
        if parti is None:
            durum = "<span class='gri'>stok takibi yok, sınırsız</span>"
            kisit = "—"
        elif parti < 1:
            bitenler += 1
            durum = "<b class='kirmizi'>üretilemez</b>"
            kisit = f"{kacir(kapasite['kisit'])} bitti"
        else:
            renk = "yesil" if parti >= 2 else "mavi"
            durum = (f"<b class='{renk}'>{mik(parti, 1)} "
                     f"{kacir(recete['parti_ad'])}</b>")
            kisit = f"önce {kacir(kapasite['kisit'])} biter"
        satirlar += (f"<tr><td>{kacir(ad)}</td><td class='sag'>{durum}</td>"
                     f"<td>{kisit}</td></tr>")

    uyari = ""
    if bitenler:
        uyari = (f'<div class="uyari bitti"><b>{bitenler} ürün şu an üretilemiyor</b>'
                 f'<div class="detay">Malzemesi bitmiş. <a href="/para">Alım / Gider</a> '
                 f'sayfasından eksik malzemeyi girince buradan üretebilirsin.</div></div>')

    return (f'<div class="kart"><h2>Eldeki malzemeyle ne kadar üretebilirsin</h2>{uyari}'
            f'<table><tr><th>Ürün</th><th class="sag">En fazla</th>'
            f'<th>Sınırlayan malzeme</th></tr>{satirlar}</table></div>')


# ---------------------------------------------------------------- stok

def sayfa_stok(baglanti, sorgu):
    liste = hesap.kalem_listesi(baglanti)
    ortalama_gun = int(sayi(ayar(baglanti, "ortalama_gun", "14"), 14))

    satirlar, toplam_deger = "", 0.0
    for baslik, grup in hesap.ture_gore(liste):
        grup_degeri = sum(k["deger"] for k in grup if k["takip"])
        satirlar += (f"<tr><th style='background:#f4f6f8;color:#0f4c75;font-size:14px'>"
                     f"{kacir(baslik)}</th><th colspan='3'></th>"
                     f"<th class='sag' style='background:#f4f6f8'>{para(grup_degeri)}</th></tr>")
        for kalem in grup:
            if not kalem["takip"]:
                satirlar += (f"<tr><td>{kacir(kalem['ad'])}</td>"
                             f"<td class='sag gri' colspan='4'>stok tutulmuyor</td></tr>")
                continue
            gunluk = hesap.gunluk_tuketim(baglanti, kalem["id"], ortalama_gun)
            kalan = f"{mik(kalem['stok'] / gunluk, 1)} gün" if gunluk > 0 else "—"
            renk = ""
            if kalem["stok"] <= 0:
                renk = ' style="color:#c1392b;font-weight:600"'
            elif kalem["kritik_seviye"] > 0 and kalem["stok"] <= kalem["kritik_seviye"]:
                renk = ' style="color:#e07b00;font-weight:600"'
            toplam_deger += kalem["deger"]
            satirlar += (
                f"<tr><td>{kacir(kalem['ad'])}</td>"
                f"<td class='sag'{renk}>{mik(kalem['stok'])} {kacir(kalem['birim'])}</td>"
                f"<td class='sag'>{mik(kalem['kritik_seviye'])}</td>"
                f"<td class='sag'>{kalan}</td>"
                f"<td class='sag'>{para(kalem['deger'])}</td></tr>"
            )

    duzeltme_gruplari = [
        (baslik, [(k["id"], f"{k['ad']} (kayıtta {mik(k['stok'])} {k['birim']})")
                  for k in grup if k["takip"]])
        for baslik, grup in hesap.ture_gore(liste)
    ]
    duzeltme_gruplari = [ikili for ikili in duzeltme_gruplari if ikili[1]]

    return f"""
<div class="kutular">{kutu("Stoğun toplam değeri", para(toplam_deger), "mavi")}</div>
<div class="kart"><h2>Stoklar</h2><table>
<tr><th>Kalem</th><th class='sag'>Eldeki</th><th class='sag'>Kritik</th>
<th class='sag'>Kaç gün yeter</th><th class='sag'>Değeri</th></tr>
{satirlar}</table></div>

<div class="kart"><h2>Sayım düzeltmesi</h2>
<p class="bos">Elle saydığında gerçek miktarı buraya yaz; program farkı fire olarak
kaydeder ve stoğu gerçeğe eşitler.</p>
<form method="post" action="/stok-duzelt"><div class="satir">
<div><label>Kalem</label>{gruplu_secim("kalem_id", duzeltme_gruplari)}</div>
<div><label>Gerçekte ne kadar var</label>{sayi_alani("miktar", min="0")}</div>
</div><button class="ikincil">Stoğu düzelt</button></form></div>"""


# ---------------------------------------------------------------- alim / gider

def sayfa_para(baglanti, sorgu):
    tarih = hesap.bugun()
    alinanlar = hesap.kalemler(baglanti, "alinir")
    alim_gruplari = [
        (baslik, [(k["id"], f"{k['ad']} ({k['birim']})") for k in grup])
        for baslik, grup in hesap.ture_gore(alinanlar)
    ]

    borclar = hesap.borc_dagilimi(baglanti)
    borc_secenek = [(b["tedarikci"], f"{b['tedarikci'] or 'Belirtilmemiş'} — {para(b['tutar'])}")
                    for b in borclar] or [("", "Borç yok")]
    borc_satirlari = "".join(
        f"<tr><td>{kacir(b['tedarikci'] or 'Belirtilmemiş')}</td>"
        f"<td class='sag'>{para(b['tutar'])}</td></tr>" for b in borclar
    ) or "<tr><td class='bos' colspan='2'>Borcun yok.</td></tr>"

    son_alimlar = baglanti.execute(
        "SELECT a.id, a.tarih, a.miktar, a.tutar, a.odeme, k.ad, k.birim FROM alimlar a"
        " JOIN kalemler k ON k.id = a.kalem_id ORDER BY a.id DESC LIMIT 10"
    ).fetchall()
    alim_satirlari = "".join(
        f"<tr><td>{kacir(a['tarih'])}</td><td>{kacir(a['ad'])}</td>"
        f"<td class='sag'>{mik(a['miktar'])} {kacir(a['birim'])}</td>"
        f"<td class='sag'>{para(a['tutar'])}</td>"
        f"<td>{'peşin' if a['odeme'] == 'pesin' else 'veresiye'}</td>"
        f"<td class='sag'>{_sil_dugmesi('alim', a['id'], '/para')}</td></tr>"
        for a in son_alimlar
    ) or "<tr><td class='bos' colspan='6'>Henüz alım girilmemiş.</td></tr>"

    # Karta girmeden kadronun durumu gorunsun; maasi yazilmamis ay varsa uyarsin.
    kadro = hesap.calisanlar(baglanti)
    yuk = hesap.aylik_maas_yuku(baglanti)
    if not kadro:
        calisan_ozeti = "Henüz çalışan girilmemiş"
    else:
        calisan_ozeti = f"{len(kadro)} kişi — aylık {para(yuk['toplam'])} maaş yükü"
        if not hesap.maas_yazildi_mi(baglanti, tarih[:7]):
            calisan_ozeti += " · bu ayın maaşı henüz yazılmadı"

    son_giderler = baglanti.execute(
        "SELECT id, tarih, aciklama, tutar FROM giderler ORDER BY id DESC LIMIT 10"
    ).fetchall()
    gider_satirlari = "".join(
        f"<tr><td>{kacir(g['tarih'])}</td><td>{kacir(g['aciklama'])}</td>"
        f"<td class='sag'>{para(g['tutar'])}</td>"
        f"<td class='sag'>{_sil_dugmesi('gider', g['id'], '/para')}</td></tr>"
        for g in son_giderler
    ) or "<tr><td class='bos' colspan='4'>Henüz gider girilmemiş.</td></tr>"

    return f"""
<div class="kutular">
{kutu("Kasadaki nakit", para(hesap.kasa(baglanti)), "yesil")}
{kutu("Toplam borç", para(hesap.borc(baglanti)), "kirmizi")}
</div>

<div class="kart"><h2>Malzeme alımı</h2>
<p class="bos">Koli/çuval ile aldıysan "kaç koli" kutusuna yaz, program adede çevirir.</p>
<form method="post" action="/alim"><div class="satir">
<div>{tarih_alani(tarih)}</div>
<div><label>Kalem</label>{gruplu_secim("kalem_id", alim_gruplari)}</div>
<div><label>Kaç koli / çuval</label>{sayi_alani("koli", min="0")}</div>
<div><label>Üstüne kaç birim</label>{sayi_alani("miktar", min="0")}</div>
<div><label>Ödenecek tutar ({kacir(para_birimi())})</label>{sayi_alani("tutar", min="0")}</div>
<div><label>Ödeme</label>{secim("odeme", [("veresiye", "Veresiye (borca yazılsın)"),
                                          ("pesin", "Peşin (kasadan çıksın)")])}</div>
</div><button>Alımı kaydet</button></form></div>

<div class="kart"><h2>Çalışanlar</h2>
<p class="bos">Kimler çalışıyor, maaşları ne kadar. Ay başında hepsinin maaşını
tek tuşla gidere yazdırmak için burası — tek tek girmene gerek yok.</p>
<p style="margin:12px 0 0"><a class="sablon" href="/calisanlar">
<b>Çalışanlar sayfasını aç</b>
{calisan_ozeti}</a></p></div>

<div class="kart"><h2>Gider</h2>
<p class="bos">Kira, elektrik, personel, yakıt gibi malzeme dışı harcamalar.
Maaşlar için yukarıdaki Çalışanlar sayfasını kullan.</p>
<form method="post" action="/gider"><div class="satir">
<div>{tarih_alani(tarih)}</div>
<div><label>Açıklama</label><input type="text" name="aciklama" placeholder="Elektrik faturası"></div>
<div><label>Tutar ({kacir(para_birimi())})</label>{sayi_alani("tutar", min="0")}</div>
</div><button>Gideri kaydet</button></form></div>

<div class="kart"><h2>Tedarikçiye ödeme</h2>
<form method="post" action="/odeme"><div class="satir">
<div>{tarih_alani(tarih)}</div>
<div><label>Tedarikçi</label>{secim("tedarikci", borc_secenek)}</div>
<div><label>Ödenen tutar ({kacir(para_birimi())})</label>{sayi_alani("tutar", min="0")}</div>
</div><button>Ödemeyi kaydet</button></form></div>

<div class="kart"><h2>Kime ne kadar borçlusun</h2><table>{borc_satirlari}</table></div>

<div class="kart"><h2>Son alımlar</h2><table>
<tr><th>Tarih</th><th>Kalem</th><th class='sag'>Miktar</th><th class='sag'>Tutar</th>
<th>Ödeme</th><th></th></tr>
{alim_satirlari}</table></div>

<div class="kart"><h2>Son giderler</h2><table>
<tr><th>Tarih</th><th>Açıklama</th><th class='sag'>Tutar</th><th></th></tr>
{gider_satirlari}</table></div>"""


# ---------------------------------------------------------------- calisanlar

GOREVLER = ("Dondurma ustası", "Tezgâhtar", "Kasiyer", "Bulaşıkçı",
            "Temizlik", "Kurye", "Çırak")


def _calisan_formu(kisi=None):
    """Yeni calisan ve duzenleme ayni formu kullanir; fark sadece gonderilen adres."""
    d = (lambda alan, varsayilan="": kacir(kisi[alan]) if kisi else varsayilan)
    sayi_d = (lambda alan: f"{kisi[alan]:g}" if kisi and kisi[alan] else "")
    gizli = (f'<input type="hidden" name="id" value="{kisi["id"]}">' if kisi else "")
    adres = "/calisan-kaydet" if kisi else "/calisan-ekle"
    dugme = "Değişikliği kaydet" if kisi else "Çalışanı ekle"
    oneriler = "".join(f'<option value="{kacir(g)}">' for g in GOREVLER)

    ayrilis = ""
    if kisi:
        ayrilis = (f'<div><label>Ayrılış tarihi</label>'
                   f'<input type="date" name="ayrilis" value="{d("ayrilis")}">'
                   f'<div class="bos" style="font-size:13px">Doldurursan listede '
                   f'"ayrıldı" görünür ve maaşı bir daha yazılmaz.</div></div>')

    return f"""<form method="post" action="{adres}">{gizli}
<div class="satir">
<div><label>Adı soyadı</label><input type="text" name="ad" value="{d('ad')}"
 placeholder="Ahmet Yılmaz" required></div>
<div><label>Görevi</label><input type="text" name="gorev" value="{d('gorev')}"
 list="gorevler" placeholder="Tezgâhtar"><datalist id="gorevler">{oneriler}</datalist></div>
<div><label>Telefon</label><input type="text" name="telefon" value="{d('telefon')}"
 placeholder="0555 111 22 33"></div>
</div>
<div class="satir">
<div><label>Eline geçen aylık maaş ({kacir(para_birimi())})</label>
{sayi_alani("maas", sayi_d("maas"), min="0")}</div>
<div><label>Üstüne SGK + vergi ({kacir(para_birimi())})</label>
{sayi_alani("sgk", sayi_d("sgk"), min="0")}</div>
<div><label>İşe giriş tarihi</label>
<input type="date" name="baslangic" value="{d('baslangic')}"></div>
{ayrilis}
</div>
<div class="satir">
<div><label>Not</label><input type="text" name="notlar" value="{d('notlar')}"
 placeholder="Hafta sonları geliyor"></div>
</div>
<button>{dugme}</button></form>"""


def sayfa_calisanlar(baglanti, sorgu):
    bugun = hesap.bugun()
    duzenlenen = None
    if sorgu.get("duzenle", [""])[0].isdigit():
        duzenlenen = hesap.calisan(baglanti, int(sorgu["duzenle"][0]))

    liste = hesap.calisanlar(baglanti, hepsi=True)
    yuk = hesap.aylik_maas_yuku(baglanti)
    calisan_sayisi = sum(1 for k in liste if k["aktif"])

    satirlar = ""
    for k in liste:
        toplam = (k["maas"] or 0) + (k["sgk"] or 0)
        if k["aktif"]:
            durum = "<span class='yesil'>çalışıyor</span>"
        else:
            durum = (f"<span class='bos'>ayrıldı"
                     f"{' · ' + kacir(gun_yaz(k['ayrilis'])) if k['ayrilis'] else ''}</span>")
        satirlar += (
            f"<tr><td><b>{kacir(k['ad'])}</b>"
            f"{'<div class=bos style=font-size:13px>' + kacir(k['notlar']) + '</div>' if k['notlar'] else ''}</td>"
            f"<td>{kacir(k['gorev'] or '—')}</td>"
            f"<td>{kacir(k['telefon'] or '—')}</td>"
            f"<td class='sag'>{para(k['maas'] or 0)}</td>"
            f"<td class='sag'>{para(k['sgk'] or 0)}</td>"
            f"<td class='sag'><b>{para(toplam)}</b></td>"
            f"<td>{durum}</td>"
            f"<td class='sag'><a href='/calisanlar?duzenle={k['id']}'>düzenle</a> "
            f"{_sil_dugmesi('calisan', k['id'], '/calisanlar')}</td></tr>"
        )
    if not satirlar:
        satirlar = ("<tr><td colspan='8' class='bos'>Henüz çalışan girilmemiş. "
                    "Aşağıdaki formdan ekle.</td></tr>")

    # Bu ayin maasi yazildi mi: yazildiysa dugme yerine bilgi gosterilir ki
    # ayni ay iki kere gidere dusmesin.
    ay = bugun[:7]
    if hesap.maas_yazildi_mi(baglanti, ay):
        maas_karti = ("<p class='bos'>Bu ayın maaşları <b>zaten gidere yazılmış</b>. "
                      "Yanlışsa aşağıdaki listeden ya da Alım / Gider ekranından "
                      "tek tek silebilirsin.</p>")
    elif calisan_sayisi == 0:
        maas_karti = "<p class='bos'>Önce çalışan ekle.</p>"
    else:
        maas_karti = f"""<p class="bos">Tek tuşla, halen çalışan {calisan_sayisi} kişinin
her biri için ayrı bir gider satırı yazılır (net maaş + SGK). Toplam
<b>{para(yuk['toplam'])}</b> kasadan düşer. Aynı ay ikinci kez yazılmaz.</p>
<form method="post" action="/maas-yaz"><div class="satir">
<div>{tarih_alani(bugun)}</div>
</div><button>Bu ayın maaşlarını gidere yaz</button></form>"""

    son_maaslar = baglanti.execute(
        "SELECT id, tarih, aciklama, tutar FROM giderler WHERE aciklama LIKE 'Maaş - %'"
        " ORDER BY tarih DESC, id DESC LIMIT 12"
    ).fetchall()
    maas_satirlari = "".join(
        f"<tr><td>{kacir(gun_yaz(g['tarih']))}</td><td>{kacir(g['aciklama'])}</td>"
        f"<td class='sag'>{para(g['tutar'])}</td>"
        f"<td class='sag'>{_sil_dugmesi('gider', g['id'], '/calisanlar')}</td></tr>"
        for g in son_maaslar
    ) or "<tr><td colspan='4' class='bos'>Henüz maaş gideri yazılmamış.</td></tr>"

    duzenleme_karti = ""
    if duzenlenen:
        duzenleme_karti = (f"<div class='kart'><h2>{kacir(duzenlenen['ad'])} — bilgileri "
                           f"düzenle</h2>{_calisan_formu(duzenlenen)}"
                           f"<p style='margin-top:12px'><a href='/calisanlar'>"
                           f"vazgeç</a></p></div>")

    return f"""
<div class="kutular">
{kutu("Çalışan sayısı", f"{calisan_sayisi} kişi", "mavi")}
{kutu("Aylık maaş yükü", para(yuk['toplam']), "kirmizi",
      alt=f"{para(yuk['net'])} net + {para(yuk['sgk'])} SGK/vergi")}
</div>

{duzenleme_karti}

<div class="kart"><h2>Çalışanlar</h2>
<p class="bos">Bu liste bir kayıt defteri — buraya yazmak tek başına kasadan para
çıkarmaz. Maaş ancak aşağıdaki <b>"maaşları gidere yaz"</b> tuşuna basınca gider olur.</p>
<table><tr><th>Ad</th><th>Görev</th><th>Telefon</th><th class='sag'>Net maaş</th>
<th class='sag'>SGK/vergi</th><th class='sag'>Dükkâna maliyeti</th><th>Durum</th><th></th></tr>
{satirlar}</table></div>

<div class="kart"><h2>Bu ayın maaşları</h2>{maas_karti}</div>

<div class="kart"><h2>Yeni çalışan ekle</h2>
<p class="bos">SGK/vergi kutusunu bilmiyorsan muhasebecine sor; asgari ücretli bir
çalışanda 2026'da net maaşın üstüne kabaca 12.000 {kacir(para_birimi())} biniyor.</p>
{_calisan_formu()}</div>

<div class="kart"><h2>Yazılmış maaş giderleri</h2>
<table><tr><th>Tarih</th><th>Kim</th><th class='sag'>Tutar</th><th></th></tr>
{maas_satirlari}</table></div>"""


# ---------------------------------------------------------------- raporlar

# Raporlar dort pencereden bakar: tek gun, hafta, ay ve tum zamanlar.
# Hepsi ayni hesaba dayanir, degisen tek sey bakilan tarih araligi.
RAPOR_KIPLERI = (("gun", "Gün"), ("hafta", "Hafta"), ("ay", "Ay"), ("tum", "Tümü"))
COK_ESKI, COK_YENI = "0001-01-01", "9999-12-31"


def _ay_kaydir(gun, adim):
    """Bir ayin ilk gununu adim kadar ileri (ya da geri) tasir."""
    toplam = gun.year * 12 + (gun.month - 1) + adim
    return datetime.date(toplam // 12, toplam % 12 + 1, 1)


def _hafta_yaz(baslangic):
    """Pazartesiden pazara: '17-23 Ağustos 2026'."""
    bitis = baslangic + datetime.timedelta(days=6)
    if baslangic.month == bitis.month:
        return f"{baslangic.day}–{bitis.day} {AYLAR[bitis.month - 1]} {bitis.year}"
    return (f"{baslangic.day} {AYLAR[baslangic.month - 1]} – "
            f"{bitis.day} {AYLAR[bitis.month - 1]} {bitis.year}")


def _rapor_araligi(kip, tarih):
    """Kip ve tarihten donemi cikarir: (bas, son, baslik, onceki, sonraki).

    'onceki' ve 'sonraki', bir onceki/sonraki donemin icinden birer tarihtir;
    tum zamanlarda ileri geri gitmek anlamsiz oldugu icin bos donerler.
    """
    try:
        gun = datetime.date.fromisoformat(tarih)
    except (ValueError, TypeError):
        gun = datetime.date.today()
    bir_hafta = datetime.timedelta(days=7)

    if kip == "hafta":
        baslangic = gun - datetime.timedelta(days=gun.weekday())   # pazartesi
        return (baslangic.isoformat(),
                (baslangic + datetime.timedelta(days=6)).isoformat(),
                _hafta_yaz(baslangic) + " haftası",
                (baslangic - bir_hafta).isoformat(),
                (baslangic + bir_hafta).isoformat())
    if kip == "ay":
        baslangic = gun.replace(day=1)
        bitis = _ay_kaydir(baslangic, 1) - datetime.timedelta(days=1)
        return (baslangic.isoformat(), bitis.isoformat(),
                f"{AYLAR[baslangic.month - 1]} {baslangic.year}",
                _ay_kaydir(baslangic, -1).isoformat(),
                _ay_kaydir(baslangic, 1).isoformat())
    if kip == "tum":
        return COK_ESKI, COK_YENI, "Tüm zamanlar", "", ""
    return (gun.isoformat(), gun.isoformat(), gun_yaz(gun.isoformat()),
            (gun - datetime.timedelta(days=1)).isoformat(),
            (gun + datetime.timedelta(days=1)).isoformat())


def _rapor_adresi(kip, tarih):
    return f"/ozet?kip={kip}&tarih={urllib.parse.quote(tarih)}"


# Alt listedeki satirlarin nasil gruplanacagi: SQL ifadesi, sutun basligi,
# kac satir gosterilecegi ve kartin basligi.
DONEM_LISTESI = {
    "gun":   ("tarih", "Tarih", 30, "Son günler"),
    "hafta": ("date(tarih, '-6 days', 'weekday 1')", "Hafta", 12, "Son haftalar"),
    "ay":    ("substr(tarih, 1, 7)", "Ay", 12, "Son aylar"),
    "tum":   ("substr(tarih, 1, 7)", "Ay", 24, "Aylara göre"),
}


def _donem_etiketi(kip, anahtar):
    """Gruplama anahtarini ('2026-08' gibi) okunur bir yaziya cevirir."""
    if kip == "gun":
        return gun_yaz(anahtar)
    if kip == "hafta":
        try:
            return _hafta_yaz(datetime.date.fromisoformat(anahtar))
        except (ValueError, TypeError):
            return anahtar
    try:
        yil, ay = anahtar.split("-")
        return f"{AYLAR[int(ay) - 1]} {yil}"
    except (ValueError, IndexError):
        return anahtar


def _donem_baglantisi(kip, anahtar):
    """Listedeki satira tiklayinca acilacak donem; ay anahtarina '-01' eklenir."""
    hedef = "ay" if kip == "tum" else kip
    return _rapor_adresi(hedef, f"{anahtar}-01" if hedef == "ay" else anahtar)


GIDER_ACIKLAMA = ("Gider, malzeme alımı dışında kalan harcamalardır: kira, "
                  "elektrik, su, personel, bakım, vergi gibi. Süt, külah, kakao "
                  "gibi malzemeye ödenen para gidere değil, \u201cAlımlar ve "
                  "ödemeler\u201d bölümüne yazılır.")


def _gider_ayrintisi(baglanti, bas, son, kip):
    """Giderlerin dökümü. Sayfa yenilenmesin diye acilir bolum olarak durur."""
    gruplar = baglanti.execute(
        "SELECT CASE WHEN TRIM(aciklama) = '' THEN 'Açıklama yazılmamış'"
        " ELSE TRIM(aciklama) END AS ad, COUNT(*) AS adet, SUM(tutar) AS tutar"
        " FROM giderler WHERE tarih BETWEEN ? AND ?"
        " GROUP BY ad ORDER BY tutar DESC", (bas, son)
    ).fetchall()
    kayitlar = baglanti.execute(
        "SELECT tarih, aciklama, tutar FROM giderler WHERE tarih BETWEEN ? AND ?"
        " ORDER BY tarih DESC, id DESC", (bas, son)
    ).fetchall()

    if not kayitlar:
        return f"""
<details class="acilir"><summary>Gider ne demek?</summary>
<div class="ic"><p class="bos">Bu dönemde hiç gider girilmemiş.</p>
<p class="bos">{GIDER_ACIKLAMA}</p></div></details>"""

    toplam = sum(k["tutar"] for k in kayitlar)
    # Cubuklar toplam gidere gore olcekleniyor: uzunluk dogrudan "payi ne kadar"
    # demek oluyor, ayri bir yuzde sutununa gerek kalmiyor.
    grup_cubuklari = grafik.cubuk_listesi(
        [(g["ad"] + (f" ({g['adet']} kez)" if g["adet"] > 1 else ""),
          para(g["tutar"]), grafik.oran(g["tutar"], toplam),
          f"{g['ad']} — {para(g['tutar'])}, giderlerin"
          f" %{grafik.oran(g['tutar'], toplam):.0f}'i")
         for g in gruplar],
        grafik.TURUNCU,
        "Gider kalemleri, büyükten küçüğe; çubuk uzunluğu toplam gider içindeki payı.")
    kayit_satirlari = "".join(
        f"<tr><td>{kacir(gun_yaz(k['tarih'], False))}</td>"
        f"<td>{kacir(k['aciklama'] or '—')}</td>"
        f"<td class='sag'>{para(k['tutar'])}</td></tr>"
        for k in kayitlar
    )
    # Tek gunde gruplama listeyle ayni seyi gosterir; sadece uzun donemde anlamli.
    grup_bolumu = "" if kip == "gun" else f"""
<h3>Neye harcanmış</h3>{grup_cubuklari}
<p class="grafik-alt">Toplam <b>{para(toplam)}</b></p>
<h3>Tek tek kayıtlar</h3>"""

    return f"""
<details class="acilir"><summary>Giderler neye harcandı?</summary>
<div class="ic"><p class="bos">{GIDER_ACIKLAMA}</p>{grup_bolumu}
<table><tr><th>Tarih</th><th>Ne için</th><th class='sag'>Tutar</th></tr>
{kayit_satirlari}
<tr><td><b>Toplam</b></td><td></td><td class='sag'><b>{para(toplam)}</b></td></tr></table>
<p class="bos" style="margin-top:10px">Gider eklemek ya da silmek için
<a href="/para">Alım / Gider</a> sayfasını kullan.</p></div></details>"""


# Uzun tablolarda bastan kac satir gorunecek; gerisi acilir bolumde durur.
KISA_LISTE = 6


def _tablo_bolumu(genislikler, basliklar, satirlar, ozet_metni):
    """Grafigin rakam ikizi: yerinde acilan bolumde duran tam tablo.

    Grafik goz icin, tablo kesin rakam icin. Grafikteki her deger burada da
    yaziyor, boylece hicbir bilgi yalnizca renge ya da uzunluga kalmiyor.
    """
    if not satirlar:
        return ""
    grup = ("<colgroup>"
            + "".join(f'<col style="width:{g}">' for g in genislikler)
            + "</colgroup>")
    return (f"<details class='acilir'><summary>{ozet_metni}</summary>"
            f"<div class='ic'><table class='sabit'>{grup}<tr>{basliklar}</tr>"
            f"{''.join(satirlar)}</table></div></details>")


KISA_AYLAR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz",
              "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]

# Sutun altina kac yazi sigar: gunler dar oldugu icin en az, aylar en cok.
ETIKET_SIKLIGI = {"gun": 8, "hafta": 6, "ay": 12, "tum": 12}


def _sutun_etiketi(kip, anahtar, yil_yaz):
    """Grafigin altina yazilacak kisa donem adi: '19', '17 Ağu', 'Ağu'."""
    try:
        if kip in ("ay", "tum"):
            yil, ay = anahtar.split("-")[:2]
            kisa = KISA_AYLAR[int(ay) - 1]
            return f"{kisa} {yil[2:]}" if yil_yaz else kisa
        gun = datetime.date.fromisoformat(anahtar)
    except (ValueError, IndexError, TypeError):
        return anahtar
    if kip == "hafta":
        return f"{gun.day} {KISA_AYLAR[gun.month - 1]}"
    # Ay basinda sadece "1" yazmak kafa karistiriyor; ay adi da yazilsin.
    return f"1 {KISA_AYLAR[gun.month - 1]}" if gun.day == 1 else str(gun.day)


def sayfa_ozet(baglanti, sorgu):
    kip = sorgu.get("kip", ["gun"])[0]
    if kip not in dict(RAPOR_KIPLERI):
        kip = "gun"
    tarih = sorgu.get("tarih", [hesap.bugun()])[0]
    bas, son, baslik, onceki, sonraki = _rapor_araligi(kip, tarih)
    ozet = hesap.aralik_ozeti(baglanti, bas, son)

    sekmeler = '<div class="sekmeler">' + "".join(
        f'<a href="{_rapor_adresi(anahtar, tarih)}" '
        f'class="{"aktif" if anahtar == kip else ""}">{etiket}</a>'
        for anahtar, etiket in RAPOR_KIPLERI
    ) + "</div>"

    # --- 1. serit: hangi donem --------------------------------------------
    if kip == "tum":
        donem_karti = (f'<div class="kart tam"><div class="donem-ust">'
                       f'<h2>{kacir(baslik)}</h2></div>'
                       f'<p class="bos" style="text-align:center;margin:6px 0 0">'
                       f'Bugüne kadar girilmiş bütün kayıtlar.</p></div>')
    else:
        donem_karti = f"""
<div class="kart tam"><div class="donem-ust">
<a class="ok-dugme" href="{_rapor_adresi(kip, onceki)}">◀</a>
<h2>{kacir(baslik)}</h2>
<a class="ok-dugme" href="{_rapor_adresi(kip, sonraki)}">▶</a></div>
<form method="get" action="/ozet" style="margin:14px auto 0; max-width:420px">
<input type="hidden" name="kip" value="{kacir(kip)}">
<div style="display:flex; gap:10px; align-items:end">
<div style="flex:1; min-width:0">{tarih_alani(bas)}</div>
<button class="ikincil">Göster</button></div></form></div>"""

    # --- 2. serit: uc buyuk rakam -----------------------------------------
    # Gunluk ortalama tek gun icin anlamsiz; hafta/ayda ciro kutusunun altina yazilir.
    ciro_alt = "bu dönemde satılan"
    if kip != "gun" and ozet["satis_gunu"]:
        ciro_alt = (f"{ozet['satis_gunu']} günde · günde ortalama "
                    f"{para(ozet['ciro'] / ozet['satis_gunu'])}")

    # --- 3. serit: para nereye gitti --------------------------------------
    # Seridin tamami cironun kendisi: maliyet + gider + net kar. Gider ve maliyet
    # ciroyu asarsa (zarar edilen donem) serit toplam gidere gore olcekleniyor ve
    # cironun nerede bittigi bir cizgiyle isaretleniyor.
    maliyet, gider_t, net = (ozet["satis_maliyeti"], ozet["gider"], ozet["net_kar"])
    serit_toplam = maliyet + gider_t + max(net, 0.0)
    parcalar = [("Satılanların maliyeti", para(maliyet),
                 grafik.oran(maliyet, serit_toplam), grafik.MAVI),
                ("Giderler", para(gider_t),
                 grafik.oran(gider_t, serit_toplam), grafik.TURUNCU)]
    isaret, zarar_notu = None, ""
    if net >= 0:
        parcalar.append(("Net kâr", para(net),
                         grafik.oran(net, serit_toplam), grafik.YESIL))
        aria = (f"Ciro {para(ozet['ciro'])}; bunun"
                f" %{grafik.oran(maliyet, serit_toplam):.0f}'i satılanların maliyeti,"
                f" %{grafik.oran(gider_t, serit_toplam):.0f}'i giderler,"
                f" %{grafik.oran(net, serit_toplam):.0f}'i net kâr.")
    else:
        isaret = (grafik.oran(ozet["ciro"], serit_toplam),
                  f"Ciro burada bitiyor: {para(ozet['ciro'])}")
        zarar_notu = (f'<p class="grafik-alt" style="color:#c1392b">Maliyet ve gider'
                      f' cironun üstünde: bu dönem <b style="color:#c1392b">'
                      f'{para(-net)} zarar</b>.</p>')
        aria = (f"Maliyet ve giderler toplamı {para(serit_toplam)}, ciro"
                f" {para(ozet['ciro'])}; aradaki fark {para(-net)} zarar.")
    serit = grafik.yigilmis_serit(parcalar, aria, isaret) + zarar_notu

    akis = f"""
<div class="kart"><h2>Para nereye gitti?</h2>
{serit}
<table class="akis">
<tr><td class="isaret"></td><td>Ciro
<span class="aciklama">satıştan gelen para</span></td>
<td class="sag">{para(ozet['ciro'])}</td></tr>
<tr><td class="isaret">−</td><td>Satılanların maliyeti
<span class="aciklama">satılan ürünlerin içine giren malzeme</span></td>
<td class="sag">{para(ozet['satis_maliyeti'])}</td></tr>
<tr class="sonuc"><td class="isaret">=</td><td>Brüt kâr</td>
<td class="sag">{para(ozet['brut_kar'])}</td></tr>
<tr><td class="isaret">−</td><td>Giderler
<span class="aciklama">kira, elektrik, personel, vergi…</span></td>
<td class="sag">{para(ozet['gider'])}</td></tr>
<tr class="sonuc"><td class="isaret">=</td><td>Net kâr</td>
<td class="sag">{para(ozet['net_kar'])}</td></tr>
</table>
{_gider_ayrintisi(baglanti, bas, son, kip)}</div>"""

    # --- 4. serit: kar hesabina girmeyen para hareketleri -----------------
    alimlar = f"""
<div class="kart"><h2>Alımlar ve ödemeler</h2>
<p class="bos">Bunlar yukarıdaki kâr hesabına girmez: alınan malzeme stoğa yazılır,
kâr ancak o malzeme satıldığında ortaya çıkar. Buradaki rakamlar paranın
kasadan ne zaman çıktığını gösterir.</p>
<table>
<tr><td>Peşin alımlar</td><td class='sag'>{para(ozet['alim_pesin'])}</td></tr>
<tr><td>Veresiye alımlar <span class="bos">(borca yazıldı)</span></td>
<td class='sag'>{para(ozet['alim_veresiye'])}</td></tr>
<tr><td>Tedarikçiye ödenen</td><td class='sag'>{para(ozet['borc_odemesi'])}</td></tr>
<tr><td>Üretime giren malzeme</td><td class='sag'>{para(ozet['uretim_maliyeti'])}</td></tr>
</table></div>"""

    # --- 5. serit: urunler -------------------------------------------------
    urunler = baglanti.execute(
        "SELECT k.ad, k.birim, SUM(s.miktar) AS miktar, SUM(s.tutar) AS ciro,"
        " SUM(s.tutar - s.maliyet) AS kar FROM satislar s"
        " JOIN kalemler k ON k.id = s.kalem_id WHERE s.tarih BETWEEN ? AND ?"
        " GROUP BY k.id ORDER BY kar DESC", (bas, son)
    ).fetchall()
    # Grafikte ilk alti urun; cubuklar en cok kazandirana gore olcekli.
    en_yuksek_kar = max((u["kar"] for u in urunler), default=0.0)
    urun_cubuklari = grafik.cubuk_listesi(
        [(u["ad"], para(u["kar"]), grafik.oran(u["kar"], en_yuksek_kar),
          f"{u['ad']} — {mik(u['miktar'])} {u['birim']} satıldı,"
          f" ciro {para(u['ciro'])}, kâr {para(u['kar'])}")
         for u in urunler[:KISA_LISTE]],
        grafik.MAVI,
        "Ürünler kâra göre sıralı; çubuk uzunluğu en çok kazandırana oranla.")
    urun_satirlari = [
        f"<tr><td>{kacir(u['ad'])}</td>"
        f"<td class='sag'>{mik(u['miktar'])} {kacir(u['birim'])}</td>"
        f"<td class='sag'>{para(u['ciro'])}</td>"
        f"<td class='sag'>{para(u['kar'])}</td></tr>"
        for u in urunler
    ]
    urun_karti = f"""
<div class="kart"><h2>En çok kazandıran ürünler</h2>
{urun_cubuklari if urunler else grafik.bos("Bu dönemde satış kaydı yok.")}
{_tablo_bolumu(("30%", "20%", "25%", "25%"),
               "<th>Ürün</th><th class='sag'>Satılan</th><th class='sag'>Ciro</th>"
               "<th class='sag'>Kâr</th>",
               urun_satirlari,
               f"{len(urun_satirlari)} ürünün tamamını tablo olarak gör")}</div>"""

    # --- 6. serit: donemin gidisati ---------------------------------------
    grup, sutun, adet, liste_basligi = DONEM_LISTESI[kip]
    donemler = baglanti.execute(
        f"SELECT {grup} AS anahtar, SUM(tutar) AS ciro, SUM(tutar - maliyet) AS brut"
        " FROM satislar GROUP BY anahtar ORDER BY anahtar DESC LIMIT ?", (adet,)
    ).fetchall()
    donem_satirlari = []
    for donem in donemler:
        anahtar = donem["anahtar"] or ""
        # Bakilan donem listede de isaretli dursun: '2026-08' ayi '2026-08-01' ile eslesir.
        vurgu = " style='background:#f4f9ff'" if anahtar == bas[:len(anahtar)] else ""
        donem_satirlari.append(
            f"<tr{vurgu}><td><a href='{_donem_baglantisi(kip, anahtar)}'>"
            f"{kacir(_donem_etiketi(kip, anahtar))}</a></td>"
            f"<td class='sag'>{para(donem['ciro'])}</td>"
            f"<td class='sag'>{para(donem['brut'])}</td></tr>")
    # Grafik zaman siralamasi ister: tablo yeniden eskiye, grafik soldan saga.
    eskiden = list(reversed(donemler))
    tavan = max((d["ciro"] for d in eskiden), default=0.0)
    yillar = {(d["anahtar"] or "")[:4] for d in eskiden}
    ham_etiketler = [_sutun_etiketi(kip, d["anahtar"] or "", len(yillar) > 1)
                     for d in eskiden]
    etiketler = grafik.etiket_seyrelt(ham_etiketler, ETIKET_SIKLIGI[kip])
    noktalar = []
    for donem, etiket in zip(eskiden, etiketler):
        anahtar = donem["anahtar"] or ""
        secili = anahtar == bas[:len(anahtar)]
        noktalar.append((
            etiket, grafik.oran(donem["ciro"], tavan), secili,
            _donem_baglantisi(kip, anahtar),
            f"{_donem_etiketi(kip, anahtar)} — ciro {para(donem['ciro'])},"
            f" brüt kâr {para(donem['brut'])}"))
    gidisat_grafigi = grafik.sutun_grafigi(
        noktalar, grafik.kisa_para(tavan, para_birimi()),
        f"{liste_basligi}: ciro sütunları, eskiden yeniye.",
        "Koyu sütun şu an baktığın dönem. Sütuna tıklayınca o dönemin raporu açılır.")

    gidisat_karti = f"""
<div class="kart"><h2>{liste_basligi}</h2>
{gidisat_grafigi if noktalar else grafik.bos("Henüz satış kaydı yok.")}
{_tablo_bolumu(("40%", "30%", "30%"),
               f"<th>{sutun}</th><th class='sag'>Ciro</th><th class='sag'>Brüt kâr</th>",
               donem_satirlari, "Rakamları tablo olarak gör")}</div>"""

    return f"""{sekmeler}
{donem_karti}
<div class="kutular baslik">
{kutu("Ciro", para(ozet["ciro"]), "mavi", ciro_alt)}
{kutu("Net kâr", para(ozet["net_kar"]),
      "yesil" if ozet["net_kar"] >= 0 else "kirmizi", "giderler düşüldükten sonra")}
{kutu("Kasa değişimi", para(ozet["kasa_degisimi"]),
      "yesil" if ozet["kasa_degisimi"] >= 0 else "kirmizi",
      "kâr değil; kasaya net giren para")}
</div>
{akis}
{alimlar}
{urun_karti}
{gidisat_karti}
{_tahmin_baglantisi(baglanti)}"""


def _tahmin_baglantisi(baglanti):
    """Raporlar gecmisi anlatir; ileriye bakmak isteyen tahmine gitsin."""
    if ayar(baglanti, "tahmin_acik", "1") != "1":
        return ""
    return """
<div class="kart"><h2>İleriye bakmak için</h2>
<p class="bos">Buradaki rakamlar olan biteni anlatır. Önümüzdeki günlerde ne
kadar satacağını ve ne üretmen gerektiğini tahmin sayfası söyler.</p>
<p style="margin:12px 0 0"><a class="sablon" href="/tahmin">
<b>Tahmin sayfasını aç</b>
Yedi günlük hava, ciro tahmini ve üretim önerisi</a></p></div>"""


# ---------------------------------------------------------------- tahmin

def _hava_serisi(baglanti, gun_sayisi=7):
    """Onumuzdeki gunlerin hava kartlari: simge, sicaklik ve yagis ihtimali."""
    bugun = datetime.date.today()
    kartlar = ""
    for kaydirma in range(gun_sayisi):
        tarih = (bugun + datetime.timedelta(days=kaydirma)).strftime("%Y-%m-%d")
        satir = hava.gun(baglanti, tarih)
        if satir is None or satir["en_yuksek"] is None:
            continue
        gun_adi = ("Bugün" if kaydirma == 0 else
                   "Yarın" if kaydirma == 1 else
                   tahmin_modulu.GUN_ADLARI[(bugun + datetime.timedelta(days=kaydirma)).weekday()])
        alt = kacir(hava.hadise_metni(satir["hadise"])
                    or ("yağışlı" if satir["yagmurlu"] else ""))
        oran = hava.ihtimal(satir)
        if oran is not None:
            yagmur = f'<b>☔ %{oran}</b> yağış ihtimali'
            alt = f"{alt}<br>{yagmur}" if alt else yagmur
        kartlar += kutu(gun_adi,
                        f'<span class="hava-simge">{hava.simge(satir)}</span>'
                        f'{satir["en_yuksek"]:.0f}°', "mavi", alt)
    return kartlar


OZEL_GUN_KARTI = """
<div class="kart"><h2>Özel günler</h2>
<p class="bos">Bayram, festival, okul tatili gibi günleri takvime yazarsan
tahmin o günleri ayrı öğrenir.</p>
<p style="margin:12px 0 0"><a class="sablon" href="/ozel-gunler">
<b>Özel gün takvimini aç</b>
Bayram, festival, tatil — girilen günler ve öğrenilenler</a></p></div>"""


def sayfa_tahmin(baglanti, sorgu):
    if not hava.sehir_secili_mi(baglanti):
        return """
<div class="kart"><h2>Önce şehri seç</h2>
<p class="bos">Tahmin, resmi MGM hava verisine dayanıyor. Hangi ildesin?
<a href="/ayarlar">Ayarlar</a> sayfasının en altındaki "Hava ve tahmin"
bölümünden ilini seç, gerisi kendiliğinden gelir.</p></div>""" + OZEL_GUN_KARTI

    model, gunler, uretimler = tahmin_modulu.ileri_tahmin(baglanti, 7)
    sehir = kacir(ayar(baglanti, "sehir", ""))
    son = kacir(ayar(baglanti, "hava_son_kontrol", "")) or "henüz alınmadı"

    hava_karti = f"""
<div class="kart"><h2>{sehir} — hava</h2>
<div class="kutular">{_hava_serisi(baglanti) or
    '<p class="bos">Hava verisi henüz alınamadı. İnternet bağlantını kontrol edip '
    'aşağıdaki düğmeye bas.</p>'}</div>
<p class="bos">Kaynak: resmi MGM tahmini · yağış ihtimali: Open-Meteo ·
son güncelleme: {son}</p>
<form method="post" action="/hava-guncelle" style="margin-top:8px">
<button class="ikincil">Havayı şimdi güncelle</button></form></div>"""

    if not gunler:
        return hava_karti + f"""
<div class="kart"><h2>Satış tahmini</h2>
<div class="uyari yakin"><b>Tahmin henüz çalışmıyor</b>
<div class="detay">{kacir(tahmin_modulu.durum_metni(model))}</div></div>
<p class="bos">Sistem şu anda arka planda çalışıyor: her günün havası
kaydediliyor. Sen gün sonu satışlarını girdikçe program "sıcaklık şu kadar
olduğunda ciro şu kadar oluyor" ilişkisini kendisi çıkaracak. Bunun için
senin bir şey yapman gerekmiyor.</p></div>""" + OZEL_GUN_KARTI

    satirlar = ""
    for gun in gunler:
        vurgu = " style='background:#f4f9ff'" if gun["tarih"] == hesap.bugun() else ""
        satirlar += (
            f"<tr{vurgu}><td><b>{kacir(gun['gun_adi'])}</b>"
            f"<div class='bos' style='font-size:13px'>{kacir(gun['tarih'])}</div></td>"
            f"<td>{kacir(gun['hava'])}</td>"
            f"<td class='sag'><b>{para(gun['ciro'])}</b>"
            f"<div class='bos' style='font-size:13px'>{tl(gun['alt'])} – {tl(gun['ust'])}</div></td>"
            f"</tr>"
        )

    # Urun kirilimi: sadece bugun ve yarin, yoksa tablo okunmaz hale geliyor
    kirilim = ""
    for gun in gunler[:2]:
        satir_html = ""
        for kalem_id, miktar in sorted(gun["urunler"].items(), key=lambda i: -i[1]):
            kalem = hesap.kalem(baglanti, kalem_id)
            if kalem is None or miktar < 0.05:
                continue
            satir_html += (f"<tr><td>{kacir(kalem['ad'])}</td>"
                           f"<td class='sag'>{mik(miktar, 1)} {kacir(kalem['birim'])}</td></tr>")
        if satir_html:
            kirilim += (f"<h3>{kacir(gun['gun_adi'])} — ne kadar satılır</h3>"
                        f"<table>{satir_html}</table>")

    uretim_html = ""
    for oneri in uretimler:
        if oneri["acik"] <= 0:
            durum = (f"<span class='yesil'>elde yeterli var "
                     f"({mik(oneri['elde'], 1)} {kacir(oneri['kalem']['birim'])})</span>")
        else:
            birim = kacir(oneri["kalem"]["birim"])
            # Tam kazan cirpildigi icin cikan miktar acigi asabiliyor; artan
            # yaziliyor ki dukkan bilerek fazla uretti gorsun.
            artan = (f", {mik(oneri['artacak'], 1)} {birim} artar"
                     if oneri["artacak"] > 0.05 else "")
            durum = (f"<b>{oneri['parti']} {kacir(oneri['parti_ad'])} üret</b> "
                     f"<div class='bos' style='font-size:13px'>"
                     f"{mik(oneri['acik'], 1)} {birim} açık → "
                     f"{mik(oneri['cikacak'], 1)} {birim} çıkar{artan}</div>")
        uretim_html += (
            f"<tr><td>{kacir(oneri['kalem']['ad'])}</td>"
            f"<td class='sag'>{mik(oneri['gereken'], 1)} {kacir(oneri['kalem']['birim'])}</td>"
            f"<td class='sag'>{mik(oneri['elde'], 1)}</td>"
            f"<td class='sag'>{durum}</td></tr>"
        )
    uretim_karti = ""
    if uretim_html:
        uretim_karti = f"""
<div class="kart"><h2>Önümüzdeki {len(gunler)} gün için ne üretmeli</h2>
<p class="bos">Tahmin edilen satışların reçetelerden hesaplanan malzeme
ihtiyacı, eldeki stokla karşılaştırıldı.</p><table>
<tr><th>Ürün</th><th class='sag'>Gereken</th><th class='sag'>Elde</th>
<th class='sag'>Öneri</th></tr>{uretim_html}</table></div>"""

    return f"""{hava_karti}
<div class="kart"><h2>Satış tahmini</h2>
<p class="bos">{kacir(tahmin_modulu.durum_metni(model))}</p>
<table><tr><th>Gün</th><th>Hava</th><th class='sag'>Tahmini ciro</th></tr>
{satirlar}</table>
<p class="bos" style="margin-top:12px">Alttaki küçük rakamlar tahminin
gerçekleşebileceği aralık. Program geçmişte ortalama {para(model['hata_payi'])}
yanılmış; aralık buradan çıkıyor. Veri arttıkça aralık daralır.</p>
{kirilim}</div>
{uretim_karti}
{OZEL_GUN_KARTI}"""


# ---------------------------------------------------------------- ozel gunler

def _ozel_gun_satiri(kayit, bugun):
    """Takvim tablosunun bir satiri: tarih, etiket ve dugmeler."""
    gun_sayisi = takvim.gun_araligi(kayit["baslangic"], kayit["bitis"])
    if gun_sayisi == 1:
        tarih = gun_yaz(kayit["baslangic"])
    else:
        tarih = (f"{gun_yaz(kayit['baslangic'])} – {gun_yaz(kayit['bitis'])}"
                 f" <span class='bos'>({gun_sayisi} gün)</span>")

    # Programin urettigi satir silinse ilk acilista geri gelir; kapatilir.
    if kayit["kaynak"] == "elle":
        dugme = (f'<form method="post" action="/ozel-gun-sil" style="display:inline">'
                 f'<input type="hidden" name="id" value="{kayit["id"]}">'
                 f'<button class="sil">sil</button></form>')
    else:
        dugme = ""
    dugme += (f'<form method="post" action="/ozel-gun-durum" style="display:inline">'
              f'<input type="hidden" name="id" value="{kayit["id"]}">'
              f'<button class="mini">{"kapat" if kayit["aktif"] else "aç"}</button>'
              f'</form>')

    sonu = kayit["bitis"] < bugun
    stil = " style='opacity:.45'" if not kayit["aktif"] or sonu else ""
    durum = "" if kayit["aktif"] else " <span class='rozet'>kapalı</span>"
    return (f"<tr{stil}><td>{tarih}</td>"
            f"<td>{kacir(kayit['ad'])}{durum}</td>"
            f"<td><span class='rozet'>{kacir(kayit['etiket'])}</span></td>"
            f"<td class='sag'>{dugme}</td></tr>")


def sayfa_ozel_gunler(baglanti, sorgu):
    bugun = hesap.bugun()
    yil = datetime.date.today().year
    kayitlar = takvim.liste(baglanti)

    # Etiket ozeti: bu yil kac gun dusuyor ve model onu ogrenebilmis mi.
    # Ekranin asil ogrettigi sey bu - "3 gun" kurali burada gorunuyor.
    model = tahmin_modulu.model_kur(baglanti)
    gunler = {}
    for kayit in kayitlar:
        if not kayit["aktif"] or not kayit["baslangic"].startswith(str(yil)):
            continue
        gunler[kayit["etiket"]] = (gunler.get(kayit["etiket"], 0)
                                   + takvim.gun_araligi(kayit["baslangic"], kayit["bitis"]))

    etiket_satirlari = ""
    for etiket, adet in sorted(gunler.items(), key=lambda i: -i[1]):
        ogrenilen = model["etiket_katsayilari"].get(etiket)
        if ogrenilen:
            durum = (f"<span class='yesil'>normalin {mik(ogrenilen[0], 2)} katı</span>"
                     f"<div class='bos' style='font-size:13px'>{ogrenilen[1]} günlük "
                     f"satıştan çıktı</div>")
        else:
            durum = ("<span class='bos'>henüz öğrenilmedi — bu etiketten en az "
                     f"{tahmin_modulu.EN_AZ_ETIKET_GUN} gün satış girilmeli</span>")
        etiket_satirlari += (f"<tr><td><span class='rozet'>{kacir(etiket)}</span></td>"
                             f"<td class='sag'>{adet} gün</td><td>{durum}</td></tr>")

    # Takvim, yila gore ayrilir; gecmis yillar da dursun ki model neyi neden
    # ogrendigi sorulunca geriye bakilabilsin.
    takvim_satirlari, onceki_yil = "", None
    for kayit in kayitlar:
        kayit_yili = kayit["baslangic"][:4]
        if kayit_yili != onceki_yil:
            onceki_yil = kayit_yili
            takvim_satirlari += (f"<tr><th colspan='4' style='background:#f4f6f8;"
                                 f"color:#0f4c75;font-size:14px'>{kacir(kayit_yili)}</th></tr>")
        takvim_satirlari += _ozel_gun_satiri(kayit, bugun)

    if not takvim_satirlari:
        takvim_satirlari = "<tr><td colspan='4' class='bos'>Takvim boş.</td></tr>"

    eksikler = takvim.eksik_bayram_yillari(baglanti)
    uyari = ""
    if eksikler:
        liste = ", ".join(f"{ad} {y}" for ad, y in eksikler)
        uyari = (f"<div class='uyari acil'><b>Bayram tarihi eksik</b>"
                 f"<div class='detay'>{kacir(liste)} takvimde yok. Dini bayramlar "
                 f"her yıl kaydığı için elle giriliyor; aşağıdaki formdan ekle.</div></div>")

    oneriler = "".join(f'<option value="{kacir(e)}">' for e in takvim.etiketler(baglanti))

    return f"""{uyari}
<div class="kart"><h2>Etiketler</h2>
<p class="bos">Program her <b>etiket</b> için tek bir katsayı öğrenir: "bu etiketli
günlerde ciro normalin kaç katı". Aynı etiketi taşıyan günler aynı havuza girer —
29 Ekim ile 23 Nisan birlikte "Resmi Tatil" katsayısını besler, o yüzden tek başına
bir güne göre çok daha çabuk öğrenilir.</p>
<table><tr><th>Etiket</th><th class='sag'>{yil}'da</th><th>Durum</th></tr>
{etiket_satirlari or "<tr><td colspan='3' class='bos'>Etiket yok.</td></tr>"}</table></div>

<div class="kart"><h2>Takvim</h2>
<p class="bos">Resmi tatiller, bayramlar, arifeler ve Ramazan ayı her açılışta
kendiliğinden yazılır. Bunlar silinmez — dükkânda fark yaratmıyorsa
<b>kapat</b>, model o günleri hiç görmez.</p>
<table><tr><th>Tarih</th><th>Ne</th><th>Etiket</th><th></th></tr>
{takvim_satirlari}</table></div>

<div class="kart"><h2>Yeni özel gün ya da dönem ekle</h2>
<p class="bos">Köprü günü, festival, yol çalışması, fındık toplama dönemi…
Satışı normalden farklı yapan her şey buraya girilebilir. Tek günlükse bitiş
tarihini boş bırak.</p>
<form method="post" action="/ozel-gun-ekle">
<div class="satir">
<div><label>Adı</label><input type="text" name="ad" placeholder="Fındık toplama 2026"></div>
<div><label>Etiket</label>
<input type="text" name="etiket" list="etiketler" placeholder="Fındık Toplama">
<datalist id="etiketler">{oneriler}</datalist></div>
</div>
<div class="satir">
<div><label>Başlangıç</label><input type="date" name="baslangic" value="{kacir(bugun)}"></div>
<div><label>Bitiş</label><input type="date" name="bitis"></div>
</div>
<button>Takvime ekle</button></form>
<p class="bos" style="margin-top:12px"><b>Etiketi nasıl seçmeli:</b> tekrar eden
bir şeyse her yıl <u>aynı</u> etiketi yaz — "Fındık Toplama 2026" değil, sadece
"Fındık Toplama". Program yılları birleştirip tek katsayı öğrenir. Yılda
{tahmin_modulu.EN_AZ_ETIKET_GUN} günün altında kalan etiketler öğrenilemez.</p>
</div>"""


# ---------------------------------------------------------------- menuler

def _gun_adi(tarih, bugun=None):
    """Tarihi yakinliga gore soyler: 'bugün', 'yarın', 'Cumartesi'."""
    bugun = bugun or datetime.date.today()
    fark = (tarih - bugun).days
    if fark <= 0:
        return "bugün"
    if fark == 1:
        return "yarın"
    return tahmin_modulu.GUN_ADLARI[tarih.weekday()]


def _gecis_simgesi(menu):
    return "❄️" if menu["kosul"] == "soguk" else "☀️" if menu["kosul"] == "sicak" else "🔁"


def _gecis_nedeni(plan):
    """'Cumartesi 14°, Pazar 15°, Pazartesi 13° — üç gün üst üste 17°C'nin altında'"""
    menu = plan["menu"]
    gunler = ", ".join(f"{tahmin_modulu.GUN_ADLARI[tarih.weekday()]} {derece:.0f}°"
                       for tarih, derece in plan["dizi"])
    yon = "altında" if menu["kosul"] == "soguk" else "üstünde"
    return (f"{gunler} — {len(plan['dizi'])} gün üst üste en yüksek sıcaklık "
            f"{mik(menu['esik'], 1)}°C'nin {yon}.")


def _gecis_dugmeleri(plan, plan_baglantisi=True):
    menu = plan["menu"]
    return (f'<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:10px">'
            f'<form method="post" action="/menu-gec"><input type="hidden" name="id" '
            f'value="{menu["id"]}"><button>Şimdi geç</button></form>'
            + (f'<a class="ok-dugme" href="/menuler">Planın tamamı</a>' if plan_baglantisi else "")
            + f'<form method="post" action="/menu-ertele"><input type="hidden" name="id" '
            f'value="{menu["id"]}"><button class="ikincil">Şimdi değil</button></form></div>')


def _gecis_ozeti(plan):
    """Ana menudeki kisa gecis uyarisi."""
    menu = plan["menu"]
    ne_zaman = _gun_adi(plan["tarih"])
    satirlar = [f'<div class="detay">Neden: {kacir(_gecis_nedeni(plan))}</div>']
    uretilen = [k for k in plan["kapananlar"] if k["uretme"] and k["elde"] > 0]
    if uretilen:
        satirlar.append(
            f'<div class="detay"><b>Kapanacak çeşitlerden yeni üretim yapma.</b> Elde '
            + ", ".join(f"{kacir(k['kalem']['ad'])} {mik(k['elde'], 1)} {kacir(k['kalem']['birim'])}"
                        for k in sorted(uretilen, key=lambda k: -k["elde"])[:4])
            + (f" ve {len(uretilen) - 4} çeşit daha" if len(uretilen) > 4 else "") + " var.</div>")
    if plan["alinacaklar"]:
        satirlar.append('<div class="detay">Almadan geçme: '
                        + ", ".join(kacir(a["kalem"]["ad"]) for a in plan["alinacaklar"])
                        + "</div>")
    sayilar = (f'{len(plan["kapananlar"])} ürün kapanacak, '
               f'{len(plan["acilanlar"])} ürün açılacak.')
    return (f'<div class="uyari mevsim"><b>{_gecis_simgesi(menu)} Menü geçişi önerisi: '
            f'{kacir(menu["ad"])} — {kacir(ne_zaman)}</b><div class="detay">{sayilar}</div>'
            f'{"".join(satirlar)}{_gecis_dugmeleri(plan)}</div>')


def _gecis_plani_karti(plan):
    """Menuler sayfasindaki tam plan."""
    menu = plan["menu"]
    ne_zaman = _gun_adi(plan["tarih"])
    ek = "" if ne_zaman in ("bugün", "yarın") else f" ({gun_yaz(plan['tarih'].isoformat(), False)})"

    kapanan_satirlar = ""
    for k in sorted(plan["kapananlar"], key=lambda k: -k["elde"]):
        kalem = k["kalem"]
        birim = kacir(kalem["birim"])
        biter = "—"
        if k["biter"] is not None and k["elde"] > 0:
            biter = f"{mik(k['biter'], 1)} gün"
        gecmis = "—"
        if k["gecmis_gun"] >= menuler.EN_AZ_GECMIS:
            gecmis = (f"{mik(k['gecmis_ort'], 2)} {birim} "
                      f"<span class='bos' style='font-size:13px'>(normalde "
                      f"{mik(k['genel_ort'], 2)}, {k['gecmis_gun']} gün)</span>")
        kapanan_satirlar += (
            f"<tr><td>{kacir(kalem['ad'])}"
            + (" <span class='rozet'>üretme</span>" if k["uretme"] and k["elde"] > 0 else "")
            + f"</td><td class='sag'>{mik(k['elde'], 1) + ' ' + birim if kalem['takip'] else '—'}</td>"
            f"<td class='sag'>{mik(k['gunluk'], 2)} {birim}</td><td class='sag'>{biter}</td>"
            f"<td class='sag'>{gecmis}</td></tr>")
    artacak = [k for k in plan["kapananlar"] if k["artacak"] > 0.05]
    artacak_notu = ""
    if artacak and plan["kalan_gun"] > 0:
        artacak_notu = (
            f'<p class="bos" style="margin-top:8px">Bugünkü satış hızıyla {plan["kalan_gun"]} '
            f'günde bitmeyecekler: ' + ", ".join(
                f"{kacir(k['kalem']['ad'])} (~{mik(k['artacak'], 1)} {kacir(k['kalem']['birim'])})"
                for k in sorted(artacak, key=lambda k: -k["artacak"])[:6])
            + ". Geçişten sonra da satılabilirler; ürün kapanınca stoğu silinmez.</p>")

    acilan = "".join(
        f"<tr><td>{kacir(a['kalem']['ad'])}</td><td class='sag'>"
        + (f"{mik(a['gunluk'], 1)} {kacir(a['kalem']['birim'])}" if a["gunluk"]
           else "<span class='bos'>ilk kez açılıyor</span>") + "</td></tr>"
        for a in plan["acilanlar"])

    alinacak = "".join(
        f"<tr><td>{kacir(a['kalem']['ad'])}</td>"
        + (f"<td class='sag'>{mik(a['elde'], 2)}</td><td class='sag'><b>{mik(a['eksik'], 2)} "
           f"{kacir(a['kalem']['birim'])}</b></td>" if a["eksik"] is not None else
           "<td class='sag'>0</td><td class='sag'><b>stokta yok</b></td>")
        + f"<td>{kacir(a['kalem']['tedarikci'])}</td></tr>"
        for a in plan["alinacaklar"])

    fiyat = "".join(
        f"<li><b>{kacir(u['kalem']['ad'])}</b> son {menuler.FIYAT_GUN} günde "
        f"{para(u['eski'])} → {para(u['yeni'])} (%{u['artis'] * 100:.0f} arttı) · "
        f"{kacir(', '.join(u['urunler']))}</li>"
        for u in plan["fiyat_uyarilari"])

    return f"""
<div class="kart tam"><h2>{_gecis_simgesi(menu)} Menü geçişi önerisi: {kacir(menu['ad'])}
— {kacir(ne_zaman)}{kacir(ek)}</h2>
<p><b>Neden:</b> {kacir(_gecis_nedeni(plan))}</p>
<p class="bos">Kararı sen verirsin. Geçince kapanan ürünler satış ve üretim
ekranlarından kalkar; geçmiş kayıtları ve stokları silinmez.</p>
{_gecis_dugmeleri(plan, plan_baglantisi=False)}
<h3>Kapanacak ürünler ({len(plan['kapananlar'])})</h3>
<div style="overflow-x:auto"><table>
<tr><th>Ürün</th><th class='sag'>Elde</th><th class='sag'>Son 14 gün, günde</th>
<th class='sag'>Bitmesi</th><th class='sag'>Geçmişte bu havada, günde</th></tr>
{kapanan_satirlar or "<tr><td class='bos' colspan='5'>Kapanacak ürün yok.</td></tr>"}
</table></div>{artacak_notu}
<h3>Açılacak ürünler ({len(plan['acilanlar'])})</h3>
<table><tr><th>Ürün</th><th class='sag'>Geçen sefer günde</th></tr>
{acilan or "<tr><td class='bos' colspan='2'>Açılacak ürün yok.</td></tr>"}</table>
<h3>Almadan geçme</h3>
<p class="bos">Açılacak ürünlerin ilk {menuler.ILK_HAFTA} günü için. Geçen sefer satışı olan
ürünlerde miktar o satıştan hesaplanır; ilk kez açılanda sadece stokta olmayan malzeme söylenir.</p>
<table><tr><th>Malzeme</th><th class='sag'>Elde</th><th class='sag'>Al</th><th>Tedarikçi</th></tr>
{alinacak or "<tr><td class='bos' colspan='4'>Eksik malzeme yok.</td></tr>"}</table>
{f'<h3>Pahalanan malzemeler</h3><ul>{fiyat}</ul>' if fiyat else ''}
</div>"""


def _menu_formu(baglanti, menu, secili, urunler_gruplu, gecerli_id):
    kutular = ""
    for baslik, grup in urunler_gruplu:
        kutular += (f"<h3>{kacir(baslik)}</h3><div class='giris-liste'>"
                    + "".join(f"<div style='padding:5px 0'>"
                              f"{kutucuk('urun_' + str(k['id']), k['id'] in secili, k['ad'])}</div>"
                              for k in grup)
                    + "</div>")
    gecerli_mi = menu["id"] == gecerli_id
    rozet = " <span class='rozet ur'>şu an geçerli</span>" if gecerli_mi else ""
    gec_dugmesi = "" if gecerli_mi else (
        f'<form method="post" action="/menu-gec" style="display:inline">'
        f'<input type="hidden" name="id" value="{menu["id"]}">'
        f'<button class="ikincil">Bu menüye şimdi geç</button></form>')
    return f"""
<div class="kart"><h2>{kacir(menu['ad'])}{rozet}</h2>
<form method="post" action="/menu-kaydet">
<input type="hidden" name="id" value="{menu['id']}">
<div class="satir">
<div><label>Menünün adı</label><input type="text" name="ad" value="{kacir(menu['ad'])}" required></div>
<div><label>Geçiş önerisi</label>{secim("kosul", menuler.KOSULLAR, menu["kosul"])}</div>
<div><label>Eşik (en yüksek sıcaklık, °C)</label>{sayi_alani("esik", mik(menu["esik"], 1))}</div>
</div>
<p class="bos">Bu menüde satılan ürünleri işaretle. Hiçbir menüde işaretli olmayan ürün her
zaman satılır. Malzemeleri işaretlemen gerekmez: sadece kapanan ürünlerde geçen malzeme
(bir çeşidin aroması gibi) ürünle birlikte kendiliğinden kapanır.</p>
{kutular}
<div style="margin-top:14px"><button>Kaydet</button></div></form>
<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:10px">{gec_dugmesi}
<form method="post" action="/menu-sil" style="display:inline">
<input type="hidden" name="id" value="{menu['id']}">
<button class="sil">Menüyü sil</button></form></div></div>"""


def sayfa_menuler(baglanti, sorgu):
    gecerli = menuler.gecerli(baglanti)
    gecis = menuler.son_gecis(baglanti)
    liste = menuler.liste(baglanti)
    plan = menuler.oneri(baglanti)

    if gecerli:
        durum = (f"<p>Şu an <b>{kacir(gecerli['ad'])}</b> geçerli — "
                 f"{kacir(gun_yaz(gecis['tarih'], False))} tarihinden beri.</p>")
    elif liste:
        durum = "<p class='bos'>Henüz hiçbir menüye geçilmedi; bütün ürünler olduğu gibi duruyor.</p>"
    else:
        durum = ""
    gecmis = menuler.gecisler(baglanti)
    gecmis_html = ""
    if len(gecmis) > 1:
        gecmis_html = ("<h3>Geçmiş geçişler</h3><table>"
                       + "".join(f"<tr><td>{kacir(gun_yaz(g['tarih'], False))}</td>"
                                 f"<td>{kacir(g['ad'])}</td></tr>" for g in gecmis)
                       + "</table>")

    tanitim = f"""
<div class="kart tam"><h2>Menü dönemleri</h2>
<p class="bos">Mevsime göre değişen menüler: dondurmacının yaz ve kış menüsü, lokantanın yaz ve
kış sebzeleri. Menüye geçince o menüde olmayan ürünler satış, sayım ve üretim ekranlarından
kalkar; geri dönünce yerine gelir. Hiçbir kayıt silinmez.</p>
<p class="bos">Bir menüye "hava soğuyunca öner" dersen program 7 günlük hava tahminine bakar:
en yüksek sıcaklık {menuler.GUN_ARDISIK} gün üst üste eşiğin altına inecekse ana menüde bir
geçiş planı çıkarır — hangi gün, kapanacak ürünlerden elde ne kaldığı, ne alınması gerektiği.
Geçişi sen yaparsın.</p>
{durum}{gecmis_html}</div>"""

    urunler = menuler.secilebilir_urunler(baglanti)
    gruplu = hesap.ture_gore(urunler)
    kartlar = "".join(
        _menu_formu(baglanti, m, menuler.urunleri(baglanti, m["id"]), gruplu,
                    gecerli["id"] if gecerli else None)
        for m in liste)

    yeni = f"""
<div class="kart"><h2>Yeni menü</h2>
<form method="post" action="/menu-ekle"><div class="satir">
<div><label>Menünün adı</label><input type="text" name="ad" placeholder="Kış menüsü" required></div>
<div><label>Geçiş önerisi</label>{secim("kosul", menuler.KOSULLAR, "")}</div>
<div><label>Eşik (en yüksek sıcaklık, °C)</label>{sayi_alani("esik", "17")}</div>
</div>
<div class="roller">{kutucuk("simdiki", True, "Şu an satılan ürünlerle başlasın")}</div>
<button>Menüyü ekle</button></form></div>"""

    return tanitim + (_gecis_plani_karti(plan) if plan else "") + kartlar + yeni


def islem_menu_ekle(baglanti, veri):
    ad = veri.get("ad", [""])[0].strip()
    if not ad:
        return "/menuler", "!Menünün adını yaz."
    if baglanti.execute("SELECT 1 FROM menuler WHERE ad = ?", (ad,)).fetchone():
        return "/menuler", f"!{ad} adında bir menü zaten var."
    urunler = []
    if "simdiki" in veri:
        urunler = [satir[0] for satir in baglanti.execute(
            "SELECT id FROM kalemler WHERE satilir = 1 AND aktif = 1")]
    kosul = veri.get("kosul", [""])[0]
    menuler.ekle(baglanti, ad, kosul if kosul in dict(menuler.KOSULLAR) else "",
                 sayi(veri.get("esik", ["0"])[0]), urunler)
    return "/menuler", f"{ad} eklendi. Ürünlerini işaretleyip kaydet."


def islem_menu_kaydet(baglanti, veri):
    menu_id = int(sayi(veri.get("id", ["0"])[0]))
    ad = veri.get("ad", [""])[0].strip()
    if menuler.menu(baglanti, menu_id) is None:
        return "/menuler", "!Menü bulunamadı."
    if not ad:
        return "/menuler", "!Menünün adını yaz."
    if baglanti.execute("SELECT 1 FROM menuler WHERE ad = ? AND id <> ?",
                        (ad, menu_id)).fetchone():
        return "/menuler", f"!{ad} adında başka bir menü var."
    urunler = [kimlik for anahtar in veri
               if (kimlik := alan_kimligi(anahtar, "urun_")) is not None]
    kosul = veri.get("kosul", [""])[0]
    menuler.kaydet(baglanti, menu_id, ad, kosul if kosul in dict(menuler.KOSULLAR) else "",
                   sayi(veri.get("esik", ["0"])[0]), urunler)
    # Gecerli menu degistiyse ekrandaki acik/kapali durum da hemen uysun.
    gecerli = menuler.gecerli(baglanti)
    if gecerli and gecerli["id"] == menu_id:
        menuler.uygula(baglanti, menu_id)
        baglanti.commit()
    return "/menuler", f"{ad} kaydedildi."


def islem_menu_gec(baglanti, veri):
    menu_id = int(sayi(veri.get("id", ["0"])[0]))
    menu = menuler.menu(baglanti, menu_id)
    if menu is None:
        return "/menuler", "!Menü bulunamadı."
    sonuc = menuler.gec(baglanti, menu_id)
    return "/", (f"{menu['ad']} geçerli: {len(sonuc['kapanan'])} ürün kapandı, "
                 f"{len(sonuc['acilan'])} ürün açıldı.")


def islem_menu_ertele(baglanti, veri):
    menuler.ertele(baglanti, int(sayi(veri.get("id", ["0"])[0])))
    return "/", f"Tamam, {menuler.ERTELE_GUN} gün sormayacağım."


def islem_menu_sil(baglanti, veri):
    menu_id = int(sayi(veri.get("id", ["0"])[0]))
    menu = menuler.menu(baglanti, menu_id)
    if menu is None:
        return "/menuler", "!Menü bulunamadı."
    menuler.sil(baglanti, menu_id)
    return "/menuler", f"{menu['ad']} silindi. Ürünler olduğu gibi duruyor."


# ---------------------------------------------------------------- kalemler

def sayfa_kalemler(baglanti, sorgu):
    liste = hesap.kalem_listesi(baglanti, sadece_aktif=False)
    satirlar = ""
    for baslik, grup in hesap.ture_gore(liste):
        satirlar += (f"<tr><th colspan='6' style='background:#f4f6f8;color:#0f4c75;"
                     f"font-size:14px'>{kacir(baslik)} ({len(grup)})</th></tr>")
        for kalem in grup:
            soluk = "" if kalem["aktif"] else " style='opacity:.5'"
            satirlar += (
                f"<tr{soluk}><td><a href='/kalem?id={kalem['id']}'>"
                f"<b>{kacir(kalem['ad'])}</b></a>"
                f"<div style='margin-top:4px'>{rozetler(kalem)}</div></td>"
                f"<td class='sag'>{kacir(kalem['birim'])}</td>"
                f"<td class='sag'>{para(kalem['birim_fiyat']) if kalem['alinir'] else '—'}</td>"
                f"<td class='sag'>{para(kalem['fiyat']) if kalem['satilir'] else '—'}</td>"
                f"<td class='sag'>{mik(kalem['stok']) if kalem['takip'] else '—'}</td>"
                f"<td class='sag'><a href='/kalem?id={kalem['id']}'>düzenle</a></td></tr>"
            )
    if not satirlar:
        satirlar = "<tr><td class='bos' colspan='6'>Henüz kalem yok.</td></tr>"

    return f"""
<div class="kart"><h2>Yeni kalem ekle</h2>
<p class="bos">Dükkanda adı, birimi ve stoğu olan her şey bir kalemdir: un da,
hamur da, ekmek de. Ne olduğunu işaretlediğin kutucuklar belirler.</p>
<form method="post" action="/kalem-ekle"><div class="satir">
<div><label>Adı</label><input type="text" name="ad" placeholder="Un" required></div>
<div><label>Birimi</label><input type="text" name="birim" placeholder="kg" value="adet"></div>
<div><label>Türü (listeleri gruplar)</label>{tur_alani(baglanti)}</div>
</div>
<div class="roller">
{kutucuk("alinir", True, "Satın alınır")}
{kutucuk("uretilir", False, "Üretilir (reçetesi var)")}
{kutucuk("satilir", False, "Satılır")}
</div>
<button>Ekle ve düzenlemeye geç</button></form></div>

<div class="kart"><h2>Bütün kalemler</h2>
<p class="bos">Türe göre gruplanmış. Tür sadece düzen içindir, hiçbir hesaba girmez —
istediğin başlığı yazabilirsin.</p><table>
<tr><th>Kalem</th><th class='sag'>Birim</th><th class='sag'>Alış</th>
<th class='sag'>Satış</th><th class='sag'>Stok</th><th></th></tr>
{satirlar}</table></div>"""


SAYIM_TARZLARI = [
    ("yok", "Gün sonu sayımında sorulmasın"),
    ("say", "Rafta kalanı sayarım"),
    ("koli", "Tek tek saymam, 'bir kolisi bitti' derim"),
    ("elle", "Sattığım miktarı elle yazarım"),
]


def sayfa_kalem(baglanti, sorgu):
    kalem_id = int(sayi(sorgu.get("id", ["0"])[0]))
    kalem = hesap.kalem(baglanti, kalem_id)
    if kalem is None:
        return '<div class="kart"><p class="bos">Kalem bulunamadı.</p></div>'

    stok = hesap.stoklar(baglanti).get(kalem_id, 0.0)
    return f"""
<div class="kart"><h2>{kacir(kalem['ad'])}</h2>
<p class="bos">{rozetler(kalem)} · stokta {mik(stok)} {kacir(kalem['birim'])} ·
birim maliyeti {para(hesap.birim_maliyet(baglanti, kalem_id))}</p>
<form method="post" action="/kalem-kaydet">
<input type="hidden" name="id" value="{kalem_id}">
<div class="satir">
<div><label>Adı</label><input type="text" name="ad" value="{kacir(kalem['ad'])}" required></div>
<div><label>Birimi</label><input type="text" name="birim" value="{kacir(kalem['birim'])}"></div>
<div><label>Türü (listeleri gruplar)</label>{tur_alani(baglanti, kalem['tur'])}</div>
<div><label>Sıra (küçük olan üstte)</label>{sayi_alani("sira", mik(kalem['sira']))}</div>
</div>
<div class="roller">
{kutucuk("alinir", kalem["alinir"], "Satın alınır")}
{kutucuk("uretilir", kalem["uretilir"], "Üretilir (reçetesi üretimde düşer)")}
{kutucuk("satilir", kalem["satilir"], "Satılır")}
{kutucuk("takip", kalem["takip"], "Stoğu tutulsun")}
{kutucuk("aktif", kalem["aktif"], "Kullanımda")}
</div>
<div class="satir">
<div><label>Alış fiyatı (bir {kacir(kalem['birim'])} için, {kacir(para_birimi())})</label>
     {sayi_alani("birim_fiyat", f"{kalem['birim_fiyat']:.2f}", min="0")}</div>
<div><label>Satış fiyatı (bir {kacir(kalem['birim'])} için, {kacir(para_birimi())})</label>
     {sayi_alani("fiyat", f"{kalem['fiyat']:.2f}", min="0")}</div>
<div><label>Kritik seviye (altına düşünce uyarır)</label>
     {sayi_alani("kritik_seviye", mik(kalem['kritik_seviye']), min="0")}</div>
</div>
<div class="satir">
<div><label>Toplu kabın adı</label>
     <input type="text" name="koli_ad" value="{kacir(kalem['koli_ad'])}" placeholder="koli"></div>
<div><label>Bir {kacir(kalem['koli_ad'])} kaç {kacir(kalem['birim'])}</label>
     {sayi_alani("koli_adet", mik(kalem['koli_adet']), min="0")}</div>
<div><label>Tedarikçi</label>
     <input type="text" name="tedarikci" value="{kacir(kalem['tedarikci'])}"></div>
</div>
<div class="satir">
<div><label>Gün sonu sayımı</label>{secim("sayim_tarzi", SAYIM_TARZLARI, kalem["sayim_tarzi"])}</div>
<div><label>Açıklama (sadece ekranda görünür)</label>
     <input type="text" name="aciklama" value="{kacir(kalem['aciklama'])}"></div>
</div>
<div class="roller">{kutucuk("dagit", kalem["dagit"],
    "Satılmaz ama harcanır — tutarını günün satışlarına paylaştır (kaşık, peçete)")}</div>
<button>Kaydet</button></form>
<form method="post" action="/kalem-sil" style="margin-top:10px">
<input type="hidden" name="id" value="{kalem_id}">
<button class="sil">Bu kalemi sil</button></form></div>
{_recete_karti(baglanti, kalem)}"""


def _recete_karti(baglanti, kalem):
    """Kalemin recetelerini duzenleme karti."""
    if kalem["uretilir"]:
        aciklama = ("Bu kalem üretiliyor: aşağıdaki malzemeler <b>üretim girdiğinde</b> "
                    "stoktan düşer. Birden fazla reçete yazabilirsin — dondurmada olduğu "
                    "gibi aynı stoğa farklı karışımlar akabilir.")
    else:
        aciklama = ("Bu kalem üretilmiyor: aşağıdaki malzemeler <b>her satışta</b> "
                    "stoktan düşer. Külahın içine konan dondurma, porsiyonun içine giren "
                    "et böyle yazılır.")

    baskalari = [k for k in hesap.kalemler(baglanti, sadece_aktif=False)
                 if k["id"] != kalem["id"]]
    malzeme_gruplari = [
        (baslik, [(k["id"], f"{k['ad']} ({k['birim']})") for k in grup])
        for baslik, grup in hesap.ture_gore(baskalari)
    ]

    kartlar = ""
    for recete in hesap.receteler(baglanti, kalem["id"], sadece_aktif=False):
        satirlar = ""
        toplam = 0.0
        for satir in hesap.recete_satirlari(baglanti, recete["id"]):
            birim_maliyet = hesap.birim_maliyet(baglanti, satir["kalem_id"])
            toplam += satir["miktar"] * birim_maliyet
            satirlar += (
                f"<tr><td>{kacir(satir['ad'])}</td>"
                f"<td style='width:130px'>"
                f"{sayi_alani('satir_' + str(satir['id']), mik(satir['miktar'], 4), min='0')}</td>"
                f"<td>{kacir(satir['birim'])}</td>"
                f"<td class='sag'>{para(satir['miktar'] * birim_maliyet)}</td>"
                f"<td class='sag'><button class='sil' formaction='/recete-satir-sil' "
                f"name='satir_id' value='{satir['id']}'>çıkar</button></td></tr>"
            )
        if not satirlar:
            satirlar = "<tr><td class='bos' colspan='5'>Reçete boş.</td></tr>"

        birim = (toplam / recete["verim"]) if recete["verim"] else 0.0
        baslik = recete["ad"] or "Reçete"
        kartlar += f"""
<div class="kart" style="background:#fafbfc">
<h3 style="margin-top:0">{kacir(baslik)}</h3>
<form method="post" action="/recete-kaydet">
<input type="hidden" name="recete_id" value="{recete['id']}">
<div class="satir">
<div><label>Reçetenin adı</label>
     <input type="text" name="ad" value="{kacir(recete['ad'])}" placeholder="Sade"></div>
<div><label>Bir üretime verdiğin ad</label>
     <input type="text" name="parti_ad" value="{kacir(recete['parti_ad'])}" placeholder="kazan"></div>
<div><label>1 {kacir(recete['parti_ad'])} kaç {kacir(kalem['birim'])} çıkarır</label>
     {sayi_alani("verim", mik(recete['verim'], 4), min="0")}</div>
</div>
<table><tr><th>Malzeme</th><th>Miktar</th><th>Birim</th><th class='sag'>Tutar</th><th></th></tr>
{satirlar}
<tr><th>TOPLAM</th><th colspan='2'></th><th class='sag'>{para(toplam)}</th><th></th></tr>
</table>
<p class="bos" style="margin:10px 0">Çıkan bir {kacir(kalem['birim'])}
başına malzeme maliyeti: <b>{para(birim)}</b></p>
<button>Reçeteyi kaydet</button>
<button class="sil" formaction="/recete-sil">reçeteyi sil</button>
</form>
<form method="post" action="/recete-satir-ekle" style="margin-top:12px">
<input type="hidden" name="recete_id" value="{recete['id']}">
<div class="satir">
<div><label>Malzeme ekle</label>{gruplu_secim("kalem_id", malzeme_gruplari)}</div>
<div><label>Miktar</label>{sayi_alani("miktar", min="0")}</div>
<div style="align-self:end"><button class="ikincil">Satır ekle</button></div>
</div></form></div>"""

    if not kartlar:
        kartlar = '<p class="bos">Bu kalemin reçetesi yok.</p>'

    return f"""
<div class="kart"><h2>Reçete</h2>
<p class="bos">{aciklama}</p>
{kartlar}
<form method="post" action="/recete-ekle" style="margin-top:10px">
<input type="hidden" name="urun_id" value="{kalem['id']}">
<button class="ikincil">Yeni reçete ekle</button></form></div>"""


# ---------------------------------------------------------------- ayarlar

def sayfa_ayarlar(baglanti, sorgu):
    fiyat_satirlari = ""
    for baslik, grup in hesap.ture_gore(hesap.kalem_listesi(baglanti)):
        fiyat_satirlari += (f"<tr><th colspan='4' style='background:#f4f6f8;"
                            f"color:#0f4c75;font-size:14px'>{kacir(baslik)}</th></tr>")
        for kalem in grup:
            alis = f"{kalem['birim_fiyat']:.2f}"
            satis = f"{kalem['fiyat']:.2f}"
            fiyat_satirlari += (
                f"<tr><td>{kacir(kalem['ad'])}"
                f"<div class='bos' style='font-size:13px'>{mik(kalem['stok'])} "
                f"{kacir(kalem['birim'])} var</div></td>"
                f"<td>{sayi_alani('bfiyat_' + str(kalem['id']), alis, min='0')}</td>"
                f"<td>{sayi_alani('sfiyat_' + str(kalem['id']), satis, min='0')}</td>"
                f"<td>{sayi_alani('kritik_' + str(kalem['id']), mik(kalem['kritik_seviye']), min='0')}</td>"
                f"</tr>"
            )
    fiyat_satirlari = fiyat_satirlari or "<tr><td class='bos' colspan='4'>Henüz kalem yok.</td></tr>"

    modlar = [
        ("sayim", "Gün sonu sayımı (rafta kalanı sayarım)"),
        ("dogrudan", "Doğrudan satış girişi (kaç sattığımı yazarım)"),
        ("ikisi", "İkisi de dursun, sekmeyle geçeyim"),
    ]

    return f"""
<div class="kart"><h2>Ürün ve malzemeler</h2>
<p class="bos">Yeni ürün eklemek, reçete yazmak, bir kalemin birimini ya da
kolisini değiştirmek için burası.</p>
<p style="margin:12px 0 0"><a class="sablon" href="/kalemler">
<b>Ürün &amp; Malzeme sayfasını aç</b>
Kalem listesi, reçeteler ve satış şekilleri</a></p>
<p style="margin:12px 0 0"><a class="sablon" href="/menuler">
<b>Menü dönemlerini aç</b>
Yaz ve kış menüsü, mevsim geçişi ve geçiş önerisi</a></p></div>

<div class="kart"><h2>Genel ayarlar</h2>
<form method="post" action="/ayarlar"><div class="satir">
<div><label>Dükkan adı</label><input type="text" name="dukkan_adi"
     value="{kacir(ayar(baglanti, 'dukkan_adi'))}"></div>
<div><label>Para birimi</label><input type="text" name="para_birimi"
     value="{kacir(ayar(baglanti, 'para_birimi', 'TL'))}"></div>
<div><label>Satış nasıl girilsin</label>
     {secim("satis_girisi", modlar, ayar(baglanti, "satis_girisi", "ikisi"))}</div>
</div><div class="satir">
<div><label>Kaç günlük kalınca uyarayım</label>
     {sayi_alani("uyari_gun", kacir(ayar(baglanti, "uyari_gun", "2")), min="0")}</div>
<div><label>Alırken kaç günlük alınsın</label>
     {sayi_alani("dolum_gun", kacir(ayar(baglanti, "dolum_gun", "7")), min="1")}</div>
<div><label>Günlük tüketim kaç günün ortalaması olsun</label>
     {sayi_alani("ortalama_gun", kacir(ayar(baglanti, "ortalama_gun")), min="1")}</div>
</div><button>Ayarları kaydet</button></form></div>

{_hava_ayar_karti(baglanti)}

{_guvenlik_karti(baglanti)}

<div class="kart"><h2>Fiyatlar</h2>
<p class="bos">Hepsini tek ekrandan güncellemek için. Alım girdiğinde alış fiyatı zaten
kendiliğinden güncellenir. Bir kalemin diğer ayarları için
<a href="/kalemler">Ürün &amp; Malzeme</a> sayfasına git.</p>
<form method="post" action="/ayarlar"><table>
<tr><th>Kalem</th><th>Alış fiyatı</th><th>Satış fiyatı</th><th>Kritik seviye</th></tr>
{fiyat_satirlari}</table>
<div style="margin-top:14px"><button>Fiyatları kaydet</button></div></form></div>"""


def _guvenlik_karti(baglanti):
    """Ayarlar sayfasindaki hesap bolumu."""
    kisi = getattr(_istek, "kullanici", None)

    if kisi:
        ad = kacir(kisi["ad"] or kisi["eposta"])
        return f"""
<div class="kart"><h2>Hesabın</h2>
<div class="uyari yakin"><b>{ad} olarak girdin</b>
<div class="detay">Kullanıcı adın: <b>{kacir(kisi["eposta"])}</b> &nbsp;·&nbsp;
Dükkanın: <b>{kacir(kisi["dukkan_adi"])}</b><br>
Bu dükkanın kayıtları kendi dosyasında tutulur; başka hiçbir dükkan onları
göremez, sen de başka dükkanınkini göremezsin.</div></div>
<form method="post" action="/sifre-kur"><div class="satir">
<div>{sifre_alani("sifre", f"Yeni şifre (en az {hesaplar.EN_KISA_SIFRE} karakter)")}
{SIFRE_GOSTER}</div>
</div><button class="ikincil">Şifreyi değiştir</button></form>
<p class="bos" style="margin-top:10px">Şifreni değiştirince başka bir cihazda
açık kalmış oturumlar etkilenmez; oradan çıkmak için o cihazda Çıkış'a bas.</p>
</div>"""

    return f"""
<div class="kart"><h2>Güvenlik</h2>
<p class="bos">Şu an giriş yok: programı açan herkes doğrudan giriyor.
<b>Dükkân içinde, kendi wifi'inde çalışırken bunun sakıncası yok</b> — dışarıdan
kimse o ağda değil. Ama programı internete açarsan adresi bilen herkes kasayı,
ciroyu ve tedarikçileri görür ve değiştirebilir. O durumda hesap şart.</p>
<p class="bos">Aşağıdan hesap kurarsan <b>bu dükkanın şu anki bütün kayıtları
olduğu gibi kalır</b>, sadece önüne giriş ekranı gelir.</p>
<form method="post" action="/hesap-kur">
<div class="satir">
<div><label>Kullanıcı adı</label>
<input type="text" name="eposta" autocomplete="username"></div>
<div><label>Adın soyadın</label><input type="text" name="ad"></div>
</div>
<div class="satir">
<div>{sifre_alani("sifre", f"Şifre (en az {hesaplar.EN_KISA_SIFRE} karakter)")}</div>
<div>{sifre_alani("sifre2", "Şifre (tekrar)")}</div>
</div>{SIFRE_GOSTER}
<button style="margin-top:12px">Hesabı kur ve girişi aç</button></form></div>"""


def _hava_ayar_karti(baglanti):
    """Ayarlar sayfasindaki hava/tahmin bolumu.

    Il listesi onbellekten okunur; bu sayfa acilirken aga cikilmaz.
    """
    iller = hava.il_listesi_onbellek(baglanti) if ayar(baglanti, "il_listesi", "") else []
    oneriler = "".join(f'<option value="{kacir(il["ad"])}">' for il in iller)
    secili = ayar(baglanti, "sehir", "")
    son = ayar(baglanti, "hava_son_kontrol", "")

    kaynaklar = [
        ("mgm+arsiv", "MGM (resmi) + geçmiş boşlukları Open-Meteo'dan"),
        ("mgm", "Sadece MGM (resmi)"),
        ("openmeteo", "Sadece Open-Meteo"),
    ]
    durum = (f"Seçili il: <b>{kacir(secili)}</b> · son güncelleme: "
             f"{kacir(son) or 'henüz alınmadı'}"
             if secili else
             "Henüz il seçilmedi. Şehir seçilene kadar program hiçbir şekilde "
             "internete çıkmaz.")

    return f"""
<div class="kart"><h2>Hava ve tahmin</h2>
<p class="bos">{durum}</p>
<p class="bos">Program hava verisini <b>resmi MGM servisinden</b> çeker ve
onu geçmiş satışlarla karşılaştırıp ileriye dönük tahmin üretir. İnternet
yoksa program normal çalışmaya devam eder, sadece tahmin susar.</p>
<form method="post" action="/sehir-kaydet"><div class="satir">
<div><label>İl</label><input type="text" name="sehir" list="iller"
     value="{kacir(secili)}" placeholder="Ordu">
     <datalist id="iller">{oneriler}</datalist></div>
<div><label>Hava verisi nereden gelsin</label>
     {secim("hava_kaynak", kaynaklar, ayar(baglanti, "hava_kaynak", "mgm+arsiv"))}</div>
<div style="align-self:end"><button>İli kaydet ve havayı çek</button></div>
</div></form>
<form method="post" action="/ayarlar" style="margin-top:6px">
<input type="hidden" name="tahmin_formu" value="1">
<div class="roller">{kutucuk("tahmin_acik", ayar(baglanti, "tahmin_acik", "1") == "1",
    "Tahmin açık olsun (ana menünün solunda ve raporlarda görünür)")}</div>
<button class="ikincil">Kaydet</button></form></div>"""


# ---------------------------------------------------------------- form islemleri

def islem_sehir_kaydet(baglanti, veri):
    ayar_yaz(baglanti, "hava_kaynak", veri.get("hava_kaynak", ["mgm+arsiv"])[0])
    baglanti.commit()

    il_adi = veri.get("sehir", [""])[0].strip()
    if not il_adi:
        return "/ayarlar", "İl adı yazılmamış."
    il = hava.sehir_kaydet(baglanti, il_adi)
    if il is None:
        return "/ayarlar", (f"'{il_adi}' MGM il listesinde bulunamadı. "
                            f"İl adını tam yaz (ilçe değil, il).")
    ileri, geri, kaynak = hava.guncelle(baglanti)
    if not ileri:
        return "/ayarlar", (f"{il['ad']} kaydedildi ama hava verisi alınamadı — "
                            f"internet bağlantını kontrol et.")
    return "/ayarlar", (f"{il['ad']} kaydedildi. {kaynak} kaynağından {ileri} günlük "
                        f"tahmin alındı.")


def islem_hava_guncelle(baglanti, veri):
    if not hava.sehir_secili_mi(baglanti):
        return "/ayarlar", "Önce il seç."
    ileri, geri, kaynak = hava.guncelle(baglanti)
    if not ileri and not geri:
        return "/tahmin", "Hava verisi alınamadı; internet bağlantısını kontrol et."
    mesaj = f"{kaynak} kaynağından {ileri} günlük tahmin alındı."
    if geri:
        mesaj += f" Geçmişteki {geri} günün gerçekleşen havası tamamlandı."
    return "/tahmin", mesaj


def islem_satis(baglanti, veri):
    """Gun sonu sayimi: kalan miktarlardan satislari hesaplar."""
    tarih = veri.get("tarih", [hesap.bugun()])[0]

    kalanlar = {}
    for anahtar, degerler in veri.items():
        for onek in ("adet_", "koli_"):
            kalem_id = alan_kimligi(anahtar, onek)
            if kalem_id is None:
                continue
            koli, adet = kalanlar.get(kalem_id, (0.0, 0.0))
            if onek == "koli_":
                koli = sayi(degerler[0])
            else:
                adet = sayi(degerler[0])
            kalanlar[kalem_id] = (koli, adet)

    elle = {}
    bitenler = []
    for anahtar, degerler in veri.items():
        kalem_id = alan_kimligi(anahtar, "elle_")
        if kalem_id is not None:
            elle[kalem_id] = sayi(degerler[0])
        kalem_id = alan_kimligi(anahtar, "bitti_")
        if kalem_id is not None:
            bitenler.append(kalem_id)

    if not kalanlar and not elle and not bitenler:
        return "/satis", "Hiçbir alan doldurulmamış."

    hesap.sayim_kaydet(baglanti, tarih, kalanlar, elle, bitenler)
    ozet = hesap.gun_ozeti(baglanti, tarih)
    return f"/satis?tarih={urllib.parse.quote(tarih)}", (
        f"Sayım kaydedildi. Ciro {para(ozet['ciro'])}, brüt kâr {para(ozet['brut_kar'])}.")


def islem_sayim_sil(baglanti, veri):
    tarih = veri.get("tarih", [hesap.bugun()])[0]
    hesap.sayim_sil(baglanti, tarih)
    return f"/satis?tarih={urllib.parse.quote(tarih)}", "Sayım silindi, satışlar geri alındı."


def islem_satis_giris(baglanti, veri):
    tarih = veri.get("tarih", [hesap.bugun()])[0]
    girilen = 0
    for anahtar, degerler in veri.items():
        kalem_id = alan_kimligi(anahtar, "miktar_")
        miktar = sayi(degerler[0])
        if kalem_id is not None and miktar > 0 and hesap.satis_ekle(
                baglanti, tarih, kalem_id, miktar):
            girilen += 1
    adres = _dogrudan_adres(tarih)
    if not girilen:
        return adres, "Hiçbir miktar yazılmamış."
    ozet = hesap.gun_ozeti(baglanti, tarih)
    return adres, f"{girilen} satış kaydedildi. Günün cirosu {para(ozet['ciro'])}."


def islem_uretim(baglanti, veri):
    tarih = veri.get("tarih", [hesap.bugun()])[0]
    recete_id = int(sayi(veri.get("recete_id", ["0"])[0]))
    adet = sayi(veri.get("adet", ["0"])[0])
    adres = f"/uretim?tarih={urllib.parse.quote(tarih)}"

    # Once stok kontrolu: malzeme yetmiyorsa hicbir sey kaydedilmez, neyin
    # ne kadar eksik oldugu tek tek yazilir.
    eksikler = hesap.recete_eksikleri(baglanti, recete_id, adet)
    if eksikler:
        detay = ", ".join(
            f"{e['ad']} ({mik(e['eksik'])} {e['birim']} eksik, elde {mik(e['elde'])})"
            for e in eksikler
        )
        return adres, f"!Üretim yapılmadı, malzeme yetmiyor: {detay}"

    if hesap.uretim_ekle(baglanti, tarih, recete_id, adet):
        return adres, "Üretim kaydedildi, malzemeler stoktan düşüldü."
    return adres, "!Üretim kaydedilemedi; parti sayısını kontrol et."


def islem_alim(baglanti, veri):
    kalem_id = int(sayi(veri.get("kalem_id", ["0"])[0]))
    kalem = hesap.kalem(baglanti, kalem_id)
    if kalem is None:
        return "/para", "Kalem seçilmemiş."
    miktar = sayi(veri.get("koli", ["0"])[0]) * kalem["koli_adet"] + sayi(veri.get("miktar", ["0"])[0])
    if miktar <= 0:
        return "/para", "Miktar yazılmamış."

    hesap.alim_ekle(
        baglanti, veri.get("tarih", [hesap.bugun()])[0], kalem_id, miktar,
        sayi(veri.get("tutar", ["0"])[0]), veri.get("odeme", ["veresiye"])[0],
    )
    return "/para", f"Alım kaydedildi ({mik(miktar)} {kalem['birim']} stoğa girdi)."


def islem_gider(baglanti, veri):
    hesap.gider_ekle(baglanti, veri.get("tarih", [hesap.bugun()])[0],
                     veri.get("aciklama", [""])[0], sayi(veri.get("tutar", ["0"])[0]))
    return "/para", "Gider kaydedildi."


def islem_calisan_ekle(baglanti, veri):
    ad = veri.get("ad", [""])[0].strip()
    if not ad:
        return "/calisanlar", "!Çalışanın adı yazılmamış."
    hesap.calisan_ekle(
        baglanti, ad,
        gorev=veri.get("gorev", [""])[0],
        telefon=veri.get("telefon", [""])[0],
        maas=sayi(veri.get("maas", ["0"])[0]),
        sgk=sayi(veri.get("sgk", ["0"])[0]),
        baslangic=veri.get("baslangic", [""])[0],
        notlar=veri.get("notlar", [""])[0],
    )
    return "/calisanlar", f"{ad} listeye eklendi."


def islem_calisan_kaydet(baglanti, veri):
    calisan_id = int(sayi(veri.get("id", ["0"])[0]))
    ad = veri.get("ad", [""])[0].strip()
    if not calisan_id or not ad:
        return "/calisanlar", "!Kayıt bulunamadı."
    hesap.calisan_kaydet(
        baglanti, calisan_id, ad=ad,
        gorev=veri.get("gorev", [""])[0].strip(),
        telefon=veri.get("telefon", [""])[0].strip(),
        maas=sayi(veri.get("maas", ["0"])[0]),
        sgk=sayi(veri.get("sgk", ["0"])[0]),
        baslangic=veri.get("baslangic", [""])[0].strip(),
        ayrilis=veri.get("ayrilis", [""])[0].strip(),
        notlar=veri.get("notlar", [""])[0].strip(),
    )
    return "/calisanlar", f"{ad} güncellendi."


def islem_maas_yaz(baglanti, veri):
    tarih = veri.get("tarih", [hesap.bugun()])[0]
    adet, toplam = hesap.maas_yaz(baglanti, tarih)
    if not adet:
        return "/calisanlar", "!Maaş yazılmadı: bu ay zaten yazılmış ya da maaşı olan çalışan yok."
    return "/calisanlar", f"{adet} kişinin maaşı gidere yazıldı ({para(toplam)})."


def islem_odeme(baglanti, veri):
    hesap.odeme_ekle(baglanti, veri.get("tarih", [hesap.bugun()])[0],
                     veri.get("tedarikci", [""])[0], sayi(veri.get("tutar", ["0"])[0]))
    return "/para", "Ödeme kaydedildi."


def islem_stok_duzelt(baglanti, veri):
    if not veri.get("miktar", [""])[0].strip():
        return "/stok", "Miktar yazılmamış."
    fark = hesap.sayim_duzelt(
        baglanti, hesap.bugun(), int(sayi(veri.get("kalem_id", ["0"])[0])),
        sayi(veri["miktar"][0]),
    )
    return "/stok", f"Stok düzeltildi ({mik(fark)} fark kaydedildi)."


def islem_kalem_ekle(baglanti, veri):
    ad = veri.get("ad", [""])[0].strip()
    if not ad:
        return "/kalemler", "Kalemin adını yaz."
    if baglanti.execute("SELECT 1 FROM kalemler WHERE ad = ?", (ad,)).fetchone():
        return "/kalemler", f"{ad} zaten kayıtlı."
    kalem_id = baglanti.execute(
        "INSERT INTO kalemler (ad, birim, tur, alinir, uretilir, satilir)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (ad, veri.get("birim", ["adet"])[0].strip() or "adet",
         veri.get("tur", [""])[0].strip(),
         1 if "alinir" in veri else 0, 1 if "uretilir" in veri else 0,
         1 if "satilir" in veri else 0),
    ).lastrowid
    baglanti.commit()
    return f"/kalem?id={kalem_id}", f"{ad} eklendi. Şimdi ayrıntılarını doldur."


def islem_kalem_kaydet(baglanti, veri):
    kalem_id = int(sayi(veri.get("id", ["0"])[0]))
    ad = veri.get("ad", [""])[0].strip()
    if not ad:
        return f"/kalem?id={kalem_id}", "Kalemin adını yaz."
    cakisma = baglanti.execute(
        "SELECT 1 FROM kalemler WHERE ad = ? AND id <> ?", (ad, kalem_id)
    ).fetchone()
    if cakisma:
        return f"/kalem?id={kalem_id}", f"{ad} adında başka bir kalem var."

    baglanti.execute(
        "UPDATE kalemler SET ad = ?, birim = ?, aciklama = ?, tur = ?, alinir = ?,"
        " uretilir = ?, satilir = ?, takip = ?, birim_fiyat = ?, fiyat = ?, koli_adet = ?,"
        " koli_ad = ?, kritik_seviye = ?, tedarikci = ?, sayim_tarzi = ?, dagit = ?,"
        " sira = ?, aktif = ? WHERE id = ?",
        (ad,
         veri.get("birim", ["adet"])[0].strip() or "adet",
         veri.get("aciklama", [""])[0].strip(),
         veri.get("tur", [""])[0].strip(),
         1 if "alinir" in veri else 0,
         1 if "uretilir" in veri else 0,
         1 if "satilir" in veri else 0,
         1 if "takip" in veri else 0,
         sayi(veri.get("birim_fiyat", ["0"])[0]),
         sayi(veri.get("fiyat", ["0"])[0]),
         sayi(veri.get("koli_adet", ["0"])[0]),
         veri.get("koli_ad", ["koli"])[0].strip() or "koli",
         sayi(veri.get("kritik_seviye", ["0"])[0]),
         veri.get("tedarikci", [""])[0].strip(),
         veri.get("sayim_tarzi", ["yok"])[0],
         1 if "dagit" in veri else 0,
         int(sayi(veri.get("sira", ["0"])[0])),
         1 if "aktif" in veri else 0,
         kalem_id),
    )
    mesaj = "Kaydedildi."
    if "aktif" not in veri:
        if baglanti.execute("SELECT 1 FROM menu_kalemleri WHERE kalem_id = ?",
                            (kalem_id,)).fetchone():
            mesaj = "Kaydedildi. Kullanım dışı olduğu için menülerden de çıkarıldı."
        menuler.kalemden_cikar(baglanti, kalem_id)
    else:
        baglanti.execute("UPDATE kalemler SET mevsim_disi = 0 WHERE id = ?", (kalem_id,))
    baglanti.commit()
    return f"/kalem?id={kalem_id}", mesaj


def islem_kalem_sil(baglanti, veri):
    """Gecmisi olan kalem silinmez; silinirse eski kayitlar anlamsizlasir.
    Boyle bir kalem sadece pasife alinir, listelerde gorunmez."""
    kalem_id = int(sayi(veri.get("id", ["0"])[0]))
    menuler.kalemden_cikar(baglanti, kalem_id)
    kullanimda = any(
        baglanti.execute(f"SELECT 1 FROM {tablo} WHERE kalem_id = ? LIMIT 1",
                         (kalem_id,)).fetchone()
        for tablo in ("stok_hareketleri", "satislar", "alimlar", "uretimler",
                      "recete_satirlari")
    )
    if kullanimda:
        baglanti.execute("UPDATE kalemler SET aktif = 0 WHERE id = ?", (kalem_id,))
        baglanti.commit()
        return "/kalemler", ("Bu kalemin geçmiş kayıtları var, tamamen silinmedi; "
                             "kullanım dışı yapıldı ve listelerden kalktı.")
    baglanti.execute("DELETE FROM receteler WHERE urun_id = ?", (kalem_id,))
    baglanti.execute("DELETE FROM kalemler WHERE id = ?", (kalem_id,))
    baglanti.commit()
    return "/kalemler", "Kalem silindi."


def islem_recete_ekle(baglanti, veri):
    urun_id = int(sayi(veri.get("urun_id", ["0"])[0]))
    sira = baglanti.execute(
        "SELECT COALESCE(MAX(sira), -1) + 1 FROM receteler WHERE urun_id = ?", (urun_id,)
    ).fetchone()[0]
    baglanti.execute(
        "INSERT INTO receteler (urun_id, ad, verim, sira) VALUES (?, '', 1, ?)",
        (urun_id, sira),
    )
    baglanti.commit()
    return f"/kalem?id={urun_id}", "Boş reçete eklendi, malzemelerini yaz."


def _recete_urunu(baglanti, recete_id):
    satir = baglanti.execute(
        "SELECT urun_id FROM receteler WHERE id = ?", (recete_id,)
    ).fetchone()
    return satir["urun_id"] if satir else 0


def islem_recete_kaydet(baglanti, veri):
    recete_id = int(sayi(veri.get("recete_id", ["0"])[0]))
    urun_id = _recete_urunu(baglanti, recete_id)
    baglanti.execute(
        "UPDATE receteler SET ad = ?, verim = ?, parti_ad = ? WHERE id = ?",
        (veri.get("ad", [""])[0].strip(),
         sayi(veri.get("verim", ["1"])[0], 1) or 1,
         veri.get("parti_ad", ["parti"])[0].strip() or "parti",
         recete_id),
    )
    for anahtar, degerler in veri.items():
        satir_id = alan_kimligi(anahtar, "satir_")
        if satir_id is not None:
            baglanti.execute(
                "UPDATE recete_satirlari SET miktar = ? WHERE id = ? AND recete_id = ?",
                (sayi(degerler[0]), satir_id, recete_id),
            )
    baglanti.commit()
    return f"/kalem?id={urun_id}", "Reçete kaydedildi."


def islem_recete_sil(baglanti, veri):
    recete_id = int(sayi(veri.get("recete_id", ["0"])[0]))
    urun_id = _recete_urunu(baglanti, recete_id)
    baglanti.execute("DELETE FROM recete_satirlari WHERE recete_id = ?", (recete_id,))
    baglanti.execute("UPDATE uretimler SET recete_id = NULL WHERE recete_id = ?", (recete_id,))
    baglanti.execute("DELETE FROM receteler WHERE id = ?", (recete_id,))
    baglanti.commit()
    return f"/kalem?id={urun_id}", "Reçete silindi."


def islem_recete_satir_ekle(baglanti, veri):
    recete_id = int(sayi(veri.get("recete_id", ["0"])[0]))
    urun_id = _recete_urunu(baglanti, recete_id)
    kalem_id = int(sayi(veri.get("kalem_id", ["0"])[0]))
    miktar = sayi(veri.get("miktar", ["0"])[0])
    if miktar <= 0:
        return f"/kalem?id={urun_id}", "Miktar yazılmamış."
    baglanti.execute(
        "INSERT INTO recete_satirlari (recete_id, kalem_id, miktar) VALUES (?, ?, ?)"
        " ON CONFLICT(recete_id, kalem_id) DO UPDATE SET miktar = excluded.miktar",
        (recete_id, kalem_id, miktar),
    )
    baglanti.commit()
    return f"/kalem?id={urun_id}", "Malzeme eklendi."


def islem_recete_satir_sil(baglanti, veri):
    recete_id = int(sayi(veri.get("recete_id", ["0"])[0]))
    urun_id = _recete_urunu(baglanti, recete_id)
    baglanti.execute(
        "DELETE FROM recete_satirlari WHERE id = ?",
        (int(sayi(veri.get("satir_id", ["0"])[0])),),
    )
    baglanti.commit()
    return f"/kalem?id={urun_id}", "Malzeme çıkarıldı."


def islem_sil(baglanti, veri):
    tur = veri.get("tur", [""])[0]
    kayit_id = int(sayi(veri.get("id", ["0"])[0]))
    donus = veri.get("donus", ["/"])[0]
    if hesap.kayit_sil(baglanti, tur, kayit_id):
        return donus, "Kayıt silindi, stok ve kasa geri alındı."
    return donus, "Kayıt silinemedi."


def islem_ozel_gun_ekle(baglanti, veri):
    ad = veri.get("ad", [""])[0].strip()
    etiket = veri.get("etiket", [""])[0].strip()
    baslangic = veri.get("baslangic", [""])[0].strip()
    bitis = veri.get("bitis", [""])[0].strip() or baslangic

    if not ad or not baslangic:
        return "/ozel-gunler", "Ad ve başlangıç tarihi gerekli."
    try:
        ilk = datetime.date.fromisoformat(baslangic)
        son = datetime.date.fromisoformat(bitis)
    except ValueError:
        return "/ozel-gunler", "Tarih anlaşılamadı."
    if son < ilk:
        return "/ozel-gunler", "Bitiş tarihi başlangıçtan önce olamaz."

    # Etiket bos birakildiysa ad etiket olur; o zaman kayit tek basina bir
    # havuz olur ve ancak kendi gunlerinden ogrenilir.
    takvim.ekle(baglanti, ad, etiket or ad, baslangic, bitis, "elle")
    baglanti.commit()
    return "/ozel-gunler", f"{ad} takvime eklendi."


def islem_ozel_gun_durum(baglanti, veri):
    takvim.durum_degistir(baglanti, int(sayi(veri.get("id", ["0"])[0])))
    return "/ozel-gunler", "Değiştirildi."


def islem_ozel_gun_sil(baglanti, veri):
    if takvim.sil(baglanti, int(sayi(veri.get("id", ["0"])[0]))):
        return "/ozel-gunler", "Silindi."
    return "/ozel-gunler", "Bu kaydı program üretiyor; silinmez, kapatılabilir."


def islem_ayarlar(baglanti, veri):
    for anahtar in ("dukkan_adi", "para_birimi", "satis_girisi", "uyari_gun",
                    "dolum_gun", "ortalama_gun"):
        if anahtar in veri:
            ayar_yaz(baglanti, anahtar, veri[anahtar][0])

    # Isaretlenmemis kutucuk forma hic gelmez; hangi formun geldigini bilmek sart.
    if "tahmin_formu" in veri:
        ayar_yaz(baglanti, "tahmin_acik", "1" if "tahmin_acik" in veri else "0")

    kolonlar = {"bfiyat_": "birim_fiyat", "sfiyat_": "fiyat", "kritik_": "kritik_seviye"}
    for anahtar, degerler in veri.items():
        for onek, kolon in kolonlar.items():
            kalem_id = alan_kimligi(anahtar, onek)
            if kalem_id is not None:
                baglanti.execute(f"UPDATE kalemler SET {kolon} = ? WHERE id = ?",
                                 (sayi(degerler[0]), kalem_id))
    baglanti.commit()
    return "/ayarlar", "Kaydedildi."


SAYFALAR = {
    "/": ("Ana Menü", sayfa_bugun),
    "/satis": ("Satış", sayfa_satis_merkezi),
    "/satis-giris": ("Satış", sayfa_satis_dogrudan),
    "/uretim": ("Üretim", sayfa_uretim),
    "/stok": ("Stok", sayfa_stok),
    "/para": ("Alım / Gider", sayfa_para),
    "/calisanlar": ("Çalışanlar", sayfa_calisanlar),
    "/ozet": ("Raporlar", sayfa_ozet),
    "/kalemler": ("Ürün & Malzeme", sayfa_kalemler),
    "/menuler": ("Menüler", sayfa_menuler),
    "/kalem": ("Kalem", sayfa_kalem),
    "/tahmin": ("Tahmin", sayfa_tahmin),
    "/ozel-gunler": ("Özel Günler", sayfa_ozel_gunler),
    "/ayarlar": ("Ayarlar", sayfa_ayarlar),
    "/kurulum": ("Kurulum", sayfa_kurulum),
}

ISLEMLER = {
    "/kurulum": islem_kurulum,
    "/sehir-kaydet": islem_sehir_kaydet,
    "/hava-guncelle": islem_hava_guncelle,
    "/satis": islem_satis,
    "/sayim-sil": islem_sayim_sil,
    "/satis-giris": islem_satis_giris,
    "/uretim": islem_uretim,
    "/alim": islem_alim,
    "/gider": islem_gider,
    "/calisan-ekle": islem_calisan_ekle,
    "/calisan-kaydet": islem_calisan_kaydet,
    "/maas-yaz": islem_maas_yaz,
    "/odeme": islem_odeme,
    "/stok-duzelt": islem_stok_duzelt,
    "/kalem-ekle": islem_kalem_ekle,
    "/menu-ekle": islem_menu_ekle,
    "/menu-kaydet": islem_menu_kaydet,
    "/menu-gec": islem_menu_gec,
    "/menu-ertele": islem_menu_ertele,
    "/menu-sil": islem_menu_sil,
    "/kalem-kaydet": islem_kalem_kaydet,
    "/kalem-sil": islem_kalem_sil,
    "/recete-ekle": islem_recete_ekle,
    "/recete-kaydet": islem_recete_kaydet,
    "/recete-sil": islem_recete_sil,
    "/recete-satir-ekle": islem_recete_satir_ekle,
    "/recete-satir-sil": islem_recete_satir_sil,
    "/sil": islem_sil,
    "/ozel-gun-ekle": islem_ozel_gun_ekle,
    "/ozel-gun-durum": islem_ozel_gun_durum,
    "/ozel-gun-sil": islem_ozel_gun_sil,
    "/ayarlar": islem_ayarlar,
}


# ---------------------------------------------------------------- sunucu

class Sunucu(BaseHTTPRequestHandler):
    server_version = "DukkanTakip"

    def log_message(self, bicim, *argumanlar):
        pass  # konsolu her istekte kirletmesin

    def _gonder(self, govde, kod=200):
        veri = govde.encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(veri)))
        self.end_headers()
        self.wfile.write(veri)

    def _hata_sayfasi(self, hata):
        """Beklenmedik bir hatada bos ekran yerine ne olacagini yazan bir sayfa.

        Ayrintili dokum konsol penceresine dusuyor; kullaniciya ne yapacagi
        soylenir, program da ayakta kalir."""
        traceback.print_exc()
        self._gonder(
            f"<!DOCTYPE html><html lang='tr'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>Bir aksilik oldu</title><style>{STIL}</style></head><body>"
            f"<header><h1>Bir aksilik oldu</h1></header><main><div class='kart'>"
            f"<h2>Bu işlem tamamlanamadı</h2>"
            f"<p class='bos'>Kayıtların olduğu gibi duruyor, bir şey bozulmadı. "
            f"Geri dönüp tekrar dene; yine olmazsa siyah pencerede yazan hatayı "
            f"not et.</p><p><code>{kacir(hata)}</code></p>"
            f"<p style='margin-top:16px'><a href='/'>Ana sayfaya dön</a></p>"
            f"</div></main></body></html>", 500)

    def _yonlendir(self, adres, mesaj="", cerez=None):
        if mesaj:
            ayrac = "&" if "?" in adres else "?"
            adres = f"{adres}{ayrac}m={urllib.parse.quote(mesaj)}"
        self.send_response(303)
        self.send_header("Location", adres)
        if cerez:
            self.send_header("Set-Cookie", cerez)
        self.end_headers()

    def _https_mi(self):
        """Sunucu bir vekilin arkasindaysa https'i ancak bu basliktan anlar."""
        return self.headers.get("X-Forwarded-Proto", "").lower() == "https"

    def _oturum(self, defter):
        """Istegi yapan kisiyi ve hangi dukkanin dosyasinin acilacagini bulur.

        (kisi, dukkan_id) doner. dukkan_id 0 ise giris gerekiyor demektir.

        Defterde hic hesap yoksa program dukkan icindeki gibi dogrudan acilir
        ve dukkan 1 kullanilir. Ama bu ASLA sunucuda yapilmaz: orada adresi
        bilen herkes girerdi. Sunucuda defter bossa once dukkan acilir.
        """
        if not SUNUCUDA and not hesaplar.kullanici_var_mi(defter):
            return None, 1
        kullanici_id = guvenlik.oturum_kullanicisi(defter, self.headers.get("Cookie"))
        if not kullanici_id:
            return None, 0
        kisi = hesaplar.kullanici(defter, kullanici_id)
        return kisi, kisi["dukkan_id"]

    def _giris_ekrani(self, defter):
        """Girmemis birine gosterilecek ekran.

        Defter bombosken giris ekrani anlamsizdir - girilecek hesap yok.
        Onun yerine dogrudan dukkan acma ekrani gosterilir.
        """
        if not hesaplar.kullanici_var_mi(defter):
            self._gonder(kayit_sayfasi())
        else:
            self._gonder(giris_sayfasi(), 401)

    def _oturum_ac(self, defter, kullanici_id, adres="/"):
        """Cerezi yazip ic sayfaya yollar."""
        self._yonlendir(adres, "", guvenlik.cerez_yaz(
            guvenlik.cerez_uret(defter, kullanici_id), self._https_mi()))

    def _kayit_islemi(self, defter, veri):
        """Yeni dukkan acar: deftere kaydi, sonra kendi veri dosyasini."""
        def d(ad):
            return veri.get(ad, [""])[0]

        hata = hesaplar.kayit_denetle(defter, d("eposta"), d("sifre"),
                                      d("sifre2"), d("dukkan_adi"))
        if hata:
            self._gonder(kayit_sayfasi(hata, veri), 400)
            return

        kullanici_id, dukkan_id = hesaplar.kayit_ol(
            defter, d("dukkan_adi"), d("eposta"), d("ad"), d("sifre"))
        # Yeni dukkanin kendi veri dosyasi burada, bos olarak kurulur.
        yeni = veritabani.hazirla(dukkan_id)
        try:
            ayar_yaz(yeni, "dukkan_adi", d("dukkan_adi").strip())
            yeni.commit()
        finally:
            yeni.close()
        self._oturum_ac(defter, kullanici_id)

    def _hesap_kur(self, defter, dukkan_id, veri):
        """Girisi olmayan bir kuruluma ilk hesabi ekler.

        Dukkanin su anki butun kayitlari oldugu gibi kalir; sadece onune
        giris ekrani gelir. Ayarlar sayfasindan cagrilir.
        """
        def d(ad):
            return veri.get(ad, [""])[0]

        hata = hesaplar.kayit_denetle(defter, d("eposta"), d("sifre"), d("sifre2"))
        if hata:
            self._yonlendir("/ayarlar", "!" + hata)
            return

        baglanti = veritabani.baglan(dukkan_id)
        try:
            ad = ayar(baglanti, "dukkan_adi", "Dükkanım")
        finally:
            baglanti.close()
        hesaplar.dukkan_saglama(defter, dukkan_id, ad)
        kullanici_id = hesaplar.kullanici_ekle(
            defter, dukkan_id, d("eposta"), d("ad"), d("sifre"))
        self._oturum_ac(defter, kullanici_id, "/ayarlar")

    def _sifre_islemi(self, defter, kisi, veri):
        """Girmis kisinin kendi sifresini degistirmesi."""
        if not kisi:
            self._yonlendir("/ayarlar", "!Şifre değiştirmek için önce giriş yapmalısın.")
            return
        sorun = hesaplar.sifre_degistir(defter, kisi["id"], veri.get("sifre", [""])[0])
        self._yonlendir("/ayarlar", ("!" + sorun) if sorun else "Şifre değiştirildi.")

    def do_GET(self):
        parca = urllib.parse.urlparse(self.path)
        if parca.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        defter = hesaplar.baglan()
        try:
            kisi, dukkan_id = self._oturum(defter)
            # Giris ve kayit ekranlari hicbir dukkanin verisine bakmadan
            # cizilir - kimin geldigi henuz bilinmiyor.
            if not dukkan_id:
                if parca.path == "/kayit":
                    self._gonder(kayit_sayfasi())
                else:
                    self._giris_ekrani(defter)
                return
            if parca.path in ("/giris", "/kayit"):
                self._yonlendir("/")
                return
        except Exception as hata:
            self._hata_sayfasi(hata)
            return
        finally:
            defter.close()

        _istek.kullanici = kisi
        baglanti = veritabani.baglan(dukkan_id)
        try:
            _istek.para = ayar(baglanti, "para_birimi", "TL")

            sayfa_bilgi = SAYFALAR.get(parca.path)
            if not sayfa_bilgi:
                self._gonder("<h1>Sayfa bulunamadı</h1><a href='/'>Ana sayfa</a>", 404)
                return

            sorgu = urllib.parse.parse_qs(parca.query)
            baslik, uretici = sayfa_bilgi
            # Ilk acilista once dukkan sablonu secilir.
            if veritabani.kurulum_gerekli(baglanti) and parca.path != "/kurulum":
                self._yonlendir("/kurulum")
                return
            icerik = uretici(baglanti, sorgu)
            self._gonder(sayfa(baglanti, parca.path, baslik, icerik,
                               sorgu.get("m", [""])[0]))
        except Exception as hata:
            self._hata_sayfasi(hata)
        finally:
            baglanti.close()

    def do_POST(self):
        parca = urllib.parse.urlparse(self.path)
        # Govde her durumda okunur; okunmadan cevap verilirse tarayici bir
        # sonraki istekte yarim kalmis veriyle karsilasir.
        uzunluk = int(self.headers.get("Content-Length", 0))
        veri = urllib.parse.parse_qs(
            self.rfile.read(uzunluk).decode("utf-8"), keep_blank_values=True
        )

        defter = hesaplar.baglan()
        try:
            kisi, dukkan_id = self._oturum(defter)

            if parca.path == "/cikis":
                self._yonlendir("/giris", "", guvenlik.cerez_sil(self._https_mi()))
                return

            if parca.path == "/giris":
                if dukkan_id:
                    self._yonlendir("/")
                    return
                girdi = hesaplar.dogrula(defter, veri.get("eposta", [""])[0],
                                         veri.get("sifre", [""])[0])
                if girdi:
                    self._oturum_ac(defter, girdi["id"])
                else:
                    # Yanlis sifreyi bir saniye bekletmek, sirayla sifre deneyen
                    # bir programi pratikte kullanissiz hale getirir.
                    time.sleep(1)
                    self._gonder(giris_sayfasi("Kullanıcı adı ya da şifre yanlış.",
                                               veri.get("eposta", [""])[0]), 401)
                return

            if parca.path == "/kayit":
                if dukkan_id:
                    self._yonlendir("/")
                else:
                    self._kayit_islemi(defter, veri)
                return

            if not dukkan_id:
                self._giris_ekrani(defter)
                return

            # Hesap islemleri cerez de yazdigi icin ISLEMLER'den gecmez.
            if parca.path == "/hesap-kur":
                if kisi:
                    self._yonlendir("/ayarlar", "!Zaten giriş yapmışsın.")
                else:
                    self._hesap_kur(defter, dukkan_id, veri)
                return
            if parca.path == "/sifre-kur":
                self._sifre_islemi(defter, kisi, veri)
                return
        except Exception as hata:
            self._hata_sayfasi(hata)
            return
        finally:
            defter.close()

        _istek.kullanici = kisi
        baglanti = veritabani.baglan(dukkan_id)
        try:
            _istek.para = ayar(baglanti, "para_birimi", "TL")

            islem = ISLEMLER.get(parca.path)
            if not islem:
                self._gonder("<h1>Bulunamadı</h1>", 404)
                return
            adres, mesaj = islem(baglanti, veri)
        except Exception as hata:
            baglanti.rollback()
            self._hata_sayfasi(hata)
            return
        finally:
            baglanti.close()
        self._yonlendir(adres, mesaj)


def _dukkan_kimlikleri():
    """Havasi tazelenecek dukkanlarin listesi.

    Defterde kayitli dukkanlar; defter bossa dukkan icindeki kurulumdur ve
    tek dukkan vardir.
    """
    defter = hesaplar.baglan()
    try:
        return hesaplar.dukkan_kimlikleri(defter) or [1]
    finally:
        defter.close()


def hava_bekcisi():
    """Havayi arka planda tazeler; ekran ciziminde asla ag beklenmez.

    Acilista bir kere, sonra uc saatte bir dener. Internet yoksa sessizce
    bekler - program cevrimdisi calismaya devam eder.

    Her dukkanin sehri ayri oldugu icin liste her turda bastan okunur; arada
    acilan yeni bir dukkan da boylece kendiliginden sıraya girer.
    """
    while True:
        for dukkan_id in _dukkan_kimlikleri():
            if not os.path.exists(veritabani.db_yolu(dukkan_id)):
                continue
            baglanti = veritabani.baglan(dukkan_id)
            try:
                if hava.sehir_secili_mi(baglanti):
                    hava.guncelle(baglanti)
            except Exception:
                traceback.print_exc()
            finally:
                baglanti.close()
        time.sleep(3 * 60 * 60)


def yerel_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as soket:
            soket.connect(("8.8.8.8", 80))
            return soket.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def calistir():
    # Once dukkan/kullanici defteri, sonra dukkan 1'in verisi. Sunucuda
    # defter bos kalabilir - orada ilk giren kendi dukkanini acar.
    defter = hesaplar.hazirla()
    try:
        dolu = hesaplar.kullanici_var_mi(defter)
    finally:
        defter.close()

    baslik = "Dükkan Takip"
    if not (SUNUCUDA and dolu):
        baglanti = veritabani.hazirla(1)
        baslik = ayar(baglanti, "dukkan_adi", "Dükkanım")
        baglanti.close()

    # Her dukkanin dosyasi yeni surumun tablolarina kavussun. Istekler dosyayi
    # sadece acar (baglan); yeni bir tablo ya da kolon eklendiginde, acilista
    # guncellenmeyen bir dukkanin ekrani o tabloyu bulamayip coker.
    for dukkan_id in _dukkan_kimlikleri():
        if os.path.exists(veritabani.db_yolu(dukkan_id)):
            veritabani.hazirla(dukkan_id).close()

    threading.Thread(target=hava_bekcisi, daemon=True).start()

    sunucu = ThreadingHTTPServer(("0.0.0.0", PORT), Sunucu)
    print("=" * 56)
    print(f"  {baslik.upper()} - TAKIP PROGRAMI")
    print("=" * 56)
    if SUNUCUDA:
        print(f"  Sunucu kipinde, {PORT} portu dinleniyor.")
        print(f"  Veri klasoru: {veritabani.DUKKAN_KLASORU}")
        print("=" * 56)
    else:
        print(f"  Bu bilgisayardan : http://localhost:{PORT}")
        print(f"  Telefondan       : http://{yerel_ip()}:{PORT}")
        print()
        print("  Kapatmak icin bu pencerede Ctrl+C tuslarina bas.")
        print("=" * 56)
        try:
            webbrowser.open(f"http://localhost:{PORT}")
        except Exception:
            pass
    try:
        sunucu.serve_forever()
    except KeyboardInterrupt:
        print("\nProgram kapatildi.")
        sunucu.shutdown()


if __name__ == "__main__":
    calistir()
