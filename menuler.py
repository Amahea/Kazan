# -*- coding: utf-8 -*-
"""Menu donemleri: yaz menusu, kis menusu ve aralarindaki gecis.

Dondurmaci havalar soguyunca otuz cesidi kapatir, alti cesitle devam eder ve
sahlep satmaya baslar. Ev yemeklerinde yazin taze fasulye, kisin pirasa
pisirilir. Bunlarin hepsi ayni kavram: MENU, o donemde satilan urunlerin
listesi.

  - Hicbir menude olmayan urun her zaman satilir (kulah, pet su, cay).
  - Bir menude olan urun ancak o menu gecerliyken acik kalir.
  - Malzemeler menuye yazilmaz; kendiliginden izler. Sadece kapanan urunlerin
    recetesinde gecen malzeme (kavun aromasi) urunle birlikte kapanir, acik
    bir urunde de gecen malzeme (sut) acik kalir.

Gecisi program yapmaz, onerir. Her menunun bir kosulu olabilir: "hava
soguyunca" ya da "hava isininca", bir de esik derecesi. Hava tahmininde bu
kosul GUN_ARDISIK gun ust uste tutarsa ana menude bir gecis plani cikar:
hangi gun, neden, kapanacak urunlerden elde ne kaldigi, "artik uretme"
uyarisi, acilacak urunler icin ne alinmasi gerektigi. Hesabin hepsi dukkanin
kendi kayitlarindan (hava, satis, stok, alis fiyati) yapilir; disariya
sorulmaz, para tutmaz.
"""

import datetime

import hesap
from veritabani import ayar, ayar_yaz

GUN_ARDISIK = 3      # kosul bu kadar gun ust uste tutarsa gecis onerilir
GERI_GUN = 2         # dunku, onceki gunku gerceklesen hava da sayilir
ILERI_GUN = 7        # hava tahmininin kapsadigi gun
ERTELE_GUN = 3       # "simdi degil" denince bu kadar gun tekrar sorulmaz
ILK_HAFTA = 7        # acilacak urunler icin kac gunluk malzeme onerilir
FIYAT_GUN = 21       # alis fiyati: son uc hafta ile ondan onceki dort hafta
FIYAT_ESIGI = 0.20   # bundan fazla artan malzeme uyarilir
EN_AZ_GECMIS = 3     # "gecmiste bu sicaklikta" demek icin gereken gun

KOSULLAR = [
    ("", "Kendim geçerim, öneri istemem"),
    ("soguk", "Hava soğuyunca öner"),
    ("sicak", "Hava ısınınca öner"),
]


def _bugun():
    return datetime.date.today()


def _simdi():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------- okuma

def liste(baglanti):
    return baglanti.execute("SELECT * FROM menuler ORDER BY sira, id").fetchall()


def menu(baglanti, menu_id):
    return baglanti.execute("SELECT * FROM menuler WHERE id = ?", (menu_id,)).fetchone()


def urunleri(baglanti, menu_id):
    """Menudeki urunlerin numaralari."""
    return {satir[0] for satir in baglanti.execute(
        "SELECT kalem_id FROM menu_kalemleri WHERE menu_id = ?", (menu_id,))}


def menulu_urunler(baglanti):
    """Herhangi bir menude gecen urunler: {kalem_id: {menu_id, ...}}"""
    sonuc = {}
    for kalem_id, menu_id in baglanti.execute("SELECT kalem_id, menu_id FROM menu_kalemleri"):
        sonuc.setdefault(kalem_id, set()).add(menu_id)
    return sonuc


def son_gecis(baglanti):
    """En son gecis: {tarih, menu_id, ad} ya da None."""
    return baglanti.execute(
        "SELECT g.tarih, g.menu_id, m.ad FROM menu_gecisleri g"
        " JOIN menuler m ON m.id = g.menu_id ORDER BY g.tarih DESC, g.id DESC LIMIT 1"
    ).fetchone()


def gecerli(baglanti):
    """Su an gecerli menu ya da None (hic gecis yapilmamis)."""
    gecis = son_gecis(baglanti)
    return menu(baglanti, gecis["menu_id"]) if gecis else None


def gecisler(baglanti, adet=6):
    return baglanti.execute(
        "SELECT g.tarih, m.ad FROM menu_gecisleri g JOIN menuler m ON m.id = g.menu_id"
        " ORDER BY g.tarih DESC, g.id DESC LIMIT ?", (adet,)
    ).fetchall()


def secilebilir_urunler(baglanti):
    """Menuye konabilecek urunler: satilan ve elle kapatilmamis olanlar."""
    return baglanti.execute(
        "SELECT * FROM kalemler WHERE satilir = 1 AND (aktif = 1 OR mevsim_disi = 1)"
        " ORDER BY tur, sira, ad"
    ).fetchall()


# ---------------------------------------------------------------- yazma

def _urunleri_yaz(baglanti, menu_id, kalem_idleri):
    baglanti.execute("DELETE FROM menu_kalemleri WHERE menu_id = ?", (menu_id,))
    baglanti.executemany(
        "INSERT OR IGNORE INTO menu_kalemleri (menu_id, kalem_id) VALUES (?, ?)",
        [(menu_id, kalem_id) for kalem_id in kalem_idleri])


def ekle(baglanti, ad, kosul="", esik=0.0, kalem_idleri=()):
    sira = baglanti.execute("SELECT COALESCE(MAX(sira), 0) + 1 FROM menuler").fetchone()[0]
    menu_id = baglanti.execute(
        "INSERT INTO menuler (ad, kosul, esik, sira) VALUES (?, ?, ?, ?)",
        (ad.strip(), kosul, esik, sira)).lastrowid
    _urunleri_yaz(baglanti, menu_id, kalem_idleri)
    baglanti.commit()
    return menu_id


def kaydet(baglanti, menu_id, ad, kosul, esik, kalem_idleri):
    baglanti.execute("UPDATE menuler SET ad = ?, kosul = ?, esik = ? WHERE id = ?",
                     (ad.strip(), kosul, esik, menu_id))
    _urunleri_yaz(baglanti, menu_id, kalem_idleri)
    baglanti.commit()


def sil(baglanti, menu_id):
    """Menuyu siler. Urunler oldugu gibi kalir; kapaliysa kapali kalir."""
    baglanti.execute("DELETE FROM menu_gecisleri WHERE menu_id = ?", (menu_id,))
    baglanti.execute("DELETE FROM menuler WHERE id = ?", (menu_id,))
    baglanti.commit()


def kalemden_cikar(baglanti, kalem_id):
    """Elle kapatilan ya da silinen kalem menulerden de cikar; yoksa bir
    sonraki gecis onu geri acardi."""
    baglanti.execute("DELETE FROM menu_kalemleri WHERE kalem_id = ?", (kalem_id,))
    baglanti.execute("UPDATE kalemler SET mevsim_disi = 0 WHERE id = ?", (kalem_id,))


def _malzemeleri(baglanti, urun_idleri):
    """Urunlerin recetelerinde gecen butun kalemler; ara urunlerin icinden de."""
    goruldu, sira = set(), list(urun_idleri)
    while sira:
        kalem_id = sira.pop()
        for (malzeme_id,) in baglanti.execute(
                "SELECT s.kalem_id FROM recete_satirlari s"
                " JOIN receteler r ON r.id = s.recete_id WHERE r.urun_id = ?", (kalem_id,)):
            if malzeme_id not in goruldu:
                goruldu.add(malzeme_id)
                sira.append(malzeme_id)
    return goruldu


def _kapsam(baglanti, hedef_menu_id):
    """Bir menuye gecilince hangi kalemler acik, hangileri kapali olmali."""
    menulu = menulu_urunler(baglanti)
    hedef = urunleri(baglanti, hedef_menu_id)
    # Hicbir menude olmayan, kullanimdaki urunler hep acik; malzemeleri de.
    sabit = {satir[0] for satir in baglanti.execute(
        "SELECT id FROM kalemler WHERE satilir = 1 AND aktif = 1")} - set(menulu)
    kapanacak = set(menulu) - hedef
    lazim = _malzemeleri(baglanti, hedef | sabit)
    gereksiz = _malzemeleri(baglanti, kapanacak) - lazim - hedef - sabit
    return hedef, lazim, kapanacak | gereksiz


def uygula(baglanti, menu_id):
    """Menunun acik/kapali durumunu kalemlere yazar; gecis kaydi tutmaz.
    Doner: {'acilan': [ad], 'kapanan': [ad]}.

    Kapanan kalem 'mevsim disi' isaretlenir; geri donuste yalnizca bunlar
    acilir. Gecmis kayitlarin hicbiri silinmez.
    """
    hedef, lazim, kapanacak = _kapsam(baglanti, menu_id)

    def adlar(sorgu, idler):
        if not idler:
            return []
        isaret = ",".join("?" * len(idler))
        return [satir[0] for satir in baglanti.execute(
            sorgu.format(isaret=isaret), tuple(idler))]

    kapanan = adlar("SELECT ad FROM kalemler WHERE satilir = 1 AND aktif = 1"
                    " AND id IN ({isaret}) ORDER BY sira, ad", kapanacak)
    acilan = adlar("SELECT ad FROM kalemler WHERE satilir = 1 AND aktif = 0"
                   " AND id IN ({isaret}) ORDER BY sira, ad", hedef)

    for kalem_id in kapanacak:
        baglanti.execute("UPDATE kalemler SET aktif = 0, mevsim_disi = 1"
                         " WHERE id = ? AND aktif = 1", (kalem_id,))
    for kalem_id in hedef:
        baglanti.execute("UPDATE kalemler SET aktif = 1, mevsim_disi = 0 WHERE id = ?",
                         (kalem_id,))
    for kalem_id in lazim:
        baglanti.execute("UPDATE kalemler SET aktif = 1, mevsim_disi = 0"
                         " WHERE id = ? AND mevsim_disi = 1", (kalem_id,))
    return {"acilan": acilan, "kapanan": kapanan}


def gec(baglanti, menu_id, tarih=None):
    """Menuye gecer ve gecisi tarihiyle kaydeder."""
    tarih = tarih or _bugun().isoformat()
    sonuc = uygula(baglanti, menu_id)
    baglanti.execute(
        "INSERT INTO menu_gecisleri (tarih, menu_id, kayit_zamani) VALUES (?, ?, ?)",
        (tarih, menu_id, _simdi()))
    ayar_yaz(baglanti, "menu_oneri_ertele", "")
    baglanti.commit()
    return sonuc


def ertele(baglanti, menu_id, gun=ERTELE_GUN):
    """"Simdi degil": bu menunun onerisi birkac gun sorulmaz."""
    son = (_bugun() + datetime.timedelta(days=gun)).isoformat()
    ayar_yaz(baglanti, "menu_oneri_ertele", f"{menu_id}:{son}")
    baglanti.commit()


def _ertelendi_mi(baglanti, menu_id, bugun):
    deger = ayar(baglanti, "menu_oneri_ertele", "")
    if ":" not in deger:
        return False
    kimlik, son = deger.split(":", 1)
    return kimlik == str(menu_id) and bugun.isoformat() <= son


# ---------------------------------------------------------------- oneri

def _uyar_mi(kosul, esik, sicaklik):
    return sicaklik < esik if kosul == "soguk" else sicaklik > esik


def _hava_gunleri(baglanti, bugun):
    """Dunden once iki gun (gerceklesen) + bugunden itibaren tahmin."""
    bas = (bugun - datetime.timedelta(days=GERI_GUN)).isoformat()
    son = (bugun + datetime.timedelta(days=ILERI_GUN - 1)).isoformat()
    return [
        (datetime.date.fromisoformat(satir["tarih"]), satir["en_yuksek"])
        for satir in baglanti.execute(
            "SELECT tarih, en_yuksek FROM hava WHERE tarih BETWEEN ? AND ?"
            " AND en_yuksek IS NOT NULL ORDER BY tarih", (bas, son))
    ]


def _kosul_baslangici(gunler, kosul, esik):
    """Kosulun GUN_ARDISIK gun ust uste tuttugu ilk dizinin ilk gunu."""
    for sira in range(len(gunler) - GUN_ARDISIK + 1):
        dizi = gunler[sira:sira + GUN_ARDISIK]
        ardisik = all((dizi[i + 1][0] - dizi[i][0]).days == 1 for i in range(len(dizi) - 1))
        if ardisik and all(_uyar_mi(kosul, esik, derece) for _, derece in dizi):
            return dizi
    return None


def oneri(baglanti, bugun=None):
    """Hava tahminine gore gecis onerisi; yoksa None.

    Birden fazla menunun kosulu tutuyorsa en erken baslayani onerilir.
    """
    bugun = bugun or _bugun()
    simdiki = gecerli(baglanti)
    gunler = _hava_gunleri(baglanti, bugun)
    adaylar = []
    for m in liste(baglanti):
        if not m["kosul"] or (simdiki and m["id"] == simdiki["id"]):
            continue
        if not urunleri(baglanti, m["id"]) or _ertelendi_mi(baglanti, m["id"], bugun):
            continue
        dizi = _kosul_baslangici(gunler, m["kosul"], m["esik"])
        if dizi:
            adaylar.append((max(dizi[0][0], bugun), m, dizi))
    if not adaylar:
        return None
    tarih, hedef, dizi = min(adaylar, key=lambda aday: aday[0])
    return gecis_plani(baglanti, hedef, tarih, dizi, bugun)


def _gecmiste_bu_havada(baglanti, kalem_id, kosul, esik):
    """Dukkanin acik oldugu gunlerde, esigin otesindeki havada gunluk satis.

    Doner: (gun sayisi, o gunlerde gunluk ortalama, butun gunlerde ortalama).
    """
    satirlar = baglanti.execute(
        "SELECT h.en_yuksek, (SELECT COALESCE(SUM(s.miktar), 0) FROM satislar s"
        "  WHERE s.kalem_id = ? AND s.tarih = h.tarih) AS miktar"
        " FROM hava h WHERE h.tahmin = 0 AND h.en_yuksek IS NOT NULL"
        " AND h.tarih IN (SELECT DISTINCT tarih FROM satislar)", (kalem_id,)
    ).fetchall()
    if not satirlar:
        return 0, 0.0, 0.0
    otesi = [s["miktar"] for s in satirlar if _uyar_mi(kosul, esik, s["en_yuksek"])]
    genel = sum(s["miktar"] for s in satirlar) / len(satirlar)
    return len(otesi), (sum(otesi) / len(otesi) if otesi else 0.0), genel


def _gunluk_satis(baglanti, kalem_id, gun=60):
    """Satildigi gunlerde gunluk ortalama (son 'gun' satis gunu)."""
    satir = baglanti.execute(
        "SELECT COUNT(*), COALESCE(SUM(m), 0) FROM (SELECT SUM(miktar) AS m FROM satislar"
        " WHERE kalem_id = ? GROUP BY tarih ORDER BY tarih DESC LIMIT ?)",
        (kalem_id, gun)).fetchone()
    return satir[1] / satir[0] if satir[0] else None


def _malzeme_ihtiyaci(baglanti, kalem_id, miktar, sonuc, _zincir=()):
    """Bir urunun 'miktar' kadarinin satin alinan malzeme karsiligi."""
    if kalem_id in _zincir:
        return
    recete = hesap.ana_recete(baglanti, kalem_id)
    if recete is None:
        return
    oran = miktar / (recete["verim"] or 1)
    for satir in hesap.recete_satirlari(baglanti, recete["id"]):
        malzeme = hesap.kalem(baglanti, satir["kalem_id"])
        if malzeme is None:
            continue
        gereken = satir["miktar"] * oran
        if malzeme["alinir"]:
            sonuc[malzeme["id"]] = sonuc.get(malzeme["id"], 0.0) + gereken
        elif malzeme["uretilir"]:
            _malzeme_ihtiyaci(baglanti, malzeme["id"], gereken, sonuc,
                              _zincir + (kalem_id,))


def gecis_plani(baglanti, hedef, tarih, dizi, bugun=None):
    """Bir menuye gecisin plani: neden, kapanan/acilan urunler, alinacaklar."""
    bugun = bugun or _bugun()
    kalan_gun = max(0, (tarih - bugun).days)
    stok = hesap.stoklar(baglanti)
    urunler_hedef = urunleri(baglanti, hedef["id"])
    menulu = menulu_urunler(baglanti)

    kapananlar = []
    for kalem in baglanti.execute(
            "SELECT * FROM kalemler WHERE satilir = 1 AND aktif = 1 ORDER BY sira, ad"):
        if kalem["id"] not in menulu or kalem["id"] in urunler_hedef:
            continue
        elde = stok.get(kalem["id"], 0.0) if kalem["takip"] else 0.0
        gunluk = hesap.gunluk_tuketim(baglanti, kalem["id"], 14) if kalem["takip"] else 0.0
        gecmis_gun, gecmis_ort, genel_ort = _gecmiste_bu_havada(
            baglanti, kalem["id"], hedef["kosul"], hedef["esik"])
        kapananlar.append({
            "kalem": kalem,
            "elde": elde,
            "gunluk": gunluk,
            "biter": (elde / gunluk) if gunluk > 0 else None,
            # Gecis gunune kadar satilamayip elde kalacak olan.
            "artacak": max(0.0, elde - gunluk * kalan_gun) if elde > 0 else 0.0,
            "uretme": bool(kalem["uretilir"]),
            "gecmis_gun": gecmis_gun,
            "gecmis_ort": gecmis_ort,
            "genel_ort": genel_ort,
        })

    acilanlar, ihtiyac, tahminsiz = [], {}, []
    for kalem in baglanti.execute(
            "SELECT * FROM kalemler WHERE satilir = 1 AND aktif = 0 AND mevsim_disi = 1"
            " ORDER BY sira, ad"):
        if kalem["id"] not in urunler_hedef:
            continue
        gunluk = _gunluk_satis(baglanti, kalem["id"])
        acilanlar.append({"kalem": kalem, "gunluk": gunluk})
        if gunluk:
            _malzeme_ihtiyaci(baglanti, kalem["id"], gunluk * ILK_HAFTA, ihtiyac)
        else:
            tahminsiz.append(kalem["id"])

    # Gecmisi olmayan (ilk kez acilan) urunlerin malzemesinden stokta hic
    # olmayanlar: miktar bilinmese de "bunu almadan gecme" denebilir.
    bos_malzemeler = set()
    for kalem_id in tahminsiz:
        yerine = {}
        _malzeme_ihtiyaci(baglanti, kalem_id, 1, yerine)
        bos_malzemeler |= {m for m in yerine if stok.get(m, 0.0) <= 0}

    alinacaklar = []
    for malzeme_id, gereken in sorted(ihtiyac.items()):
        malzeme = hesap.kalem(baglanti, malzeme_id)
        elde = stok.get(malzeme_id, 0.0)
        if malzeme is None or not malzeme["takip"] or elde >= gereken:
            continue
        alinacaklar.append({"kalem": malzeme, "gereken": gereken, "elde": elde,
                            "eksik": gereken - elde})
    for malzeme_id in sorted(bos_malzemeler - set(ihtiyac)):
        malzeme = hesap.kalem(baglanti, malzeme_id)
        if malzeme is not None and malzeme["takip"]:
            alinacaklar.append({"kalem": malzeme, "gereken": None, "elde": 0.0,
                                "eksik": None})

    return {
        "menu": hedef,
        "tarih": tarih,
        "kalan_gun": kalan_gun,
        "dizi": dizi,
        "kapananlar": kapananlar,
        "acilanlar": acilanlar,
        "alinacaklar": alinacaklar,
        "fiyat_uyarilari": fiyat_uyarilari(baglanti, [k["kalem"]["id"] for k in kapananlar],
                                           bugun),
    }


def fiyat_uyarilari(baglanti, urun_idleri, bugun=None):
    """Urunlerin malzemesinden son uc haftada alis fiyati belirgin artanlar.

    Ev yemeginde "domates pahalandi" sinyali: mevsimi gecen sebzenin fiyati
    tirmanir. Son FIYAT_GUN gunun ortalama alis fiyati, ondan onceki dort
    haftanin ortalamasiyla karsilastirilir.
    """
    bugun = bugun or _bugun()
    yeni_bas = (bugun - datetime.timedelta(days=FIYAT_GUN)).isoformat()
    eski_bas = (bugun - datetime.timedelta(days=FIYAT_GUN + 28)).isoformat()
    kullanan = {}
    for urun_id in urun_idleri:
        for malzeme_id in _malzemeleri(baglanti, [urun_id]):
            kullanan.setdefault(malzeme_id, set()).add(urun_id)

    uyarilar = []
    for malzeme_id, urunler in kullanan.items():
        satir = baglanti.execute(
            "SELECT SUM(CASE WHEN tarih >= ? THEN tutar END) / SUM(CASE WHEN tarih >= ?"
            " THEN miktar END) AS yeni, SUM(CASE WHEN tarih < ? THEN tutar END) /"
            " SUM(CASE WHEN tarih < ? THEN miktar END) AS eski FROM alimlar"
            " WHERE kalem_id = ? AND tarih >= ? AND tarih <= ?",
            (yeni_bas, yeni_bas, yeni_bas, yeni_bas, malzeme_id, eski_bas,
             bugun.isoformat())).fetchone()
        if not satir["yeni"] or not satir["eski"]:
            continue
        artis = satir["yeni"] / satir["eski"] - 1
        if artis >= FIYAT_ESIGI:
            malzeme = hesap.kalem(baglanti, malzeme_id)
            adlar = [hesap.kalem(baglanti, u)["ad"] for u in sorted(urunler)]
            uyarilar.append({"kalem": malzeme, "eski": satir["eski"], "yeni": satir["yeni"],
                             "artis": artis, "urunler": adlar})
    uyarilar.sort(key=lambda u: -u["artis"])
    return uyarilar


def uretilmeyecekler(plan):
    """Gecis yaklasirken 'uret' denmemesi gereken kalemler: kapanacak urunler."""
    if not plan:
        return set()
    return {k["kalem"]["id"] for k in plan["kapananlar"] if k["uretme"]}
