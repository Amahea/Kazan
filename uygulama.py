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

import guvenlik
import hava
import hesap
import tahmin as tahmin_modulu
import takvim
import veritabani
from veritabani import ayar, ayar_yaz, sayi

# Bulut servisleri dinlenecek portu PORT degiskeniyle bildirir. Bu degiskenin
# varligi ayni zamanda "bir sunucuda calisiyoruz" demektir: orada tarayici
# acmanin ya da yerel ag adresi yazdirmanin anlami yok.
PORT = int(os.environ.get("PORT") or 8000)
SUNUCUDA = "PORT" in os.environ
PARA = "TL"   # her istekte ayarlardan tazelenir


# ---------------------------------------------------------------- bicimlendirme

def tl(deger):
    """1234.5 -> '1.234,50'"""
    metin = f"{abs(deger):,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")
    return ("-" if deger < 0 else "") + metin


def para(deger):
    return f"{tl(deger)} {PARA}"


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
.hava-simge { margin-right:6px; }
.yesil { color:#1b7f4f; } .kirmizi { color:#c1392b; } .mavi { color:#0f4c75; } .gri { color:#6b7c8f; }
table { width:100%; border-collapse:collapse; font-size:15px; }
th, td { text-align:left; padding:9px 6px; border-bottom:1px solid #e6ebf0; }
th { font-size:13px; color:#6b7c8f; font-weight:600; }
td.sag, th.sag { text-align:right; }
input, select, button { font-size:16px; font-family:inherit; }
input[type=text], input[type=number], input[type=date], select {
    width:100%; padding:10px; border:1px solid #cfd8e0; border-radius:7px; background:#fff; }
label { display:block; font-size:13px; color:#6b7c8f; margin:0 0 4px; }
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
    ("/para", "Alım / Gider", "💰", ()),
    ("/ozet", "Raporlar", "📊", ("/tahmin", "/ozel-gunler")),
    ("/ayarlar", "Ayarlar", "⚙️", ("/kalemler", "/kalem")),
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
    # Cikis ancak girilecek bir sifre varsa anlamli.
    if guvenlik.sifre_var_mi(baglanti):
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
<main>{mesaj_html}{govde}</main></body></html>"""


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
    """Ana menunun solundaki tahmin sutunu: hava, yedi gunluk ciro tahmini
    ve kisa uretim onerisi. Tahmin kapaliysa sutun hic cizilmez."""
    if ayar(baglanti, "tahmin_acik", "1") != "1":
        return ""

    if not hava.sehir_secili_mi(baglanti):
        return ('<div class="kart"><h2>Tahmin</h2>'
                '<p class="bos">Hava ve satış tahmini için '
                '<a href="/ayarlar">Ayarlar</a> sayfasından ilini seç.</p></div>')

    sehir = kacir(ayar(baglanti, "sehir", ""))
    model, gunler, uretimler = tahmin_modulu.ileri_tahmin(baglanti, 7)

    if gunler:
        govde = "".join(
            f'<div class="yan-satir"><div><b>{kacir(gun["gun_adi"])}</b>'
            f'<div class="bos" style="font-size:12px">{kacir(gun["hava"])}</div></div>'
            f'<div class="sag"><b>{para(gun["ciro"])}</b>'
            f'<div class="bos" style="font-size:12px">'
            f'{tl(gun["alt"])} – {tl(gun["ust"])}</div></div></div>'
            for gun in gunler
        )
    else:
        # Tahmin henuz calismiyorsa en azindan hava gorunsun.
        govde = _yan_hava_satirlari(baglanti)
        govde += f'<p class="bos" style="margin-top:10px">{kacir(tahmin_modulu.durum_metni(model))}</p>'

    panel = (f'<div class="kart"><h2>{sehir} — tahmin</h2>{govde}'
             f'<p class="bos" style="margin-top:10px">'
             f'<a href="/tahmin">Tahmin sayfasını aç</a></p></div>')

    acik_olanlar = [oneri for oneri in uretimler if oneri["acik"] > 0][:5]
    if acik_olanlar:
        satirlar = "".join(
            f'<div class="yan-satir"><div>{kacir(oneri["kalem"]["ad"])}</div>'
            f'<div class="sag"><b>{mik(oneri["parti"], 1)} '
            f'{kacir(oneri["parti_ad"])}</b></div></div>'
            for oneri in acik_olanlar
        )
        panel += (f'<div class="kart"><h2>Ne üretmeli</h2>{satirlar}'
                  f'<p class="bos" style="margin-top:10px">Tahmine göre eldeki '
                  f'stok bu kadar yetmiyor.</p></div>')

    return panel


def giris_sayfasi(baglanti, hata=""):
    """Sifre ekrani. Menusuz ve tek alanli: giris yapmadan hicbir sey gorunmez."""
    dukkan = kacir(ayar(baglanti, "dukkan_adi", "Dükkanım"))
    uyari = f'<div class="uyari bitti"><b>{kacir(hata)}</b></div>' if hata else ""
    return f"""<!DOCTYPE html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Giriş - {dukkan}</title><style>{STIL}</style></head>
<body><header><h1>{dukkan}</h1></header>
<main><div class="kart" style="max-width:400px;margin:40px auto">
<h2>Giriş</h2>{uyari}
<form method="post" action="/giris">
<label>Şifre</label>
<input type="password" name="sifre" autofocus autocomplete="current-password">
<button style="margin-top:14px">Gir</button></form></div></main></body></html>"""


def kutu(etiket, deger, renk="mavi", alt=""):
    alt_html = f'<div class="etiket" style="margin:4px 0 0">{alt}</div>' if alt else ""
    return (f'<div class="kutu"><div class="etiket">{kacir(etiket)}</div>'
            f'<div class="deger {renk}">{deger}</div>{alt_html}</div>')


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

    liste = hesap.oneriler(baglanti)
    if liste:
        uyarilar = ""
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
            if satir["onerilen"] > 0:
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
<div><label>Ödenecek tutar ({kacir(PARA)})</label>{sayi_alani("tutar", min="0")}</div>
<div><label>Ödeme</label>{secim("odeme", [("veresiye", "Veresiye (borca yazılsın)"),
                                          ("pesin", "Peşin (kasadan çıksın)")])}</div>
</div><button>Alımı kaydet</button></form></div>

<div class="kart"><h2>Gider</h2>
<p class="bos">Kira, elektrik, personel, yakıt gibi malzeme dışı harcamalar.</p>
<form method="post" action="/gider"><div class="satir">
<div>{tarih_alani(tarih)}</div>
<div><label>Açıklama</label><input type="text" name="aciklama" placeholder="Elektrik faturası"></div>
<div><label>Tutar ({kacir(PARA)})</label>{sayi_alani("tutar", min="0")}</div>
</div><button>Gideri kaydet</button></form></div>

<div class="kart"><h2>Tedarikçiye ödeme</h2>
<form method="post" action="/odeme"><div class="satir">
<div>{tarih_alani(tarih)}</div>
<div><label>Tedarikçi</label>{secim("tedarikci", borc_secenek)}</div>
<div><label>Ödenen tutar ({kacir(PARA)})</label>{sayi_alani("tutar", min="0")}</div>
</div><button>Ödemeyi kaydet</button></form></div>

<div class="kart"><h2>Kime ne kadar borçlusun</h2><table>{borc_satirlari}</table></div>

<div class="kart"><h2>Son alımlar</h2><table>
<tr><th>Tarih</th><th>Kalem</th><th class='sag'>Miktar</th><th class='sag'>Tutar</th>
<th>Ödeme</th><th></th></tr>
{alim_satirlari}</table></div>

<div class="kart"><h2>Son giderler</h2><table>
<tr><th>Tarih</th><th>Açıklama</th><th class='sag'>Tutar</th><th></th></tr>
{gider_satirlari}</table></div>"""


# ---------------------------------------------------------------- raporlar

def sayfa_ozet(baglanti, sorgu):
    tarih = sorgu.get("tarih", [hesap.bugun()])[0]
    ozet = hesap.gun_ozeti(baglanti, tarih)

    gunler = baglanti.execute(
        "SELECT tarih, SUM(tutar) AS ciro, SUM(tutar - maliyet) AS brut"
        " FROM satislar GROUP BY tarih ORDER BY tarih DESC LIMIT 30"
    ).fetchall()
    gun_satirlari = "".join(
        f"<tr><td><a href='/ozet?tarih={kacir(g['tarih'])}'>{kacir(g['tarih'])}</a></td>"
        f"<td class='sag'>{para(g['ciro'])}</td>"
        f"<td class='sag'>{para(g['brut'])}</td></tr>" for g in gunler
    ) or "<tr><td class='bos' colspan='3'>Henüz satış kaydı yok.</td></tr>"

    analiz = baglanti.execute(
        "SELECT k.ad, k.birim, SUM(s.miktar) AS miktar, SUM(s.tutar) AS ciro,"
        " SUM(s.tutar - s.maliyet) AS kar FROM satislar s"
        " JOIN kalemler k ON k.id = s.kalem_id GROUP BY k.id ORDER BY kar DESC"
    ).fetchall()
    analiz_satirlari = "".join(
        f"<tr><td>{kacir(a['ad'])}</td>"
        f"<td class='sag'>{mik(a['miktar'])} {kacir(a['birim'])}</td>"
        f"<td class='sag'>{para(a['ciro'])}</td><td class='sag'>{para(a['kar'])}</td>"
        f"<td class='sag'>{para(a['kar'] / a['miktar']) if a['miktar'] else '—'}</td></tr>"
        for a in analiz
    ) or "<tr><td class='bos' colspan='5'>Henüz satış kaydı yok.</td></tr>"

    return f"""
<div class="kart"><h2>Gün seç</h2>
<form method="get" action="/ozet"><div class="satir">
<div>{tarih_alani(tarih)}</div>
<div style="align-self:end"><button class="ikincil">Göster</button></div>
</div></form></div>

<div class="kutular">
{kutu("Ciro", para(ozet["ciro"]), "mavi")}
{kutu("Satılanın maliyeti", para(ozet["satis_maliyeti"]), "gri")}
{kutu("Brüt kâr", para(ozet["brut_kar"]), "yesil")}
{kutu("Giderler", para(ozet["gider"]), "gri")}
{kutu("Net kâr", para(ozet["net_kar"]), "yesil" if ozet["net_kar"] >= 0 else "kirmizi")}
{kutu("Kasa değişimi", para(ozet["kasa_degisimi"]),
      "yesil" if ozet["kasa_degisimi"] >= 0 else "kirmizi",
      "kâr değil, o gün kasaya net giren para")}
</div>

<div class="kart"><h2>{kacir(tarih)} detayı</h2><table>
<tr><td>Peşin alımlar</td><td class='sag'>{para(ozet['alim_pesin'])}</td></tr>
<tr><td>Veresiye alımlar (borca yazıldı)</td><td class='sag'>{para(ozet['alim_veresiye'])}</td></tr>
<tr><td>Tedarikçiye ödenen</td><td class='sag'>{para(ozet['borc_odemesi'])}</td></tr>
<tr><td>Üretime giren malzeme</td><td class='sag'>{para(ozet['uretim_maliyeti'])}</td></tr>
</table></div>

<div class="kart"><h2>Ürünlere göre kârlılık (tüm zamanlar)</h2><table>
<tr><th>Ürün</th><th class='sag'>Satılan</th><th class='sag'>Ciro</th>
<th class='sag'>Kâr</th><th class='sag'>Birim başına kâr</th></tr>
{analiz_satirlari}</table></div>

<div class="kart"><h2>Son günler</h2><table>
<tr><th>Tarih</th><th class='sag'>Ciro</th><th class='sag'>Brüt kâr</th></tr>
{gun_satirlari}</table></div>
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
            durum = (f"<b>{mik(oneri['parti'], 1)} {kacir(oneri['parti_ad'])} üret</b> "
                     f"({mik(oneri['acik'], 1)} {kacir(oneri['kalem']['birim'])} açık)")
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
<div><label>Alış fiyatı (bir {kacir(kalem['birim'])} için, {kacir(PARA)})</label>
     {sayi_alani("birim_fiyat", f"{kalem['birim_fiyat']:.2f}", min="0")}</div>
<div><label>Satış fiyatı (bir {kacir(kalem['birim'])} için, {kacir(PARA)})</label>
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
Kalem listesi, reçeteler ve satış şekilleri</a></p></div>

<div class="kart"><h2>Genel ayarlar</h2>
<form method="post" action="/ayarlar"><div class="satir">
<div><label>Dükkan adı</label><input type="text" name="dukkan_adi"
     value="{kacir(ayar(baglanti, 'dukkan_adi'))}"></div>
<div><label>Para birimi</label><input type="text" name="para_birimi"
     value="{kacir(ayar(baglanti, 'para_birimi', 'TL'))}"></div>
<div><label>Satış nasıl girilsin</label>
     {secim("satis_girisi", modlar, ayar(baglanti, "satis_girisi", "ikisi"))}</div>
</div><div class="satir">
<div><label>Tedarikçi kaç günde bir geliyor</label>
     {sayi_alani("tedarik_gun", kacir(ayar(baglanti, "tedarik_gun")), min="0")}</div>
<div><label>Kaç günlük yedek dursun</label>
     {sayi_alani("emniyet_gun", kacir(ayar(baglanti, "emniyet_gun")), min="0")}</div>
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
    """Ayarlar sayfasindaki giris sifresi bolumu."""
    if guvenlik.ortamdan_mi():
        return """
<div class="kart"><h2>Güvenlik</h2>
<div class="uyari yakin"><b>Şifre sunucudan geliyor</b>
<div class="detay">Bu kopya internete açık bir sunucuda çalışıyor ve şifresi
oraya kurulumda verilmiş. Buradan değiştirilemez; değiştirmek için sunucudaki
ayarı güncellemek gerekir.</div></div></div>"""

    if guvenlik.sifre_var_mi(baglanti):
        return """
<div class="kart"><h2>Güvenlik</h2>
<div class="uyari yakin"><b>Giriş şifresi açık</b>
<div class="detay">Programı açan herkesten önce şifre isteniyor. Şifreyi
değiştirirsen açık kalmış bütün oturumlar kapanır — telefonunda açık
duruyorsa oradan da yeniden giriş istenir.</div></div>
<form method="post" action="/sifre-kur"><div class="satir">
<div><label>Yeni şifre</label>
<input type="password" name="sifre" autocomplete="new-password"></div>
</div><button class="ikincil">Şifreyi değiştir</button></form>
<form method="post" action="/sifre-kaldir" style="margin-top:10px">
<button class="sil">Şifreyi kaldır</button></form>
<p class="bos" style="margin-top:10px">Şifreyi kaldırırsan program yine
doğrudan açılır. Sadece dükkânda, kendi wifi'inde kullanıyorsan sakıncası
yok; internete açıksa kaldırma.</p></div>"""

    return f"""
<div class="kart"><h2>Güvenlik</h2>
<p class="bos">Şu an şifre yok: programı açan herkes doğrudan giriyor.
<b>Dükkân içinde, kendi wifi'inde çalışırken bunun sakıncası yok</b> — dışarıdan
kimse o ağda değil. Ama programı internete açarsan adresi bilen herkes kasayı,
ciroyu ve tedarikçileri görür ve değiştirebilir. O durumda şifre şart.</p>
<form method="post" action="/sifre-kur"><div class="satir">
<div><label>Şifre koy (en az {guvenlik.EN_KISA_SIFRE} karakter)</label>
<input type="password" name="sifre" autocomplete="new-password"></div>
</div><button>Şifreyi kur</button></form></div>"""


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
    baglanti.commit()
    return f"/kalem?id={kalem_id}", "Kaydedildi."


def islem_kalem_sil(baglanti, veri):
    """Gecmisi olan kalem silinmez; silinirse eski kayitlar anlamsizlasir.
    Boyle bir kalem sadece pasife alinir, listelerde gorunmez."""
    kalem_id = int(sayi(veri.get("id", ["0"])[0]))
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
    for anahtar in ("dukkan_adi", "para_birimi", "satis_girisi", "tedarik_gun",
                    "emniyet_gun", "ortalama_gun"):
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
    "/ozet": ("Raporlar", sayfa_ozet),
    "/kalemler": ("Ürün & Malzeme", sayfa_kalemler),
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
    "/odeme": islem_odeme,
    "/stok-duzelt": islem_stok_duzelt,
    "/kalem-ekle": islem_kalem_ekle,
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

    def _girisli_mi(self, baglanti):
        return guvenlik.girisli_mi(baglanti, self.headers.get("Cookie"))

    def _sifre_islemi(self, baglanti, yol, veri):
        """Sifre kurma/kaldirma. Ikisi de acik oturumlarin hepsini kapatir."""
        if guvenlik.ortamdan_mi():
            self._yonlendir("/ayarlar", "Şifre sunucudan geliyor, buradan değişmez.")
            return

        if yol == "/sifre-kaldir":
            guvenlik.sifre_kaldir(baglanti)
            self._yonlendir("/ayarlar", "Şifre kaldırıldı.",
                            guvenlik.cerez_sil(self._https_mi()))
            return

        sorun = guvenlik.sifre_kur(baglanti, veri.get("sifre", [""])[0])
        if sorun:
            self._yonlendir("/ayarlar", sorun)
            return
        # Sifre degisince butun oturumlar kapanir. Degistiren kisinin kendi
        # tarayicisi yeniden giris yapmak zorunda kalmasin diye taze cerez.
        self._yonlendir("/ayarlar", "Şifre kaydedildi.",
                        guvenlik.cerez_yaz(guvenlik.cerez_uret(baglanti),
                                           self._https_mi()))

    def do_GET(self):
        global PARA
        parca = urllib.parse.urlparse(self.path)
        if parca.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        baglanti = veritabani.baglan()
        try:
            PARA = ayar(baglanti, "para_birimi", "TL")

            # Sifre kuruluysa giris yapmadan hicbir sayfa acilmaz. Sifre yoksa
            # girisli_mi zaten dogru doner; dukkan ici kullanim degismez.
            girisli = self._girisli_mi(baglanti)
            if parca.path == "/giris":
                if girisli:
                    self._yonlendir("/")
                else:
                    self._gonder(giris_sayfasi(baglanti))
                return
            if not girisli:
                self._gonder(giris_sayfasi(baglanti), 401)
                return

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
        global PARA
        parca = urllib.parse.urlparse(self.path)
        # Govde her durumda okunur; okunmadan cevap verilirse tarayici bir
        # sonraki istekte yarim kalmis veriyle karsilasir.
        uzunluk = int(self.headers.get("Content-Length", 0))
        veri = urllib.parse.parse_qs(
            self.rfile.read(uzunluk).decode("utf-8"), keep_blank_values=True
        )
        baglanti = veritabani.baglan()
        try:
            PARA = ayar(baglanti, "para_birimi", "TL")

            if parca.path == "/giris":
                if guvenlik.sifre_dogru_mu(baglanti, veri.get("sifre", [""])[0]):
                    self._yonlendir("/", "", guvenlik.cerez_yaz(
                        guvenlik.cerez_uret(baglanti), self._https_mi()))
                else:
                    # Yanlis sifreyi bir saniye bekletmek, sirayla sifre deneyen
                    # bir programi pratikte kullanissiz hale getirir.
                    time.sleep(1)
                    self._gonder(giris_sayfasi(baglanti, "Şifre yanlış."), 401)
                return

            if parca.path == "/cikis":
                self._yonlendir("/giris", "", guvenlik.cerez_sil(self._https_mi()))
                return

            if not self._girisli_mi(baglanti):
                self._gonder(giris_sayfasi(baglanti), 401)
                return

            # Sifre islemleri cerez de yazdigi icin ISLEMLER'den gecmez.
            if parca.path in ("/sifre-kur", "/sifre-kaldir"):
                self._sifre_islemi(baglanti, parca.path, veri)
                return

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


def hava_bekcisi():
    """Havayi arka planda tazeler; ekran ciziminde asla ag beklenmez.

    Acilista bir kere, sonra uc saatte bir dener. Internet yoksa sessizce
    bekler - program cevrimdisi calismaya devam eder.
    """
    while True:
        baglanti = veritabani.baglan()
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
    baglanti = veritabani.hazirla()
    baslik = ayar(baglanti, "dukkan_adi", "Dükkanım")
    baglanti.close()

    threading.Thread(target=hava_bekcisi, daemon=True).start()

    sunucu = ThreadingHTTPServer(("0.0.0.0", PORT), Sunucu)
    print("=" * 56)
    print(f"  {baslik.upper()} - TAKIP PROGRAMI")
    print("=" * 56)
    if SUNUCUDA:
        print(f"  Sunucu kipinde, {PORT} portu dinleniyor.")
        print(f"  Veritabani: {veritabani.DB_YOLU}")
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
