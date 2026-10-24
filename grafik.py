# -*- coding: utf-8 -*-
"""Rapor grafikleri.

Disaridan hicbir kutuphane kullanilmiyor: grafikler duz HTML kutulari, boylari
ve genislikleri yuzdeyle veriliyor. SVG yerine HTML secildi cunku SVG olcege
gore buyuyunce yazilar da buyuyup kuculuyor; burada yazilar sayfanin normal
yazisi, telefonda da okunakli kaliyor. JavaScript de yok.

Renkler dataviz olcutlerine gore secildi ve renk korlugu testinden gecirildi:
mavi ile yesil, mavi ile turuncu ve turuncu ile yesil, protanopi ve deuteranopi
benzetimi altinda ayirt edilebilir uzaklikta (OKLab dE >= 8).
"""
import html

MAVI = "#1a6ca5"        # ciro, urun kari, secili donem
MAVI_SOLUK = "#83b1d3"  # gecmis donemler - ayni rengin acik kademesi
TURUNCU = "#e07b00"     # giderler
YESIL = "#1b7f4f"       # net kar
KIRMIZI = "#c1392b"     # zarar

# Bir parcanin icine yuzde yazisi ancak bu genislikten sonra sigar; altinda
# yazi kirpilacagi icin hic yazilmiyor, deger zaten altta anahtar satirinda var.
IC_ETIKET_ESIGI = 15.0


def _k(metin):
    return html.escape(str(metin), quote=True)


def _isik(renk):
    """WCAG bagil parlaklik."""
    kanallar = []
    for i in (1, 3, 5):
        c = int(renk[i:i + 2], 16) / 255
        kanallar.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * kanallar[0] + 0.7152 * kanallar[1] + 0.0722 * kanallar[2]


def _kontrast(a, b):
    ust, alt = sorted((_isik(a), _isik(b)), reverse=True)
    return (ust + 0.05) / (alt + 0.05)


def ic_yazi_rengi(zemin):
    """Renkli bir dolgunun icine yazilacak yazinin rengi.

    Beyaz mi koyu mu daha okunakliysa o secilir; ikisi de 4.5:1'i gecemiyorsa
    None doner ve o parcaya hic yazi konmaz (kirpik ya da soluk yazi yerine
    hic yazi yok - deger zaten anahtar satirinda yaziyor).
    """
    adaylar = [("#ffffff", _kontrast(zemin, "#ffffff")),
               ("#1c2733", _kontrast(zemin, "#1c2733"))]
    renk, oran = max(adaylar, key=lambda ikili: ikili[1])
    return renk if oran >= 4.5 else None


def oran(deger, toplam):
    """Bir degerin toplam icindeki yuzdesi; eksi degerler sifir sayilir."""
    return 0.0 if not toplam else max(0.0, deger) / toplam * 100


def bos(metin="Grafik için henüz yeterli kayıt yok."):
    return f'<p class="bos">{_k(metin)}</p>'


def yigilmis_serit(parcalar, aria, isaret=None):
    """Bir butunun neye bolundugunu gosteren yatay serit.

    parcalar: (ad, deger_metni, oran_yuzde, renk) dizisi.
    isaret: (oran_yuzde, etiket) - seridin uzerine dikey bir cizgi koyar;
            giderler cironun ustune ciktiginda cironun nerede kaldigini gosterir.
    """
    parcalar = [p for p in parcalar if p[2] > 0]
    if not parcalar:
        return bos()

    dilimler = ""
    for ad, deger, oran, renk in parcalar:
        # Yuzde yazisi ancak rahat sigacaksa parcanin icine giriyor.
        yazi = ic_yazi_rengi(renk)
        ic = (f'<span class="serit-ic" style="color:{yazi}">%{oran:.0f}</span>'
              if oran >= IC_ETIKET_ESIGI and yazi else "")
        dilimler += (f'<span class="serit-parca" style="flex:{oran:.4f} 1 0;'
                     f'background:{renk}" title="{_k(ad)} — {_k(deger)}'
                     f' (%{oran:.0f})">{ic}</span>')

    isaret_html = ""
    if isaret:
        yer, etiket = isaret
        isaret_html = (f'<span class="serit-isaret" style="left:{min(yer, 100):.4f}%"'
                       f' title="{_k(etiket)}"></span>')

    anahtar = "".join(
        f'<li><span class="anahtar-nokta" style="background:{renk}"></span>'
        f'{_k(ad)}<b>{_k(deger)}</b></li>'
        for ad, deger, oran, renk in parcalar
    )
    return (f'<div class="serit" role="img" aria-label="{_k(aria)}">{dilimler}'
            f'{isaret_html}</div><ul class="anahtar">{anahtar}</ul>')


def cubuk_listesi(satirlar, renk, aria):
    """Sirali yatay cubuklar: ad ustte, degeri saginda, cubuk altinda.

    satirlar: (ad, deger_metni, oran_yuzde, ipucu) dizisi. Tek bir olcu
    gosterildigi icin butun cubuklar ayni renk - uzunluk zaten buyuklugu
    anlatiyor, rengi de buna baglamak ayni bilgiyi iki kere soylemek olur.
    """
    if not satirlar:
        return bos()
    govde = ""
    for ad, deger, oran, ipucu in satirlar:
        govde += (
            f'<div class="cubuk-satir" title="{_k(ipucu)}">'
            f'<div class="cubuk-ust"><span>{_k(ad)}</span><b>{_k(deger)}</b></div>'
            f'<div class="cubuk-yol"><span class="cubuk-dolgu"'
            f' style="width:{max(oran, 0.6):.4f}%; background:{renk}"></span></div>'
            f'</div>')
    return f'<div class="cubuklar" role="img" aria-label="{_k(aria)}">{govde}</div>'


def sutun_grafigi(noktalar, tavan_metni, aria, altyazi=""):
    """Zaman icinde gidisati gosteren dikey sutunlar; eskiden yeniye soldan saga.

    noktalar: (etiket, oran_yuzde, secili_mi, adres, ipucu) dizisi.
    Etiketi bos birakilan sutunun altina yazi yazilmaz; sutun sikisinca
    yazilar ust uste binmesin diye bir kismi bosaltilir.
    """
    if not noktalar:
        return bos()
    sutunlar, etiketler = "", ""
    for etiket, yuzde, secili, adres, ipucu in noktalar:
        renk = MAVI if secili else MAVI_SOLUK
        # Sifira yakin donem de gorunsun diye en az bir tirnak boy veriliyor.
        boy = max(yuzde, 1.2)
        # Baglanti sutunun tamami: kisa bir cubuga nisan almak gerekmiyor.
        sutunlar += (f'<a class="sutun" href="{_k(adres)}" title="{_k(ipucu)}">'
                     f'<span class="sutun-cubuk" style="height:{boy:.4f}%;'
                     f'background:{renk}"></span></a>')
        sinif = ' class="secili"' if secili else ""
        etiketler += f"<span{sinif}>{_k(etiket)}</span>"
    alt = f'<p class="grafik-alt">{_k(altyazi)}</p>' if altyazi else ""
    return (f'<div class="sutun-grafik" role="img" aria-label="{_k(aria)}">'
            f'<div class="sutun-tavan"><span>{_k(tavan_metni)}</span></div>'
            f'<div class="sutun-sira">{sutunlar}</div>'
            f'<div class="sutun-etiketler">{etiketler}</div></div>{alt}')


def etiket_seyrelt(etiketler, en_fazla=10):
    """Cok sayida sutun varken alt yazilari birbirine girmesin diye seyreltir.

    Sondaki (en yeni) donem her zaman yazili kalir; geriye dogru esit araliklarla
    secilir, aradakiler bos birakilir.
    """
    adet = len(etiketler)
    if adet <= en_fazla:
        return list(etiketler)
    adim = -(-adet // en_fazla)          # yukari yuvarlanmis bolme
    return [e if (adet - 1 - i) % adim == 0 else "" for i, e in enumerate(etiketler)]


def kisa_para(deger, para_birimi="TL"):
    """Eksen ucundaki sayi kisa olsun: 1.058.170 -> '1,06 mn TL'."""
    deger = float(deger or 0)
    if abs(deger) >= 1_000_000:
        sayi, ek = deger / 1_000_000, " mn"
    elif abs(deger) >= 1_000:
        sayi, ek = deger / 1_000, " bin"
    else:
        sayi, ek = deger, ""
    metin = f"{sayi:,.1f}".replace(",", "#").replace(".", ",").replace("#", ".")
    if metin.endswith(",0"):
        metin = metin[:-2]
    return f"{metin}{ek} {para_birimi}".strip()


def cizgi_grafigi(seriler, x_etiketler, tavan, tavan_metni, aria, altyazi=""):
    """Gun sayisina karsi hata egrisi gibi cizgiler. SVG, acik temaya gore.

    seriler: [{"ad":..., "renk":..., "degerler":[y,...]}]; hepsi ayni x
    noktalarini paylasir. tavan: y ekseninin tepesi (0..tavan). x_etiketler
    noktalarin altina yazilir (seyreltilir). Grafik goz icindir; kesin
    rakamlar yanindaki tabloda durur.
    """
    uzun = max((len(s["degerler"]) for s in seriler), default=0)
    if uzun < 2 or tavan <= 0:
        return bos()
    W, H = 100.0, 60.0

    def nokta_dizi(degerler):
        n = len(degerler)
        pts = []
        for i, v in enumerate(degerler):
            x = (i / (n - 1)) * W if n > 1 else 0
            y = H - _kirp_oran(v, tavan) * H
            pts.append(f"{x:.2f},{y:.2f}")
        return pts

    # Soluk yatay izgara (0/25/50/75/100%)
    izgara = "".join(
        f'<line x1="0" y1="{H - o * H:.2f}" x2="{W}" y2="{H - o * H:.2f}" '
        f'stroke="#e6ebf0" stroke-width="0.4"/>'
        for o in (0.25, 0.5, 0.75, 1.0)
    )
    cizgiler = ""
    for s in seriler:
        pts = nokta_dizi(s["degerler"])
        cizgiler += (f'<polyline fill="none" stroke="{_k(s["renk"])}" stroke-width="1.1" '
                     f'stroke-linejoin="round" stroke-linecap="round" '
                     f'vector-effect="non-scaling-stroke" points="{" ".join(pts)}"/>')
        # son noktayi vurgula
        if pts:
            sx, sy = pts[-1].split(",")
            cizgiler += f'<circle cx="{sx}" cy="{sy}" r="1.3" fill="{_k(s["renk"])}"/>'

    svg = (f'<svg class="cizgi-svg" viewBox="0 0 {W:.0f} {H:.0f}" preserveAspectRatio="none" '
           f'role="img" aria-label="{_k(aria)}">{izgara}{cizgiler}</svg>')

    etiketler = "".join(f"<span>{_k(e)}</span>"
                        for e in etiket_seyrelt(x_etiketler, 8))
    gosterge = "".join(
        f'<span class="gosterge"><i style="background:{_k(s["renk"])}"></i>{_k(s["ad"])}</span>'
        for s in seriler)
    alt = f'<p class="grafik-alt">{_k(altyazi)}</p>' if altyazi else ""
    return (f'<div class="cizgi-grafik">'
            f'<div class="sutun-tavan"><span>{_k(tavan_metni)}</span></div>'
            f'{svg}<div class="sutun-etiketler">{etiketler}</div>'
            f'<div class="gostergeler">{gosterge}</div>{alt}</div>')


def _kirp_oran(deger, tavan):
    """0..1 arasi; tavani asani tepede tutar."""
    if tavan <= 0:
        return 0.0
    return max(0.0, min(1.0, deger / tavan))
