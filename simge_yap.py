# -*- coding: utf-8 -*-
"""Kazan masaüstü simgesini (simge.ico) saf Python ile üretir — dış kütüphane yok.

Kimlik: lacivert zemin (giriş ekranıyla aynı degrade) + amber çubuk grafik
(hesap-kitap/takip teması).
Birden çok boyut (256/64/48/32/16) tek .ico içine konur; Windows küçük yerlerde
küçük boyutu kullanır, böylece 16 px'te bile net görünür. Kenarlar 4x büyük
çizip küçülterek (supersampling) yumuşatılır; saydam kenarda kararma olmasın
diye alfa-ağırlıklı küçültme kullanılır.

Çalıştır:  python simge_yap.py      ->  simge.ico (+ simge-onizleme.png)
"""
import struct
import zlib

LACI_UST = (0x14, 0x56, 0x7f)      # degrade üstü
LACI_ALT = (0x0a, 0x33, 0x50)      # degrade altı
KULAH = (0xc2, 0x72, 0x28)         # külah (amber koyu)
TOP = (0xf2, 0xb0, 0x5a)           # dondurma topu (amber açık)
TOP_ISIK = (0xff, 0xd9, 0x9c)      # top üzerinde ışık


def _karistir(alt, ust):
    """ust rengi (RGBA) alt rengin (RGB) üzerine yerleştirir, basit alfa."""
    a = ust[3] / 255.0
    return (int(alt[0] * (1 - a) + ust[0] * a),
            int(alt[1] * (1 - a) + ust[1] * a),
            int(alt[2] * (1 - a) + ust[2] * a))


def _ic_yuvarlak(x, y, S, r):
    cx = min(max(x, r), S - 1 - r)
    cy = min(max(y, r), S - 1 - r)
    dx, dy = x - cx, y - cy
    return dx * dx + dy * dy <= r * r


def _ciz(size, ss=4):
    """Bir boyutu ss katı büyük çizip alfa-ağırlıklı küçülterek döndürür."""
    S = size * ss
    buf = bytearray(S * S * 4)       # RGBA, hepsi saydam

    r_kose = 0.20 * S
    bar_w = 0.150 * S
    taban = 0.740 * S
    # (sol kenar, tepe y) — soldan sağa yükselen üç çubuk (hesap/takip grafiği)
    barlar = [(0.250 * S, 0.560 * S), (0.425 * S, 0.430 * S), (0.600 * S, 0.300 * S)]
    cx0, cx1, cy0, cy1 = 0.220 * S, 0.780 * S, 0.740 * S, 0.778 * S   # taban çizgisi

    for y in range(S):
        t = y / (S - 1)
        bg = tuple(int(LACI_UST[k] + (LACI_ALT[k] - LACI_UST[k]) * t) for k in range(3))
        row = y * S * 4
        for x in range(S):
            if not _ic_yuvarlak(x, y, S, r_kose):
                continue                              # zemin dışı: saydam kalsın
            renk = bg
            if cx0 <= x <= cx1 and cy0 <= y <= cy1:
                renk = TOP_ISIK                       # taban çizgisi (krem)
            for sol, tepe in barlar:
                if sol <= x <= sol + bar_w and tepe <= y <= taban:
                    renk = TOP                        # çubuk (amber)
                    break
            i = row + x * 4
            buf[i], buf[i + 1], buf[i + 2], buf[i + 3] = renk[0], renk[1], renk[2], 255

    # alfa-ağırlıklı küçültme (ss x ss blok ortalaması)
    out = bytearray(size * size * 4)
    for oy in range(size):
        for ox in range(size):
            sr = sg = sb = sa = 0
            for yy in range(ss):
                for xx in range(ss):
                    i = (((oy * ss + yy) * S) + (ox * ss + xx)) * 4
                    a = buf[i + 3]
                    sr += buf[i] * a
                    sg += buf[i + 1] * a
                    sb += buf[i + 2] * a
                    sa += a
            j = (oy * size + ox) * 4
            if sa:
                out[j], out[j + 1], out[j + 2] = sr // sa, sg // sa, sb // sa
            out[j + 3] = sa // (ss * ss)
    return bytes(out)


def _png(pixels, w, h):
    ham = bytearray()
    satir = w * 4
    for y in range(h):
        ham.append(0)
        ham.extend(pixels[y * satir:(y + 1) * satir])

    def parca(tur, veri):
        g = struct.pack(">I", len(veri)) + tur + veri
        return g + struct.pack(">I", zlib.crc32(tur + veri) & 0xffffffff)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + parca(b"IHDR", ihdr)
            + parca(b"IDAT", zlib.compress(bytes(ham), 9)) + parca(b"IEND", b""))


def _ico(pngler):
    n = len(pngler)
    bas = struct.pack("<HHH", 0, 1, n)
    girisler = b""
    govde = b""
    offset = 6 + 16 * n
    for size, png in pngler:
        wh = 0 if size >= 256 else size
        girisler += struct.pack("<BBBBHHII", wh, wh, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
        govde += png
    return bas + girisler + govde


def main():
    boyutlar = [256, 64, 48, 32, 16]
    pngler = []
    for b in boyutlar:
        px = _ciz(b)
        pngler.append((b, _png(px, b, b)))
    with open("simge.ico", "wb") as f:
        f.write(_ico(pngler))
    # kolay önizleme için 256'lık PNG
    with open("simge-onizleme.png", "wb") as f:
        f.write(dict(pngler)[256])
    print("Yazildi: simge.ico (" + ", ".join(str(b) for b in boyutlar) + ") + simge-onizleme.png")


if __name__ == "__main__":
    main()
