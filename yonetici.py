# -*- coding: utf-8 -*-
"""Yonetici panelinin veri tarafi: butun dukkanlari capraz okur.

Normal akista her istek TEK dukkanin dosyasini acar; bir dukkan sahibi
baskasinin verisini goremez. Yonetici ise (bu bir TUBITAK calismasi oldugu,
onam formu da bunu kapsadigi icin) butun dukkanlari gorur. Bu modul, kullanici
defterini (hesaplar) ve her dukkanin kendi dosyasini (veritabani) birlikte
gezip ozet cikarir. Hicbir sey yazmaz; yalnizca okur ve toplar.

Tasarim: uygulama.py yalnizca bu fonksiyonlarin dondurdugu sozlukleri ekrana
cizer; butun capraz-okuma mantigi burada toplanir.
"""

import datetime
import os

import hesap
import hesaplar
import tahmin
import veritabani


def _varsa(dukkan_id):
    """Dukkanin veri dosyasi diskte var mi."""
    return os.path.exists(veritabani.db_yolu(dukkan_id))

# "Veri girilmedi" uyarisinin esikleri (gun). Son gun sonu sayiminin uzerinden
# bu kadar gun gectiyse dukkan once 'uyari', sonra 'kritik' sayilir.
UYARI_GUN = 2
KRITIK_GUN = 4
ANOMALI_PENCERE_GUN = 14   # model sagliginda "son kac gunun anomalisi" sayilir


def _bugun():
    return datetime.date.today()


def _gun_farki(tarih_metni):
    """Bugun ile verilen tarih (YYYY-AA-GG) arasindaki gun sayisi; yoksa None."""
    if not tarih_metni:
        return None
    try:
        t = datetime.datetime.strptime(tarih_metni[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    return (_bugun() - t).days


def _durum(gun_gecti):
    """Son veri girisinin uzerinden gecen gune gore durum etiketi."""
    if gun_gecti is None:
        return "veri_yok"
    if gun_gecti >= KRITIK_GUN:
        return "kritik"
    if gun_gecti >= UYARI_GUN:
        return "uyari"
    return "iyi"


def dukkan_durumlari(defter):
    """Her dukkanin veri-giris saglik durumu + kullanicilari.

    Doner: dukkan basina sozluk listesi:
      {id, ad, son_sayim, gun_gecti, durum, kullanicilar:[{ad,eposta,rol,son_giris}],
       son_giris (en yeni), acik (dukkan dosyasi var mi)}
    """
    # Kullanicilari dukkana gore grupla (tek sorgu).
    kullanicilar = {}
    for k in hesaplar.tum_kullanicilar(defter):
        kullanicilar.setdefault(k["dukkan_id"], []).append(k)

    sonuc = []
    for d in defter.execute("SELECT id, ad FROM dukkanlar ORDER BY id"):
        kisiler = kullanicilar.get(d["id"], [])
        # Son veri girisi = gun sonu sayimi VEYA dogrudan satis (hangisi daha
        # yeniyse). Bazi dukkanlar sayim yapar, bazilari satisi dogrudan girer.
        son_veri = None
        if _varsa(d["id"]):
            b = veritabani.baglan(d["id"])
            try:
                tarihler = []
                for tablo in ("satislar", "sayimlar"):
                    try:
                        r = b.execute(f"SELECT MAX(tarih) t FROM {tablo}").fetchone()
                        if r and r["t"]:
                            tarihler.append(r["t"])
                    except Exception:
                        pass
                son_veri = max(tarihler) if tarihler else None
            finally:
                b.close()
        gun_gecti = _gun_farki(son_veri)
        son_girisler = [k["son_giris"] for k in kisiler if k["son_giris"]]
        sonuc.append({
            "id": d["id"], "ad": d["ad"],
            "son_veri": son_veri, "gun_gecti": gun_gecti,
            "durum": _durum(gun_gecti),
            "kullanicilar": kisiler,
            "son_giris": max(son_girisler) if son_girisler else None,
            "acik": _varsa(d["id"]),
        })
    return sonuc


def uyari_sayisi(durumlar):
    """Dikkat gereken dukkan sayisi (uyari + kritik + veri_yok). Menu rozeti."""
    return sum(1 for d in durumlar if d["durum"] in ("uyari", "kritik", "veri_yok"))


def _fire_tl(b):
    """Bir dukkanda toplam fire (sayim farki eksikleri) TL cinsinden.

    Sayim farki negatifleri kalem bazinda toplanip birim maliyetle carpilir
    (birim_maliyet uretilen kalemlerde uretim ortalamasi, alinanilarda son alis).
    """
    toplam = 0.0
    for r in b.execute(
        "SELECT kalem_id, SUM(-miktar) AS m FROM stok_hareketleri"
        " WHERE (sebep = 'Sayım farkı' OR sebep LIKE 'Fire%') AND miktar < 0"
        " GROUP BY kalem_id"
    ):
        if r["m"] and r["m"] > 0:
            toplam += r["m"] * hesap.birim_maliyet(b, r["kalem_id"])
    return toplam


def capraz_ozet(defter, son_gun=30):
    """Butun dukkanlar icin ciro/kar/fire ozeti (hem tum zaman hem son N gun).

    Doner: liste [{id, ad, gun, ciro, cogs, brut, gider, net, fire, ciro_son}]
    ve toplamlar sozlugu.
    """
    esik = (_bugun() - datetime.timedelta(days=son_gun)).strftime("%Y-%m-%d")
    satirlar = []
    for d in defter.execute("SELECT id, ad FROM dukkanlar ORDER BY id"):
        if not _varsa(d["id"]):
            continue
        b = veritabani.baglan(d["id"])
        try:
            s = b.execute(
                "SELECT COALESCE(SUM(tutar),0) ciro, COALESCE(SUM(maliyet),0) cogs,"
                " COUNT(DISTINCT tarih) gun FROM satislar").fetchone()
            g = b.execute("SELECT COALESCE(SUM(tutar),0) t FROM giderler").fetchone()
            cs = b.execute(
                "SELECT COALESCE(SUM(tutar),0) t FROM satislar WHERE tarih >= ?",
                (esik,)).fetchone()
            brut = s["ciro"] - s["cogs"]
            satirlar.append({
                "id": d["id"], "ad": d["ad"], "gun": s["gun"],
                "ciro": s["ciro"], "cogs": s["cogs"], "brut": brut,
                "gider": g["t"], "net": brut - g["t"],
                "fire": _fire_tl(b), "ciro_son": cs["t"],
            })
        finally:
            b.close()
    toplam = {alan: sum(r[alan] for r in satirlar)
              for alan in ("ciro", "cogs", "brut", "gider", "net", "fire", "ciro_son")}
    return satirlar, toplam


def _anomali_sayisi(b):
    """Son ANOMALI_PENCERE_GUN gunde istatistiksel fire anomalisi sayisi."""
    esik = (_bugun() - datetime.timedelta(days=ANOMALI_PENCERE_GUN)).strftime("%Y-%m-%d")
    adet = 0
    for r in b.execute(
        "SELECT tarih, kalem_id, SUM(-miktar) AS fire FROM stok_hareketleri"
        " WHERE sebep = 'Sayım farkı' AND miktar < 0 AND tarih >= ?"
        " GROUP BY tarih, kalem_id", (esik,)
    ):
        if r["fire"] and tahmin.fire_anomalisi(b, r["kalem_id"], r["tarih"], r["fire"]):
            adet += 1
    return adet


def model_sagligi(defter):
    """Her dukkanda tahmin modelinin durumu: yeterli mi, kac gun, MAPE, secim.

    MAPE, modelin ortalama hatasinin (hata_payi) ortalama ciroya oranidir -
    ucuz ve kaba ama panelde dukkanlari kiyaslamaya yeter (kesin kiyas
    /tahmin-gunlugu'nde). Anomali: son 14 gunun istatistiksel fire sayisi.
    """
    sonuc = []
    for d in defter.execute("SELECT id, ad FROM dukkanlar ORDER BY id"):
        if not _varsa(d["id"]):
            sonuc.append({"id": d["id"], "ad": d["ad"], "yeterli": False,
                          "gun": 0, "mape": None, "secim": None, "anomali": 0})
            continue
        b = veritabani.baglan(d["id"])
        try:
            m = tahmin.model_kur(b)
            mape = (100.0 * m["hata_payi"] / m["ortalama"]
                    if m["yeterli"] and m["ortalama"] else None)
            sonuc.append({
                "id": d["id"], "ad": d["ad"], "yeterli": m["yeterli"],
                "gun": m["gun_sayisi"], "mape": mape,
                "secim": m.get("secim"), "eksik_gun": m.get("eksik_gun", 0),
                "anomali": _anomali_sayisi(b) if m["yeterli"] else 0,
            })
        finally:
            b.close()
    return sonuc


def arastirma_csv(defter, dukkan_idleri):
    """Secili dukkanlarin gunluk ciro + hava verisini CSV metni olarak doner.

    Sutunlar: dukkan, tarih, ciro, satis_adedi, en_yuksek_sicaklik, yagis_mm.
    TUBITAK analizi icin ham, anonimlestirilebilir gunluk veri.
    """
    basliklar = ["dukkan", "tarih", "ciro", "satis_adedi", "en_yuksek_sicaklik", "yagis_mm"]
    satirlar = [";".join(basliklar)]
    idler = {int(x) for x in dukkan_idleri}
    for d in defter.execute("SELECT id, ad FROM dukkanlar ORDER BY id"):
        if d["id"] not in idler or not _varsa(d["id"]):
            continue
        b = veritabani.baglan(d["id"])
        try:
            gunler = {}
            for r in b.execute(
                "SELECT tarih, SUM(tutar) ciro, SUM(miktar) adet FROM satislar"
                " GROUP BY tarih"):
                gunler[r["tarih"]] = [r["ciro"], r["adet"]]
            hava = {}
            try:
                for r in b.execute(
                    "SELECT tarih, en_yuksek, yagis FROM hava"):
                    hava[r["tarih"]] = (r["en_yuksek"], r["yagis"])
            except Exception:
                pass
            for tarih in sorted(gunler):
                ciro, adet = gunler[tarih]
                sic, yagis = hava.get(tarih, (None, None))
                hucre = [d["ad"], tarih, f"{ciro:.2f}", f"{adet:.3f}",
                         "" if sic is None else f"{sic:.1f}",
                         "" if yagis is None else f"{yagis:.1f}"]
                satirlar.append(";".join(_csv_guvenli(x) for x in hucre))
        finally:
            b.close()
    return "\n".join(satirlar) + "\n"


def _csv_guvenli(deger):
    """Noktali virgul/tirnak/yeni satir iceren hucreyi tirnakla sarar."""
    s = str(deger)
    if any(c in s for c in ';"\n\r'):
        return '"' + s.replace('"', '""') + '"'
    return s
