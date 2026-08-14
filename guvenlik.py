# -*- coding: utf-8 -*-
"""Giris sifresi ve oturum yonetimi.

Program dukkanda, kendi wifi'inda calisirken sifreye gerek yoktur; disaridan
kimse o agda degildir. Ama program internete acilirsa adresi bilen herkes
kasayi, cirouyu, tedarikcileri gorur ve degistirir. Bu yuzden sifre ISTEGE
BAGLI tutuldu:

    sifre yok  -> program eskisi gibi dogrudan acilir (dukkan ici kullanim)
    sifre var  -> her sayfa once girisi sorar

Sifre uc yerden gelebilir, sirasiyla:

    1. KAZAN_SIFRE ortam degiskeni  -> sunucuya kurulumda verilir. Internete
       acilan kurulumda bu kullanilir; boylece bos veritabaniyla acilan bir
       kopya bile ilk saniyeden sifreli olur, "sifre koymayi unuttum" diye
       bir acik kalmaz.
    2. Ayarlar ekranindan kurulan sifre -> veritabaninda ozeti durur.
    3. Hicbiri yoksa sifre kapalidir.

Sifre hicbir yerde acik metin durmaz; pbkdf2 ozeti saklanir. Ortam
degiskeninden gelen sifre ise zaten diske hic yazilmaz.

Oturum sunucunun belleginde tutulmaz - cerezin icine son kullanma tarihi ve
imzasi konur. Boylece program yeniden baslayinca acik oturumlar bozulmaz ve
sunucu tarafinda temizlenmesi gereken bir liste birikmez.
"""

import base64
import hashlib
import hmac
import os
import secrets
import time

from veritabani import ayar, ayar_yaz

ORTAM_ANAHTARI = "KAZAN_SIFRE"
CEREZ_ADI = "kazan_oturum"
OTURUM_GUN = 30
DONGU = 200_000          # pbkdf2 tur sayisi
EN_KISA_SIFRE = 6


# ---------------------------------------------------------------- sifre

def _ozet(sifre, tuz):
    return hashlib.pbkdf2_hmac("sha256", sifre.encode("utf-8"),
                               bytes.fromhex(tuz), DONGU).hex()


def _ortam_sifresi():
    """Sunucuya kurulumda verilen sifre. Bosluk sadece yazim hatasidir."""
    return (os.environ.get(ORTAM_ANAHTARI) or "").strip()


def sifre_var_mi(baglanti):
    return bool(_ortam_sifresi()) or bool(ayar(baglanti, "sifre_ozet", ""))


def ortamdan_mi():
    """Sifre sunucudan mi geliyor - Ayarlar ekraninda degistirilemez demektir."""
    return bool(_ortam_sifresi())


def sifre_kur(baglanti, sifre):
    """Yeni sifre kurar. Kisa sifreyi reddeder, sebebini metin olarak doner."""
    sifre = (sifre or "").strip()
    if len(sifre) < EN_KISA_SIFRE:
        return f"Şifre en az {EN_KISA_SIFRE} karakter olmalı."
    tuz = secrets.token_hex(16)
    ayar_yaz(baglanti, "sifre_ozet", f"{tuz}${_ozet(sifre, tuz)}")
    # Sifre degisince eski cerezler gecersizlesir: baskasinin acik oturumu
    # varsa kapanir. Sifre degistirmenin asil anlami budur.
    ayar_yaz(baglanti, "oturum_anahtari", secrets.token_hex(32))
    baglanti.commit()
    return ""


def sifre_kaldir(baglanti):
    ayar_yaz(baglanti, "sifre_ozet", "")
    ayar_yaz(baglanti, "oturum_anahtari", secrets.token_hex(32))
    baglanti.commit()


def sifre_dogru_mu(baglanti, sifre):
    sifre = (sifre or "").strip()
    if not sifre:
        return False

    ortam = _ortam_sifresi()
    if ortam:
        return hmac.compare_digest(sifre, ortam)

    kayit = ayar(baglanti, "sifre_ozet", "")
    if "$" not in kayit:
        return False
    tuz, beklenen = kayit.split("$", 1)
    return hmac.compare_digest(_ozet(sifre, tuz), beklenen)


# ---------------------------------------------------------------- oturum

def _anahtar(baglanti):
    """Cerezleri imzalayan gizli anahtar; ilk ihtiyacta uretilir.

    Uretildigi anda kaydedilmesi sart: kaydedilmezse her istek kendine yeni
    bir anahtar uretir, bir onceki istekte verilen cerez hicbir zaman
    dogrulanmaz ve giris hic tutmaz.
    """
    deger = ayar(baglanti, "oturum_anahtari", "")
    if not deger:
        deger = secrets.token_hex(32)
        ayar_yaz(baglanti, "oturum_anahtari", deger)
        baglanti.commit()
    return deger.encode("utf-8")


def _imza(baglanti, govde):
    ham = hmac.new(_anahtar(baglanti), govde.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(ham).decode("ascii").rstrip("=")


def cerez_uret(baglanti):
    """'<bitis>.<imza>' - sunucuda hicbir sey saklanmaz."""
    bitis = str(int(time.time()) + OTURUM_GUN * 24 * 3600)
    return f"{bitis}.{_imza(baglanti, bitis)}"


def cerez_gecerli_mi(baglanti, deger):
    if not deger or "." not in deger:
        return False
    bitis, imza = deger.rsplit(".", 1)
    if not hmac.compare_digest(_imza(baglanti, bitis), imza):
        return False
    try:
        return int(bitis) > time.time()
    except ValueError:
        return False


def girisli_mi(baglanti, cerez_basligi):
    """Sifre kapaliysa herkes girmis sayilir; acikken cereze bakilir."""
    if not sifre_var_mi(baglanti):
        return True
    return cerez_gecerli_mi(baglanti, cerezden_oku(cerez_basligi))


def cerezden_oku(baslik):
    """Ham 'Cookie' basligindan bizim cerezi ayiklar."""
    for parca in (baslik or "").split(";"):
        ad, _, deger = parca.strip().partition("=")
        if ad == CEREZ_ADI:
            return deger
    return ""


def cerez_yaz(deger, https, omur=OTURUM_GUN * 24 * 3600):
    """Set-Cookie basligi.

    HttpOnly : sayfadaki betikler cereze bakamaz.
    SameSite : baska bir siteden gonderilen form bizim oturumu kullanamaz.
    Secure   : sadece https'te konur. Dukkan icindeki duz http kurulumda
               konursa tarayici cerezi hic saklamaz, giris hic tutmaz.
    """
    parcalar = [f"{CEREZ_ADI}={deger}", "Path=/", f"Max-Age={omur}",
                "HttpOnly", "SameSite=Lax"]
    if https:
        parcalar.append("Secure")
    return "; ".join(parcalar)


def cerez_sil(https):
    return cerez_yaz("", https, 0)
