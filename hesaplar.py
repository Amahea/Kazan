# -*- coding: utf-8 -*-
"""Dukkan ve kullanici defteri.

Program artik tek bir dukkana degil, birden fazla dukkana hizmet edebiliyor.
Her dukkanin verisi KENDI DOSYASINDA durur:

    veri/dukkanlar/dukkan-1.db
    veri/dukkanlar/dukkan-2.db

Bu dosyalarin icine kimin girebilecegi ise burada, ayri bir defterde tutulur:

    veri/kullanicilar.db

Ikisini ayirmanin sebebi guvenliktir. Iki dukkanin kaydi ayni dosyada hic
bulunmadigi icin, koddaki bir hata yuzunden bir dukkan sahibinin otekinin
cirosunu gormesi mumkun degildir. Yedek almak da dosya kopyalamak kadar
basit kalir.

Sifreler hicbir zaman acik metin durmaz; pbkdf2 ozeti saklanir.

KAZAN_SIFRE ortam degiskeni verilmisse, defter bos oldugunda kendiliginden
bir yonetici hesabi kurulur. Boylece internete acilan bos bir kopya bile ilk
saniyeden korumalidir; "sifre koymayi unuttum" diye bir acik kalmaz.
"""

import datetime
import hashlib
import hmac
import os
import re
import secrets
import sqlite3

from veritabani import VERI_KLASORU

DB_YOLU = os.path.join(VERI_KLASORU, "kullanicilar.db")

ORTAM_ANAHTARI = "KAZAN_SIFRE"
ORTAM_EPOSTA = "yonetici"
DONGU = 200_000          # pbkdf2 tur sayisi
EN_KISA_SIFRE = 6

SEMA = """
CREATE TABLE IF NOT EXISTS dukkanlar (
    id       INTEGER PRIMARY KEY,
    ad       TEXT NOT NULL,
    kuruldu  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS kullanicilar (
    id          INTEGER PRIMARY KEY,
    dukkan_id   INTEGER NOT NULL REFERENCES dukkanlar(id),
    -- Her zaman kucuk harfe cevrilerek yazilir; "Ali@" ile "ali@" ayni kisidir.
    eposta      TEXT NOT NULL UNIQUE,
    ad          TEXT NOT NULL DEFAULT '',
    sifre_ozet  TEXT NOT NULL,
    -- 'sahip' dukkani kuran kisidir, silinemez. Ilerisi icin ayrildi.
    rol         TEXT NOT NULL DEFAULT 'sahip',
    kuruldu     TEXT NOT NULL DEFAULT '',
    son_giris   TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS ayarlar (
    anahtar TEXT PRIMARY KEY,
    deger   TEXT NOT NULL DEFAULT ''
);
"""


# ---------------------------------------------------------------- baglanti

def baglan():
    baglanti = sqlite3.connect(DB_YOLU)
    baglanti.row_factory = sqlite3.Row
    baglanti.execute("PRAGMA foreign_keys = ON")
    return baglanti


def hazirla():
    """Defteri acar, yoksa kurar. Acilista bir kere cagrilir."""
    os.makedirs(VERI_KLASORU, exist_ok=True)
    baglanti = baglan()
    baglanti.executescript(SEMA)
    baglanti.commit()
    _ortam_yoneticisi(baglanti)
    return baglanti


def _ortam_yoneticisi(baglanti):
    """KAZAN_SIFRE verilmisse ve defter bossa ilk yoneticiyi kurar.

    Sadece defter tamamen bosken calisir: sonradan sifre degistiren bir
    yoneticinin degisikligini her acilista geri almasin diye.
    """
    sifre = (os.environ.get(ORTAM_ANAHTARI) or "").strip()
    if not sifre or kullanici_var_mi(baglanti):
        return
    kayit_ol(baglanti, "Dükkanım", ORTAM_EPOSTA, "Yönetici", sifre)
    print(f"  Yonetici hesabi kuruldu. Kullanici adi: {ORTAM_EPOSTA}")


# ---------------------------------------------------------------- sifre

def _ozet(sifre, tuz):
    return hashlib.pbkdf2_hmac("sha256", sifre.encode("utf-8"),
                               bytes.fromhex(tuz), DONGU).hex()


def sifre_ozetle(sifre):
    tuz = secrets.token_hex(16)
    return f"{tuz}${_ozet(sifre, tuz)}"


def sifre_uyar_mi(kayit, sifre):
    if "$" not in (kayit or ""):
        return False
    tuz, beklenen = kayit.split("$", 1)
    return hmac.compare_digest(_ozet(sifre, tuz), beklenen)


# ---------------------------------------------------------------- kayit

def kullanici_var_mi(baglanti):
    """Defter bos mu. Bos ise program dukkan icindeki gibi sifresiz acilir."""
    return baglanti.execute("SELECT 1 FROM kullanicilar LIMIT 1").fetchone() is not None


def _eposta_duzelt(eposta):
    return (eposta or "").strip().lower()


def kullanici_bul(baglanti, eposta):
    return baglanti.execute(
        "SELECT * FROM kullanicilar WHERE eposta = ?", (_eposta_duzelt(eposta),)
    ).fetchone()


def kullanici(baglanti, kullanici_id):
    return baglanti.execute(
        "SELECT k.*, d.ad AS dukkan_adi FROM kullanicilar k "
        "JOIN dukkanlar d ON d.id = k.dukkan_id WHERE k.id = ?", (kullanici_id,)
    ).fetchone()


def kayit_denetle(baglanti, eposta, sifre, sifre2=None, dukkan_adi=None):
    """Kayit formunu denetler; sorun varsa sebebini metin olarak doner.

    dukkan_adi None ise dukkan adi sorulmaz: mevcut bir dukkana kullanici
    eklerken dukkan zaten var.
    """
    if dukkan_adi is not None and not dukkan_adi.strip():
        return "Dükkanın adını yaz."
    eposta = _eposta_duzelt(eposta)
    if not eposta:
        return "Kullanıcı adı ya da e-posta yaz."
    if len(eposta) > 120 or re.search(r"\s", eposta):
        return "Kullanıcı adında boşluk olamaz."
    if len(sifre or "") < EN_KISA_SIFRE:
        return f"Şifre en az {EN_KISA_SIFRE} karakter olmalı."
    if sifre2 is not None and sifre != sifre2:
        return "İki şifre birbirini tutmuyor."
    if kullanici_bul(baglanti, eposta):
        return "Bu kullanıcı adı zaten alınmış."
    return ""


def _simdi():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def kullanici_ekle(baglanti, dukkan_id, eposta, ad, sifre):
    """Var olan bir dukkana kullanici ekler; numarasini doner."""
    kullanici_id = baglanti.execute(
        "INSERT INTO kullanicilar (dukkan_id, eposta, ad, sifre_ozet, rol, kuruldu) "
        "VALUES (?, ?, ?, ?, 'sahip', ?)",
        (dukkan_id, _eposta_duzelt(eposta), (ad or "").strip(),
         sifre_ozetle(sifre), _simdi()),
    ).lastrowid
    baglanti.commit()
    return kullanici_id


def dukkan_saglama(baglanti, dukkan_id, ad):
    """Numarasi belli bir dukkani deftere yazar; zaten varsa dokunmaz.

    Tek dukkanli surumden gelen kurulumda dukkan 1'in dosyasi vardir ama
    defterde kaydi yoktur; ilk hesap kurulurken buradan eklenir.
    """
    baglanti.execute(
        "INSERT OR IGNORE INTO dukkanlar (id, ad, kuruldu) VALUES (?, ?, ?)",
        (dukkan_id, (ad or "").strip() or "Dükkanım", _simdi()),
    )
    baglanti.commit()


def kayit_ol(baglanti, dukkan_adi, eposta, ad, sifre):
    """Yeni dukkan + o dukkanin sahibi. (kullanici_id, dukkan_id) doner.

    Ikisi tek islemde yazilir: yarim kalirsa sahipsiz bir dukkan kaydi
    ya da dukkansiz bir kullanici kalmasin.
    """
    simdi = _simdi()
    with baglanti:
        dukkan_id = baglanti.execute(
            "INSERT INTO dukkanlar (ad, kuruldu) VALUES (?, ?)",
            (dukkan_adi.strip(), simdi),
        ).lastrowid
        kullanici_id = baglanti.execute(
            "INSERT INTO kullanicilar (dukkan_id, eposta, ad, sifre_ozet, rol, kuruldu) "
            "VALUES (?, ?, ?, ?, 'sahip', ?)",
            (dukkan_id, _eposta_duzelt(eposta), (ad or "").strip(),
             sifre_ozetle(sifre), simdi),
        ).lastrowid
    return kullanici_id, dukkan_id


def dogrula(baglanti, eposta, sifre):
    """Girisi dogrular. Basarisizsa None doner - sebebi asla soylenmez.

    "Kullanici yok" ile "sifre yanlis" ayri ayri soylenirse, disaridan biri
    hangi kullanici adlarinin var oldugunu tek tek ogrenebilir.
    """
    kayit = kullanici_bul(baglanti, eposta)
    if not kayit or not sifre_uyar_mi(kayit["sifre_ozet"], sifre or ""):
        return None
    baglanti.execute(
        "UPDATE kullanicilar SET son_giris = ? WHERE id = ?",
        (datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), kayit["id"]),
    )
    baglanti.commit()
    return kayit


def sifre_degistir(baglanti, kullanici_id, sifre):
    """Sifreyi degistirir; sorun varsa sebebini metin olarak doner."""
    if len(sifre or "") < EN_KISA_SIFRE:
        return f"Şifre en az {EN_KISA_SIFRE} karakter olmalı."
    baglanti.execute("UPDATE kullanicilar SET sifre_ozet = ? WHERE id = ?",
                     (sifre_ozetle(sifre), kullanici_id))
    baglanti.commit()
    return ""


def dukkan_adi_yaz(baglanti, dukkan_id, ad):
    """Dukkan adi hem dukkanin kendi dosyasinda hem defterde durur.

    Defterdeki kopya giris ekraninda ve yonetimde lazim; oraya bakmak icin
    dukkanin dosyasini acmak gerekmesin diye burada da tutulur.
    """
    baglanti.execute("UPDATE dukkanlar SET ad = ? WHERE id = ?",
                     ((ad or "").strip() or "Dükkanım", dukkan_id))
    baglanti.commit()


def dukkan_kimlikleri(baglanti):
    """Butun dukkanlarin numaralari. Arka plan isleri hepsini tek tek gezer."""
    return [satir["id"] for satir in
            baglanti.execute("SELECT id FROM dukkanlar ORDER BY id")]


# ---------------------------------------------------------------- oturum

def oturum_anahtari(baglanti):
    """Cerezleri imzalayan gizli anahtar; ilk ihtiyacta uretilir.

    Uretildigi anda kaydedilmesi sart: kaydedilmezse her istek kendine yeni
    bir anahtar uretir, bir onceki istekte verilen cerez hicbir zaman
    dogrulanmaz ve giris hic tutmaz.
    """
    satir = baglanti.execute(
        "SELECT deger FROM ayarlar WHERE anahtar = 'oturum_anahtari'"
    ).fetchone()
    if satir and satir["deger"]:
        return satir["deger"]
    deger = secrets.token_hex(32)
    baglanti.execute(
        "INSERT OR REPLACE INTO ayarlar (anahtar, deger) VALUES ('oturum_anahtari', ?)",
        (deger,),
    )
    baglanti.commit()
    return deger


if __name__ == "__main__":
    baglanti = hazirla()
    print(f"Defter: {DB_YOLU}")
    for satir in baglanti.execute(
        "SELECT d.id, d.ad, COUNT(k.id) AS kisi FROM dukkanlar d "
        "LEFT JOIN kullanicilar k ON k.dukkan_id = d.id GROUP BY d.id ORDER BY d.id"
    ):
        print(f"  {satir['id']}. {satir['ad']} - {satir['kisi']} kullanici")
