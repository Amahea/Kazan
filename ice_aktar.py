# -*- coding: utf-8 -*-
"""Yerelde uretilmis bir dukkan veri dosyasini (dukkan-N.db) sunucuya GUVENLE ekler.

Neden duz kopyalama degil: her dukkanin dosya adi bir NUMARAYLA baglidir ve bu
numara kullanici defterindeki (kullanicilar.db) kayitla eslesmek zorundadir.
Sunucuda zaten baska dukkanlar olabilir; dosyayi ayni numarayla kopyalamak
oradaki dukkani EZER. Bu betik bunun yerine BOS bir numara bulur, dosyayi o
numarayla koyar ve deftere kaydeder - var olan hicbir dukkana dokunmaz.

Kullanim (sunucuda, ~/Kazan icinde):
    python3 ice_aktar.py <db_dosyasi> ["Dukkan Adi"] [kullanici_adi] [sifre]

  - db_dosyasi : yuklenen yerel dosya (orn. ~/dukkan-5.db)
  - Dukkan Adi : verilmezse dosyanin icindeki addan okunur
  - kullanici + sifre verilirse o dukkana bir GIRIS hesabi da acilir; verilmezse
    dukkan yalnizca YONETICI panelinde gorunur (ayri giris olmadan).
"""
import os
import shutil
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hesaplar
import veritabani
from veritabani import ayar, ayar_yaz


def _bos_numara(defter):
    """Hem defterdeki kayitlari hem klasordeki dosyalari asan ilk bos numara."""
    idler = set(hesaplar.dukkan_kimlikleri(defter))
    klasor = veritabani.DUKKAN_KLASORU
    if os.path.isdir(klasor):
        for ad in os.listdir(klasor):
            if ad.startswith("dukkan-") and ad.endswith(".db"):
                try:
                    idler.add(int(ad[len("dukkan-"):-3]))
                except ValueError:
                    pass
    return (max(idler) + 1) if idler else 1


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    kaynak = sys.argv[1]
    ad = sys.argv[2] if len(sys.argv) > 2 else ""
    kullanici = sys.argv[3] if len(sys.argv) > 3 else ""
    sifre = sys.argv[4] if len(sys.argv) > 4 else ""

    if not os.path.exists(kaynak):
        print("Dosya bulunamadi:", kaynak)
        return
    # Gercekten bir dukkan veri dosyasi mi (yanlis dosya kopyalanmasin).
    try:
        test = sqlite3.connect(kaynak)
        test.execute("SELECT 1 FROM satislar LIMIT 1")
        test.close()
    except sqlite3.Error as e:
        print("Bu bir dukkan veri dosyasi gibi gorunmuyor:", e)
        return

    defter = hesaplar.hazirla()
    try:
        yeni = _bos_numara(defter)
        hedef = veritabani.db_yolu(yeni)
        os.makedirs(veritabani.DUKKAN_KLASORU, exist_ok=True)
        shutil.copy2(kaynak, hedef)

        b = veritabani.hazirla(yeni)        # yeni surumun semasina goc
        try:
            if not ad:
                ad = ayar(b, "dukkan_adi", "") or f"Dükkan {yeni}"
            ayar_yaz(b, "dukkan_adi", ad)
            b.commit()
        finally:
            b.close()

        hesaplar.dukkan_saglama(defter, yeni, ad)
        print(f"Eklendi: #{yeni}  {ad}  ({os.path.basename(hedef)})")

        if kullanici and sifre:
            hata = hesaplar.kayit_denetle(defter, kullanici, sifre)
            if hata:
                print("  (giris hesabi acilmadi:", hata, ")")
            else:
                hesaplar.kullanici_ekle(defter, yeni, kullanici, "", sifre)
                print(f"  giris hesabi: {kullanici}")
        else:
            print("  (giris hesabi acilmadi; dukkan yonetici panelinde gorunur)")
    finally:
        defter.close()


if __name__ == "__main__":
    main()
