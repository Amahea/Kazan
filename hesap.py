# -*- coding: utf-8 -*-
"""Isin mantigi: stok dusumu, maliyet hesabi, gun sonu ozeti ve oneriler.

Buradaki fonksiyonlar veritabanina yazar ama ekranla hic ilgilenmez.
Ekranlar uygulama.py icinde.

Butun hesaplar tek bir kurala dayanir: bir kalemin recetesi, kalem
"uretilir" isaretliyse URETIMDE, degilse HER SATISTA stoktan duser.
Dondurmaci ile firincinin farki bu kutucuktan ibarettir; kodda ayrica
dondurmaya ya da ekmege dair hicbir sey yoktur.
"""

import datetime
import math

from veritabani import ayar, sayi

TARIH_BICIMI = "%Y-%m-%d"
EPSILON = 0.0001


def bugun():
    return datetime.date.today().strftime(TARIH_BICIMI)


def _simdi():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------- kalem sorgulari

def kalem(baglanti, kalem_id):
    return baglanti.execute("SELECT * FROM kalemler WHERE id = ?", (kalem_id,)).fetchone()


def kalemler(baglanti, rol=None, sadece_aktif=True):
    """rol: 'alinir', 'uretilir', 'satilir' ya da None (hepsi)."""
    kosullar = ["1 = 1"]
    if rol:
        kosullar.append(f"{rol} = 1")
    if sadece_aktif:
        kosullar.append("aktif = 1")
    return baglanti.execute(
        f"SELECT * FROM kalemler WHERE {' AND '.join(kosullar)} ORDER BY sira, ad"
    ).fetchall()


TURSUZ = "Türü yazılmamış"


def turler(baglanti):
    """Kullanimda olan tur basliklari, alfabetik. Turu bos olanlar sona."""
    liste = sorted(
        satir["tur"] for satir in baglanti.execute(
            "SELECT DISTINCT tur FROM kalemler WHERE tur <> ''"
        )
    )
    return liste


def ture_gore(kalemler_listesi):
    """Kalemleri tur basligina gore gruplar: [(baslik, [kalem, ...]), ...]"""
    gruplar = {}
    for kalem in kalemler_listesi:
        gruplar.setdefault(kalem["tur"] or TURSUZ, []).append(kalem)
    return sorted(gruplar.items(), key=lambda ikili: (ikili[0] == TURSUZ, ikili[0]))


def stoklar(baglanti):
    """Her kalemin guncel stogu: {kalem_id: miktar}"""
    satirlar = baglanti.execute(
        "SELECT kalem_id, SUM(miktar) AS toplam FROM stok_hareketleri GROUP BY kalem_id"
    ).fetchall()
    return {satir["kalem_id"]: satir["toplam"] or 0.0 for satir in satirlar}


def kalem_listesi(baglanti, sadece_aktif=True):
    """Kalemler + guncel stok + birim maliyet, tek listede."""
    stok = stoklar(baglanti)
    liste = []
    for satir in kalemler(baglanti, sadece_aktif=sadece_aktif):
        kayit = dict(satir)
        kayit["stok"] = stok.get(satir["id"], 0.0)
        kayit["maliyet"] = birim_maliyet(baglanti, satir["id"])
        kayit["deger"] = kayit["stok"] * kayit["maliyet"]
        liste.append(kayit)
    return liste


def kasa(baglanti):
    return baglanti.execute(
        "SELECT COALESCE(SUM(tutar), 0) FROM kasa_hareketleri"
    ).fetchone()[0]


def borc(baglanti):
    return baglanti.execute(
        "SELECT COALESCE(SUM(tutar), 0) FROM borc_hareketleri"
    ).fetchone()[0]


def borc_dagilimi(baglanti):
    return baglanti.execute(
        "SELECT tedarikci, SUM(tutar) AS tutar FROM borc_hareketleri"
        " GROUP BY tedarikci HAVING ABS(SUM(tutar)) > 0.01 ORDER BY tutar DESC"
    ).fetchall()


# ---------------------------------------------------------------- receteler

def receteler(baglanti, urun_id, sadece_aktif=True):
    ek = " AND aktif = 1" if sadece_aktif else ""
    return baglanti.execute(
        f"SELECT * FROM receteler WHERE urun_id = ?{ek} ORDER BY sira, id", (urun_id,)
    ).fetchall()


def ana_recete(baglanti, urun_id):
    """Bir kalemin varsayilan recetesi: ilk aktif olan."""
    liste = receteler(baglanti, urun_id)
    return liste[0] if liste else None


def recete_satirlari(baglanti, recete_id):
    return baglanti.execute(
        "SELECT r.*, k.ad, k.birim, k.takip FROM recete_satirlari r"
        " JOIN kalemler k ON k.id = r.kalem_id WHERE r.recete_id = ? ORDER BY k.ad",
        (recete_id,),
    ).fetchall()


def recete_maliyeti(baglanti, recete_id, _zincir=()):
    """Recetenin bir uretiminin (verim kadar cikan) malzeme maliyeti."""
    return sum(
        satir["miktar"] * birim_maliyet(baglanti, satir["kalem_id"], _zincir)
        for satir in baglanti.execute(
            "SELECT kalem_id, miktar FROM recete_satirlari WHERE recete_id = ?",
            (recete_id,),
        )
    )


def birim_maliyet(baglanti, kalem_id, _zincir=()):
    """Stokta duran bir birimin maliyeti.

    Uretilen kalemlerde gercek uretim kayitlarinin ortalamasi kullanilir; hic
    uretim yoksa receteden tahmin edilir, boylece ilk gunlerde de kar sifir
    cikmaz. Satin alinan kalemlerde son alis fiyatidir.

    _zincir, recetesi kendini isaret eden bir kurgu sonsuz donguye girmesin diye
    tasinir; boyle bir halka gorulurse o dal sifir maliyetle kapatilir.
    """
    if kalem_id in _zincir:
        return 0.0
    satir = kalem(baglanti, kalem_id)
    if satir is None:
        return 0.0

    if satir["uretilir"]:
        gecmis = baglanti.execute(
            "SELECT COALESCE(SUM(maliyet), 0) AS maliyet, COALESCE(SUM(miktar), 0) AS miktar"
            " FROM uretimler WHERE kalem_id = ?", (kalem_id,)
        ).fetchone()
        if gecmis["miktar"] > 0:
            return gecmis["maliyet"] / gecmis["miktar"]
        recete = ana_recete(baglanti, kalem_id)
        if recete and recete["verim"] > 0:
            return recete_maliyeti(baglanti, recete["id"], _zincir + (kalem_id,)) / recete["verim"]
    return satir["birim_fiyat"]


def satis_maliyeti(baglanti, kalem_id):
    """Bir birim satisin dukkana maliyeti.

    Kalem stokta duruyorsa (kulah, ekmek, pet su) kendi birim maliyeti sayilir.
    Uretilmiyorsa recetesi de eklenir: kulahin ustune 60 gram dondurma gibi.
    Uretilen kalemde recete eklenmez, cunku o maliyet zaten uretimde islendi.
    """
    satir = kalem(baglanti, kalem_id)
    if satir is None:
        return 0.0
    toplam = birim_maliyet(baglanti, kalem_id) if satir["takip"] else 0.0
    if not satir["uretilir"]:
        recete = ana_recete(baglanti, kalem_id)
        if recete:
            toplam += recete_maliyeti(baglanti, recete["id"]) / (recete["verim"] or 1)
    return toplam


def _stok_yaz(baglanti, tarih, kalem_id, miktar, sebep, kaynak_tur, kaynak_id):
    """Takip edilmeyen kalemler (sebeke suyu gibi) stoktan dusulmez."""
    satir = kalem(baglanti, kalem_id)
    if satir is None or not satir["takip"] or abs(miktar) < EPSILON:
        return
    baglanti.execute(
        "INSERT INTO stok_hareketleri (tarih, kalem_id, miktar, sebep, kaynak_tur, kaynak_id)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (tarih, kalem_id, miktar, sebep, kaynak_tur, kaynak_id),
    )


def _recete_dus(baglanti, tarih, recete_id, kat, sebep, kaynak_tur, kaynak_id):
    for satir in baglanti.execute(
        "SELECT kalem_id, miktar FROM recete_satirlari WHERE recete_id = ?", (recete_id,)
    ).fetchall():
        _stok_yaz(baglanti, tarih, satir["kalem_id"], -satir["miktar"] * kat,
                  sebep, kaynak_tur, kaynak_id)


# ---------------------------------------------------------------- kayit ekleme

def uretim_ekle(baglanti, tarih, recete_id, adet):
    """Uretim: recetedeki malzemeler stoktan duser, urun stogu artar."""
    recete = baglanti.execute(
        "SELECT r.*, k.ad AS urun_ad FROM receteler r JOIN kalemler k ON k.id = r.urun_id"
        " WHERE r.id = ?", (recete_id,)
    ).fetchone()
    if recete is None or adet <= 0:
        return None

    maliyet = recete_maliyeti(baglanti, recete_id) * adet
    miktar = recete["verim"] * adet
    etiket = f"{recete['urun_ad']}{' - ' + recete['ad'] if recete['ad'] else ''}"

    uretim_id = baglanti.execute(
        "INSERT INTO uretimler (tarih, recete_id, kalem_id, sayi, miktar, maliyet, kayit_zamani)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (tarih, recete_id, recete["urun_id"], adet, miktar, maliyet, _simdi()),
    ).lastrowid

    _recete_dus(baglanti, tarih, recete_id, adet, f"Üretim: {etiket}", "uretim", uretim_id)
    _stok_yaz(baglanti, tarih, recete["urun_id"], miktar, f"Üretim: {etiket}",
              "uretim", uretim_id)
    baglanti.commit()
    return uretim_id


def satis_ekle(baglanti, tarih, kalem_id, miktar, sayim_id=None):
    """Satis: kasaya para girer, urun ve recetesi stoktan duser."""
    urun = kalem(baglanti, kalem_id)
    if urun is None or miktar <= 0:
        return None

    tutar = miktar * urun["fiyat"]
    maliyet = miktar * satis_maliyeti(baglanti, kalem_id)

    satis_id = baglanti.execute(
        "INSERT INTO satislar (tarih, kalem_id, miktar, tutar, maliyet, sayim_id, kayit_zamani)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (tarih, kalem_id, miktar, tutar, maliyet, sayim_id, _simdi()),
    ).lastrowid

    baglanti.execute(
        "INSERT INTO kasa_hareketleri (tarih, tutar, aciklama, kaynak_tur, kaynak_id)"
        " VALUES (?, ?, ?, 'satis', ?)",
        (tarih, tutar, f"Satış: {urun['ad']}", satis_id),
    )
    _stok_yaz(baglanti, tarih, kalem_id, -miktar, f"Satış: {urun['ad']}", "satis", satis_id)
    if not urun["uretilir"]:
        recete = ana_recete(baglanti, kalem_id)
        if recete:
            _recete_dus(baglanti, tarih, recete["id"], miktar / (recete["verim"] or 1),
                        f"Satış: {urun['ad']}", "satis", satis_id)
    baglanti.commit()
    return satis_id


def alim_ekle(baglanti, tarih, kalem_id, miktar, tutar, odeme, tedarikci=""):
    """Alim. Pesinse kasadan duser, veresiyeyse borca yazar."""
    urun = kalem(baglanti, kalem_id)
    if urun is None or miktar <= 0:
        return None

    tedarikci = tedarikci or urun["tedarikci"]
    alim_id = baglanti.execute(
        "INSERT INTO alimlar (tarih, kalem_id, miktar, tutar, odeme, tedarikci, kayit_zamani)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (tarih, kalem_id, miktar, tutar, odeme, tedarikci, _simdi()),
    ).lastrowid

    _stok_yaz(baglanti, tarih, kalem_id, miktar, f"Alım: {tedarikci}".strip(),
              "alim", alim_id)

    # Son alis fiyatini guncelle; maliyet hesaplari hep guncel fiyattan yurusun.
    if tutar > 0:
        baglanti.execute(
            "UPDATE kalemler SET birim_fiyat = ? WHERE id = ?", (tutar / miktar, kalem_id)
        )

    if odeme == "pesin":
        baglanti.execute(
            "INSERT INTO kasa_hareketleri (tarih, tutar, aciklama, kaynak_tur, kaynak_id)"
            " VALUES (?, ?, ?, 'alim', ?)",
            (tarih, -tutar, f"Alım: {urun['ad']}", alim_id),
        )
    else:
        baglanti.execute(
            "INSERT INTO borc_hareketleri (tarih, tedarikci, tutar, aciklama, kaynak_tur, kaynak_id)"
            " VALUES (?, ?, ?, ?, 'alim', ?)",
            (tarih, tedarikci, tutar, f"Alım: {urun['ad']}", alim_id),
        )
    baglanti.commit()
    return alim_id


def gider_ekle(baglanti, tarih, aciklama, tutar):
    """Kira, elektrik, personel gibi giderler: kasadan cikar."""
    if tutar <= 0:
        return None
    gider_id = baglanti.execute(
        "INSERT INTO giderler (tarih, aciklama, tutar, kayit_zamani) VALUES (?, ?, ?, ?)",
        (tarih, aciklama, tutar, _simdi()),
    ).lastrowid
    baglanti.execute(
        "INSERT INTO kasa_hareketleri (tarih, tutar, aciklama, kaynak_tur, kaynak_id)"
        " VALUES (?, ?, ?, 'gider', ?)",
        (tarih, -tutar, aciklama or "Gider", gider_id),
    )
    baglanti.commit()
    return gider_id


def odeme_ekle(baglanti, tarih, tedarikci, tutar):
    """Tedarikciye borc odemesi: kasa azalir, borc azalir."""
    if tutar <= 0:
        return None
    odeme_id = baglanti.execute(
        "INSERT INTO odemeler (tarih, tedarikci, tutar, kayit_zamani) VALUES (?, ?, ?, ?)",
        (tarih, tedarikci, tutar, _simdi()),
    ).lastrowid
    baglanti.execute(
        "INSERT INTO kasa_hareketleri (tarih, tutar, aciklama, kaynak_tur, kaynak_id)"
        " VALUES (?, ?, ?, 'odeme', ?)",
        (tarih, -tutar, f"Ödeme: {tedarikci}", odeme_id),
    )
    baglanti.execute(
        "INSERT INTO borc_hareketleri (tarih, tedarikci, tutar, aciklama, kaynak_tur, kaynak_id)"
        " VALUES (?, ?, ?, ?, 'odeme', ?)",
        (tarih, tedarikci, -tutar, "Borç ödemesi", odeme_id),
    )
    baglanti.commit()
    return odeme_id


def sayim_duzelt(baglanti, tarih, kalem_id, gercek_miktar, aciklama="Sayım düzeltmesi"):
    """Elle sayim sonucu: fark kadar hareket yazar, stok gercege esitlenir."""
    fark = gercek_miktar - stoklar(baglanti).get(kalem_id, 0.0)
    if abs(fark) < EPSILON:
        return 0.0
    baglanti.execute(
        "INSERT INTO stok_hareketleri (tarih, kalem_id, miktar, sebep, kaynak_tur)"
        " VALUES (?, ?, ?, ?, 'elle_sayim')",
        (tarih, kalem_id, fark, aciklama),
    )
    baglanti.commit()
    return fark


# ---------------------------------------------------------------- gun sonu sayimi

def sayilacaklar(baglanti):
    """Gun sonu ekraninda cikacak kalemler, sayim tarzina gore gruplu."""
    gruplar = {"say": [], "koli": [], "elle": []}
    for satir in kalemler(baglanti):
        if satir["sayim_tarzi"] in gruplar and (satir["takip"] or satir["sayim_tarzi"] == "elle"):
            gruplar[satir["sayim_tarzi"]].append(satir)
    return gruplar


def sayim_getir(baglanti, tarih):
    return baglanti.execute("SELECT * FROM sayimlar WHERE tarih = ?", (tarih,)).fetchone()


def sayim_satirlari(baglanti, sayim_id):
    return baglanti.execute(
        "SELECT s.*, k.ad, k.birim, k.koli_adet, k.koli_ad FROM sayim_satirlari s"
        " JOIN kalemler k ON k.id = s.kalem_id WHERE s.sayim_id = ? ORDER BY k.sira, k.ad",
        (sayim_id,),
    ).fetchall()


def sayim_sil(baglanti, tarih):
    """O gunun sayimini ve ondan turetilen tum satis/stok kayitlarini geri alir."""
    sayim = sayim_getir(baglanti, tarih)
    if sayim is None:
        return False
    for satis in baglanti.execute(
        "SELECT id FROM satislar WHERE sayim_id = ?", (sayim["id"],)
    ).fetchall():
        kayit_sil(baglanti, "satis", satis["id"])
    baglanti.execute(
        "DELETE FROM stok_hareketleri WHERE kaynak_tur = 'sayim' AND kaynak_id = ?",
        (sayim["id"],),
    )
    baglanti.execute("DELETE FROM sayim_satirlari WHERE sayim_id = ?", (sayim["id"],))
    baglanti.execute("DELETE FROM sayimlar WHERE id = ?", (sayim["id"],))
    baglanti.commit()
    return True


def sayim_kaydet(baglanti, tarih, kalanlar, elle_satislar=None, bitenler=()):
    """Gun sonu sayimi. Raflarda kalani yazarsin, program ne satildigini bulur.

    kalanlar      -> {kalem_id: (koli, adet)} raflarda kalan miktar
    elle_satislar -> {kalem_id: miktar} sayimla bulunamayanlar (kilo ile satis)
    bitenler      -> o gun bir kolisi biten kalemler (kasik, pecete). Tek tek
                     sayilmadiklari icin bir koli dolusu tuketilmis sayilir.

    Iki asamada yurur. Once satilan kalemlerin tuketimi sabah stogundan
    hesaplanip satisa cevrilir; sonra butun sayilanlar, satislar islendikten
    sonraki stokla karsilastirilip aradaki fark fire/sarf olarak yazilir.
    Ayni tarihe ikinci kez sayim girilirse oncekini silip bastan hesaplar.
    """
    sayim_sil(baglanti, tarih)
    sayim_id = baglanti.execute(
        "INSERT INTO sayimlar (tarih, kayit_zamani) VALUES (?, ?)", (tarih, _simdi())
    ).lastrowid

    # Satislar stogu degistirecegi icin once sabahki fotografi cekiyoruz.
    onceki_stok = stoklar(baglanti)
    tumu = {satir["id"]: satir for satir in kalemler(baglanti)}

    hedefler = {}   # kalem_id -> rafta kalmasi gereken miktar
    for kalem_id, (koli, adet) in kalanlar.items():
        satir = tumu.get(kalem_id)
        if satir is not None and satir["takip"]:
            hedefler[kalem_id] = koli * satir["koli_adet"] + adet
    for kalem_id in bitenler:
        satir = tumu.get(kalem_id)
        if satir is not None and satir["takip"] and satir["koli_adet"] > 0:
            hedefler[kalem_id] = max(onceki_stok.get(kalem_id, 0.0) - satir["koli_adet"], 0.0)

    # 1. asama: satilan kalemlerde eksilen miktar = o gun satilan miktar.
    tuketimler = {}
    for kalem_id, hedef in hedefler.items():
        tuketim = onceki_stok.get(kalem_id, 0.0) - hedef
        tuketimler[kalem_id] = tuketim
        if tumu[kalem_id]["satilir"] and tuketim > EPSILON:
            satis_ekle(baglanti, tarih, kalem_id, tuketim, sayim_id)

    for kalem_id, miktar in (elle_satislar or {}).items():
        if miktar > 0 and kalem_id in tumu:
            satis_ekle(baglanti, tarih, kalem_id, miktar, sayim_id)

    # 2. asama: satislar islendikten sonra kalan fark fire ya da sarftir.
    guncel_stok = stoklar(baglanti)
    for kalem_id, hedef in hedefler.items():
        fark = hedef - guncel_stok.get(kalem_id, 0.0)
        if abs(fark) > EPSILON:
            dagitilir = tumu[kalem_id]["dagit"] and not tumu[kalem_id]["satilir"]
            baglanti.execute(
                "INSERT INTO stok_hareketleri (tarih, kalem_id, miktar, sebep,"
                " kaynak_tur, kaynak_id) VALUES (?, ?, ?, ?, 'sayim', ?)",
                (tarih, kalem_id, fark,
                 "Sarf" if (dagitilir and fark < 0) else "Sayım farkı", sayim_id),
            )

    for kalem_id, (koli, adet) in kalanlar.items():
        if kalem_id in hedefler:
            baglanti.execute(
                "INSERT INTO sayim_satirlari (sayim_id, kalem_id, koli, adet, kalan, tuketim)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (sayim_id, kalem_id, koli, adet, hedefler[kalem_id], tuketimler[kalem_id]),
            )
    for kalem_id in bitenler:
        if kalem_id in hedefler:
            baglanti.execute(
                "INSERT OR IGNORE INTO sayim_satirlari"
                " (sayim_id, kalem_id, koli, adet, kalan, tuketim)"
                " VALUES (?, ?, 0, 0, ?, ?)",
                (sayim_id, kalem_id, hedefler[kalem_id], tuketimler[kalem_id]),
            )

    _dagitilan_maliyeti_yay(baglanti, sayim_id, tuketimler, tumu)
    baglanti.commit()
    return sayim_id


def _dagitilan_maliyeti_yay(baglanti, sayim_id, tuketimler, tumu):
    """Satilmayan ama harcanan kalemlerin (kasik, pecete, kilo kabi) tutarini
    o gunun satislarina paylastirir; boylece bir satisin gercek maliyeti cikar."""
    toplam = sum(
        tuketim * birim_maliyet(baglanti, kalem_id)
        for kalem_id, tuketim in tuketimler.items()
        if tuketim > 0 and tumu[kalem_id]["dagit"] and not tumu[kalem_id]["satilir"]
    )
    if toplam <= 0:
        return

    satislar = baglanti.execute(
        "SELECT id, miktar FROM satislar WHERE sayim_id = ?", (sayim_id,)
    ).fetchall()
    toplam_miktar = sum(satis["miktar"] for satis in satislar)
    if toplam_miktar <= 0:
        return
    for satis in satislar:
        pay = toplam * satis["miktar"] / toplam_miktar
        baglanti.execute(
            "UPDATE satislar SET maliyet = maliyet + ? WHERE id = ?", (pay, satis["id"])
        )


# ---------------------------------------------------------------- silme

_SILINEBILIR = {
    "satis": "satislar",
    "uretim": "uretimler",
    "alim": "alimlar",
    "gider": "giderler",
    "odeme": "odemeler",
}


def kayit_sil(baglanti, tur, kayit_id):
    """Yanlis girilen kaydi ve dogurdugu tum stok/kasa/borc hareketlerini siler."""
    tablo = _SILINEBILIR.get(tur)
    if not tablo:
        return False
    for hareket in ("stok_hareketleri", "kasa_hareketleri", "borc_hareketleri"):
        baglanti.execute(
            f"DELETE FROM {hareket} WHERE kaynak_tur = ? AND kaynak_id = ?", (tur, kayit_id)
        )
    baglanti.execute(f"DELETE FROM {tablo} WHERE id = ?", (kayit_id,))
    baglanti.commit()
    return True


# ---------------------------------------------------------------- ozet ve oneriler

def gun_ozeti(baglanti, tarih):
    ciro, maliyet = baglanti.execute(
        "SELECT COALESCE(SUM(tutar), 0), COALESCE(SUM(maliyet), 0)"
        " FROM satislar WHERE tarih = ?", (tarih,)
    ).fetchone()
    gider = baglanti.execute(
        "SELECT COALESCE(SUM(tutar), 0) FROM giderler WHERE tarih = ?", (tarih,)
    ).fetchone()[0]
    alim_pesin = baglanti.execute(
        "SELECT COALESCE(SUM(tutar), 0) FROM alimlar WHERE tarih = ? AND odeme = 'pesin'",
        (tarih,),
    ).fetchone()[0]
    alim_veresiye = baglanti.execute(
        "SELECT COALESCE(SUM(tutar), 0) FROM alimlar WHERE tarih = ? AND odeme <> 'pesin'",
        (tarih,),
    ).fetchone()[0]
    odeme = baglanti.execute(
        "SELECT COALESCE(SUM(tutar), 0) FROM odemeler WHERE tarih = ?", (tarih,)
    ).fetchone()[0]
    uretim_maliyeti = baglanti.execute(
        "SELECT COALESCE(SUM(maliyet), 0) FROM uretimler WHERE tarih = ?", (tarih,)
    ).fetchone()[0]
    # Sarf tutari zaten satis maliyetine dagitildi; burada ayrica gosterilsin diye.
    sarf = baglanti.execute(
        "SELECT COALESCE(SUM(-h.miktar * k.birim_fiyat), 0) FROM stok_hareketleri h"
        " JOIN kalemler k ON k.id = h.kalem_id WHERE h.tarih = ? AND h.sebep = 'Sarf'",
        (tarih,),
    ).fetchone()[0]

    return {
        "tarih": tarih,
        "ciro": ciro,
        "satis_maliyeti": maliyet,
        "brut_kar": ciro - maliyet,
        "gider": gider,
        "net_kar": ciro - maliyet - gider,
        "sarf_maliyeti": sarf,
        "alim_pesin": alim_pesin,
        "alim_veresiye": alim_veresiye,
        "borc_odemesi": odeme,
        "kasa_degisimi": ciro - gider - alim_pesin - odeme,
        "uretim_maliyeti": uretim_maliyeti,
    }


def gunluk_tuketim(baglanti, kalem_id, gun_sayisi):
    """Son N gunde bu kalemden gunde ortalama ne kadar harcanmis."""
    baslangic = (
        datetime.date.today() - datetime.timedelta(days=gun_sayisi - 1)
    ).strftime(TARIH_BICIMI)
    harcanan = baglanti.execute(
        "SELECT COALESCE(SUM(-miktar), 0) FROM stok_hareketleri"
        " WHERE kalem_id = ? AND miktar < 0 AND tarih >= ?",
        (kalem_id, baslangic),
    ).fetchone()[0]
    if harcanan <= 0:
        return 0.0

    ilk = baglanti.execute(
        "SELECT MIN(tarih) FROM stok_hareketleri WHERE kalem_id = ? AND miktar < 0 AND tarih >= ?",
        (kalem_id, baslangic),
    ).fetchone()[0]
    try:
        gecen = (datetime.date.today()
                 - datetime.datetime.strptime(ilk, TARIH_BICIMI).date()).days + 1
    except (TypeError, ValueError):
        gecen = gun_sayisi
    return harcanan / max(1, min(gun_sayisi, gecen))


def oneriler(baglanti):
    """'Sut bitmek uzere, 104 litre al' tarzi uyarilari uretir.

    Onem sirasi: once bitenler, sonra bitmek uzere olanlar.
    """
    ortalama_gun = int(sayi(ayar(baglanti, "ortalama_gun", "14"), 14))
    tedarik_gun = sayi(ayar(baglanti, "tedarik_gun", "3"), 3)
    emniyet_gun = sayi(ayar(baglanti, "emniyet_gun", "2"), 2)
    hedef_gun = tedarik_gun + emniyet_gun

    liste = []
    for satir in kalem_listesi(baglanti):
        if not satir["takip"] or not (satir["alinir"] or satir["uretilir"]):
            continue
        gunluk = gunluk_tuketim(baglanti, satir["id"], ortalama_gun)
        stok = satir["stok"]
        kalan_gun = stok / gunluk if gunluk > 0 else None

        kritik = satir["kritik_seviye"] > 0 and stok <= satir["kritik_seviye"]
        acil = kalan_gun is not None and kalan_gun <= hedef_gun
        if not kritik and not acil:
            continue

        gerekli = gunluk * hedef_gun - stok
        if gunluk <= 0:
            gerekli = max(satir["kritik_seviye"] * 2 - stok, 0)
        onerilen = math.ceil(max(gerekli, 0))

        liste.append({
            "kalem": satir,
            "stok": stok,
            "gunluk": gunluk,
            "kalan_gun": kalan_gun,
            "onerilen": onerilen,
            "tutar": onerilen * satir["maliyet"],
            "eylem": "al" if satir["alinir"] else "üret",
            "seviye": "bitti" if stok <= 0 else (
                "acil" if (kalan_gun or 99) <= tedarik_gun else "yakin"),
        })

    sirala = {"bitti": 0, "acil": 1, "yakin": 2}
    liste.sort(key=lambda k: (sirala[k["seviye"]],
                              k["kalan_gun"] if k["kalan_gun"] is not None else 999))
    return liste
