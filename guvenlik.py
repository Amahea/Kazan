# -*- coding: utf-8 -*-
"""Oturum cerezi.

Sifreler ve kullanici kayitlari hesaplar.py'de; burasi sadece "giren kisi
kim" sorusunun cevabini tarayiciyla program arasinda tasir.

Program dukkanda, kendi wifi'inda calisirken girise gerek yoktur; disaridan
kimse o agda degildir. Bu yuzden giris ISTEGE BAGLI tutuldu:

    defterde hic kullanici yok  -> program eskisi gibi dogrudan acilir
    en az bir kullanici var     -> her sayfa once girisi sorar

Oturum sunucunun belleginde tutulmaz - cerezin icine kullanicinin numarasi,
son kullanma tarihi ve imzasi konur. Boylece program yeniden baslayinca acik
oturumlar bozulmaz ve sunucu tarafinda temizlenmesi gereken bir liste
birikmez. Imza olmadan cerez ise yaramaz: numarayi elle degistirip baska
birinin dukkanina girmek mumkun degildir, cunku imza tutmaz.
"""

import base64
import hashlib
import hmac
import time

import hesaplar

CEREZ_ADI = "kazan_oturum"
OTURUM_GUN = 30


def _imza(defter, govde):
    anahtar = hesaplar.oturum_anahtari(defter).encode("utf-8")
    ham = hmac.new(anahtar, govde.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(ham).decode("ascii").rstrip("=")


def cerez_uret(defter, kullanici_id):
    """'<kullanici>.<bitis>.<imza>' - sunucuda hicbir sey saklanmaz."""
    govde = f"{int(kullanici_id)}.{int(time.time()) + OTURUM_GUN * 24 * 3600}"
    return f"{govde}.{_imza(defter, govde)}"


def oturum_kullanicisi(defter, cerez_basligi):
    """Cerezdeki kullanici numarasi; gecersizse 0.

    Once imza dogrulanir, sonra kullanicinin hala defterde olduguna bakilir.
    Ikincisi onemli: hesabi silinen birinin cerezi hala imzali gorunur, ama
    artik girmemeli.
    """
    deger = cerezden_oku(cerez_basligi)
    if not deger or deger.count(".") != 2:
        return 0
    kimlik, bitis, imza = deger.split(".")
    if not hmac.compare_digest(_imza(defter, f"{kimlik}.{bitis}"), imza):
        return 0
    try:
        if int(bitis) <= time.time():
            return 0
        kullanici_id = int(kimlik)
    except ValueError:
        return 0
    return kullanici_id if hesaplar.kullanici(defter, kullanici_id) else 0


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


def cerez_deger(baslik, ad):
    """Ham 'Cookie' basligindan adi verilen cerezin degerini ayiklar."""
    for parca in (baslik or "").split(";"):
        a, _, deger = parca.strip().partition("=")
        if a == ad:
            return deger
    return ""


def deger_cerezi(ad, deger, https, omur=365 * 24 * 3600):
    """Oturumla ilgisi olmayan, acik bir tercih cerezi icin Set-Cookie.

    Dil secimi (dil=en) ya da tanitimin gorulup gorulmedigi gibi; icinde gizli
    bir sey yoktur, o yuzden imzalanmaz."""
    parcalar = [f"{ad}={deger}", "Path=/", f"Max-Age={omur}", "SameSite=Lax"]
    if https:
        parcalar.append("Secure")
    return "; ".join(parcalar)


def bayrak_cerezi(ad, https, omur=365 * 24 * 3600):
    """Basit bir "bu oldu" isareti: sadece 1 degeri durur.

    Tanitim ekraninin bir kez gosterilip bir daha gosterilmemesi gibi."""
    return deger_cerezi(ad, "1", https, omur)
