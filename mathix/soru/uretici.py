"""MATHİX — Matematik soru üretici.

İki kaynak:
  1) Soru bankası dosyası (data/ klasöründe) — kavramsal sorular
  2) Prosedürel üretici — sınıf/zorluğa göre dinamik işlem soruları
"""
import math
import os
import random
import re
from pathlib import Path

from mathix.config import SORU_BANKASI_DOSYA_ADLARI


# ==============================================================================
# SORU BANKASI (DOSYADAN)
# ==============================================================================
SORU_BANKASI = {}
SORU_BANKASI_HAVUZLARI = {}

# Son üretilen sorunun meta bilgisi (QuizFrame "Soru Bankası #42" göstermek için kullanır)
SON_SORU_META = {
    "bank": False,
    "sinif": None,
    "zorluk": None,
    "no": None,
    "soru": None,
}


def _bank_dosya_yolu():
    """data/ klasöründeki soru bankası dosyasının tam yolunu bul."""
    # mathix/soru/uretici.py → mathix/soru/ → mathix/ → proje kökü
    proje_koku = Path(__file__).resolve().parent.parent.parent
    data_klasoru = proje_koku / "data"

    aday_klasorler = [data_klasoru, proje_koku]
    for klasor in aday_klasorler:
        for ad in SORU_BANKASI_DOSYA_ADLARI:
            yol = klasor / ad
            if yol.exists():
                return yol
    return None


def soru_bankasi_yukle():
    """data/ klasöründeki soru bankası dosyasını yükle. Başarı: True."""
    global SORU_BANKASI, SORU_BANKASI_HAVUZLARI
    SORU_BANKASI = {}
    SORU_BANKASI_HAVUZLARI = {}

    dosya_yolu = _bank_dosya_yolu()
    if dosya_yolu is None:
        return False

    try:
        satirlar = dosya_yolu.read_text(encoding="utf-8").splitlines()
    except Exception:
        return False

    aktif_sinif = None
    aktif_zorluk = None

    for satir in satirlar:
        satir = satir.strip()
        if not satir:
            continue

        m = re.search(r"(\d+)\.\s*SINIF\s+—\s+100\s+SORU", satir, re.IGNORECASE)
        if m:
            aktif_sinif = int(m.group(1))
            SORU_BANKASI.setdefault(aktif_sinif, {})
            aktif_zorluk = None
            continue

        for baslik, zorluk in (
            (r"KOLAY\s*\(1-40\)", "Kolay"),
            (r"ORTA\s*\(41-75\)", "Orta"),
            (r"ZOR\s*\(76-100\)", "Zor"),
        ):
            if re.fullmatch(baslik, satir, re.IGNORECASE):
                aktif_zorluk = zorluk
                SORU_BANKASI.setdefault(aktif_sinif, {}).setdefault(zorluk, [])
                break
        else:
            q = re.match(r"(\d+)\.\s+(.*)", satir)
            if q and aktif_sinif and aktif_zorluk:
                SORU_BANKASI[aktif_sinif][aktif_zorluk].append({
                    "no": int(q.group(1)),
                    "soru": q.group(2).strip(),
                })

    # Havuzları karıştır
    for sinif, zorluklar in SORU_BANKASI.items():
        for zorluk, sorular in zorluklar.items():
            havuz = list(sorular)
            random.shuffle(havuz)
            SORU_BANKASI_HAVUZLARI[(sinif, zorluk)] = havuz

    return bool(SORU_BANKASI)


def bankadan_soru_sec(sinif, zorluk):
    """Havuzdan sıradaki soruyu çek. Havuz boşalırsa karıştırıp yeniden doldur."""
    key = (sinif, zorluk)
    if key not in SORU_BANKASI_HAVUZLARI:
        return None

    if not SORU_BANKASI_HAVUZLARI[key]:
        havuz = list(SORU_BANKASI.get(sinif, {}).get(zorluk, []))
        if not havuz:
            return None
        random.shuffle(havuz)
        SORU_BANKASI_HAVUZLARI[key] = havuz

    return SORU_BANKASI_HAVUZLARI[key].pop()


# ==============================================================================
# PROSEDÜREL ÜRETİCİ
# ==============================================================================
def prosedurel_soru_uret(sinif, zorluk):
    """Sınıf ve zorluğa göre dinamik soru üret. (soru_metni, cevap) döner."""
    sinif = max(1, min(12, int(sinif)))
    if sinif <= 4:
        return _uret_1_4(sinif, zorluk)
    elif sinif <= 6:
        return _uret_5_6(sinif, zorluk)
    elif sinif <= 8:
        return _uret_7_8(sinif, zorluk)
    elif sinif <= 10:
        return _uret_9_10(sinif, zorluk)
    else:
        return _uret_11_12(sinif, zorluk)


# ---- 1-4. sınıf ----
def _uret_1_4(sinif, zorluk):
    """1-4. sinif: sayi bilgisi ve temel matematik konulari."""
    sinir = {"Kolay": 20, "Orta": 60, "Zor": 120}.get(zorluk, 60)
    konular = ["islem", "basamak", "oruntu", "geometri"]
    if sinif >= 3:
        konular += ["carpma_bolme", "carpma_bolme", "olcu"]
    if sinif >= 4:
        konular += ["kesir"]
    konu = random.choice(konular)

    if konu == "islem":
        a, b = random.randint(2, sinir), random.randint(1, sinir)
        islem = random.choice(["+", "-"])
        if islem == "-" and b > a:
            a, b = b, a
        return (f"{a} {islem} {b} = ?", a + b if islem == "+" else a - b)
    if konu == "basamak":
        basamak = random.choice([10, 100] if sinif >= 3 else [10])
        sayi = random.randint(basamak, basamak * 10 - 1)
        cevap = (sayi // basamak) % 10
        ad = "onlar" if basamak == 10 else "yüzler"
        return (f"{sayi} sayısındaki {ad} basamağının değeri kaçtır?", cevap * basamak)
    if konu == "oruntu":
        adim = random.randint(2, 5 if zorluk == "Kolay" else 12)
        baslangic = random.randint(1, 20)
        terim = baslangic + adim * 3
        return (f"{baslangic}, {baslangic + adim}, {baslangic + 2 * adim}, ? örüntüsünde sonraki sayı kaçtır?", terim)
    if konu == "geometri":
        sekiller = [("üçgenin kenar sayısı", 3), ("karenin köşe sayısı", 4),
                    ("dikdörtgenin kenar sayısı", 4), ("beşgenin kenar sayısı", 5)]
        if sinif <= 2:
            sekiller = sekiller[:2]
        ifade, cevap = random.choice(sekiller)
        return (f"Bir {ifade} kaçtır?", cevap)
    if konu == "olcu":
        miktar = random.randint(2, 9 if zorluk == "Kolay" else 20)
        return (f"{miktar} metre kaç santimetredir?", miktar * 100)
    if konu == "kesir":
        payda = random.choice([2, 4, 8, 10])
        pay = random.randint(1, payda - 1)
        hedef = payda * random.choice([2, 3, 4])
        return (f"{pay}/{payda} kesrinin paydası {hedef} yapılırsa pay kaç olur?", pay * hedef // payda)

    if random.choice([True, False]):
        carpim = random.randint(2, 10 if zorluk == "Kolay" else 12)
        carpan = random.randint(2, 10)
        return (f"{carpim} × {carpan} = ?", carpim * carpan)
    bolen = random.randint(2, 10)
    bolum = random.randint(2, 10 if zorluk == "Kolay" else 15)
    return (f"{bolen * bolum} ÷ {bolen} = ?", bolum)


def _uret_5_6(sinif, zorluk):
    """5-6. sinif: dort isleme ek olarak kesir, ondalik, oran, olcu ve geometri."""
    konular = ["islem", "kesir", "ondalik", "geometri", "olcu", "oran"]
    if sinif >= 6:
        konular += ["yuzde", "yuzde"]
    konu = random.choice(konular)
    buyut = 1 if zorluk == "Kolay" else (2 if zorluk == "Orta" else 4)

    if konu == "islem":
        a, b = random.randint(12, 80 * buyut), random.randint(3, 30 * buyut)
        islem = random.choice(["+", "-", "×", "÷"])
        if islem == "÷":
            bolum = random.randint(2, 15 * buyut)
            return (f"{b * bolum} ÷ {b} = ?", bolum)
        if islem == "-" and b > a:
            a, b = b, a
        if islem == "+":
            return (f"{a} + {b} = ?", a + b)
        if islem == "-":
            return (f"{a} - {b} = ?", a - b)
        return (f"{a} × {b} = ?", a * b)
    if konu == "kesir":
        payda = random.choice([4, 5, 8, 10, 20])
        pay = random.randint(1, payda - 1)
        miktar = payda * random.randint(2, 12 * buyut)
        return (f"{miktar} sayısının {pay}/{payda}'i kaçtır?", miktar * pay // payda)
    if konu == "ondalik":
        a, b = random.randint(10, 999), random.randint(1, 999)
        x, y = a / 10, b / 10
        if random.choice([True, False]):
            return (f"{x:g} + {y:g} = ?", round(x + y, 1))
        larger, smaller = max(x, y), min(x, y)
        return (f"{larger:g} - {smaller:g} = ?", round(larger - smaller, 1))
    if konu == "geometri":
        if random.choice([True, False]):
            en = random.randint(3, 12 * buyut)
            boy = random.randint(3, 12 * buyut)
            return (f"Kenarları {en} cm ve {boy} cm olan dikdörtgenin alanı kaç cm²'dir?", en * boy)
        kenar = random.randint(3, 15 * buyut)
        return (f"Bir karenin bir kenarı {kenar} cm ise çevresi kaç cm'dir?", 4 * kenar)
    if konu == "olcu":
        miktar = random.randint(2, 25 * buyut)
        birim, hedef, katsayi = random.choice([
            ("metre", "santimetre", 100),
            ("kilogram", "gram", 1000),
            ("litre", "mililitre", 1000),
        ])
        return (f"{miktar} {birim} kaç {hedef} eder?", miktar * katsayi)
    if konu == "oran":
        birim = random.randint(2, 12 * buyut)
        kat = random.randint(2, 8)
        return (f"3 kalem {3 * birim} TL ise {3 * kat} kalem kaç TL'dir?", birim * 3 * kat // 3)
    miktar = random.choice([100, 200, 400, 500, 800, 1000]) * buyut
    yuzde = random.choice([10, 20, 25, 50])
    return (f"{miktar} sayısının %{yuzde}'si kaçtır?", miktar * yuzde // 100)


def _uret_7_8(sinif, zorluk):
    """7-8. sinif: cebir, oran-oranti, yuzde, us, karekok ve geometri."""
    seviye = {"Kolay": 1, "Orta": 2, "Zor": 4}.get(zorluk, 2)
    konu = random.choice(["denklem", "us", "yuzde", "oran", "karekok", "geometri", "islem"])
    if konu == "denklem":
        x = random.randint(1, 12 * seviye)
        a = random.randint(1, 5 if zorluk == "Kolay" else 12)
        b = random.randint(2, 20 * seviye)
        return (f"{a}x + {b} = {a * x + b} ise x kaçtır?", x)
    if konu == "us":
        taban = random.randint(2, 8 if zorluk == "Kolay" else 12)
        us = random.randint(2, 3 if zorluk == "Kolay" else 5)
        return (f"{taban}^{us} = ?", taban ** us)
    if konu == "yuzde":
        yuzde = random.choice([10, 20, 25, 40, 50, 75])
        temel = random.choice([100, 200, 400, 800]) * seviye
        return (f"{temel} sayısının %{yuzde}'si kaçtır?", temel * yuzde / 100)
    if konu == "oran":
        a, b, kat = random.randint(2, 8), random.randint(3, 10), random.randint(2, 12 * seviye)
        return (f"x/{kat} = {a}/{b} ise x kaçtır?", kat * a / b)
    if konu == "karekok":
        kok = random.randint(2, 12 * seviye)
        return (f"√{kok * kok} = ?", kok)
    if konu == "geometri":
        if sinif >= 8 and random.choice([True, False]):
            kat = random.randint(1, 5 * seviye)
            a, b = 3 * kat, 4 * kat
            return (f"Dik üçgende dik kenarlar {a} ve {b} cm ise hipotenüs kaç cm'dir?", 5 * kat)
        aci = random.randint(20, 55)
        return (f"Üçgenin iki açısı {aci}° ve {2 * aci}° ise üçüncü açı kaç derecedir?", 180 - 3 * aci)
    if konu == "islem":
        a, b, c = random.randint(5, 30 * seviye), random.randint(2, 20 * seviye), random.randint(2, 10)
        return (f"({a} + {b}) × {c} = ?", (a + b) * c)
    sayi = random.randint(100, 1000 * seviye)
    yuzde = random.choice([5, 10, 15, 20, 25])
    return (f"{sayi} sayısının %{yuzde}'si kaçtır?", sayi * yuzde / 100)


def _uret_9_10(sinif, zorluk):
    """9-10. sinif: denklem, fonksiyon, us, kok, mutlak deger ve trigonometrik oran."""
    seviye = {"Kolay": 1, "Orta": 2, "Zor": 4}.get(zorluk, 2)
    konu = random.choice(["denklem", "parabol", "fonksiyon", "mutlak", "us", "kok", "trig"])
    if konu == "denklem":
        x = random.randint(-10 * seviye, 10 * seviye)
        a = random.randint(1, 5 if zorluk == "Kolay" else 12)
        b = random.randint(-20 * seviye, 20 * seviye)
        return (f"{a}x + ({b}) = {a * x + b} ise x kaçtır?", x)
    if konu == "parabol":
        r1, r2 = random.sample(range(1, 12 * seviye + 1), 2)
        return (f"x² - {r1 + r2}x + {r1 * r2} = 0 denkleminin küçük kökü kaçtır?", min(r1, r2))
    if konu == "fonksiyon":
        x, a, b = random.randint(-10, 10 * seviye), random.randint(1, 8), random.randint(-20, 20 * seviye)
        return (f"f(x) = {a}x + ({b}) ise f({x}) kaçtır?", a * x + b)
    if konu == "mutlak":
        deger = random.randint(-100 * seviye, 100 * seviye)
        ek = random.randint(1, 30)
        return (f"|{deger}| + {ek} = ?", abs(deger) + ek)
    if konu == "us":
        taban = random.randint(2, 8)
        us = random.randint(2, 3 if zorluk == "Kolay" else 5)
        return (f"{taban}^{us} = ?", taban ** us)
    if konu == "kok":
        kok = random.randint(2, 20 * seviye)
        return (f"√{kok * kok} = ?", kok)
    aci, deger = random.choice([(0, 0), (30, 0.5), (90, 1), (180, 0), (270, -1), (360, 0)])
    return (f"sin({aci}°) = ? (ondalık yazabilirsiniz)", deger)


def _uret_11_12(sinif, zorluk):
    """11-12. sinif: fonksiyon, trigonometrik deger, logaritma, dizi ve turev."""
    seviye = {"Kolay": 1, "Orta": 2, "Zor": 4}.get(zorluk, 2)
    konu = random.choice(["denklem", "fonksiyon", "trig", "log", "dizi", "turev"])
    if konu == "denklem":
        x = random.randint(-40 * seviye, 40 * seviye)
        a = random.randint(1, 15)
        b = random.randint(-50 * seviye, 50 * seviye)
        return (f"{a}x + ({b}) = {a * x + b} ise x kaçtır?", x)
    if konu == "fonksiyon":
        x = random.randint(-20 * seviye, 20 * seviye)
        a, b = random.randint(1, 15), random.randint(-50 * seviye, 50 * seviye)
        return (f"f(x) = {a}x + ({b}) ise f({x}) kaçtır?", a * x + b)
    if konu == "trig":
        aci, deger = random.choice([(0, 0), (30, 0.5), (90, 1), (180, 0), (270, -1), (360, 0)])
        return (f"sin({aci}°) = ?", deger)
    if konu == "log":
        taban, us = random.choice([2, 3, 5, 10]), random.randint(1, 6 * seviye)
        return (f"log_{taban}({taban ** us}) = ?", us)
    if konu == "dizi":
        ilk, fark = random.randint(1, 20 * seviye), random.randint(2, 10 * seviye)
        n = random.randint(5, 12)
        return (f"Aritmetik dizide a₁={ilk}, ortak fark={fark}. a_{n} kaçtır?", ilk + (n - 1) * fark)
    # Turev: ax² + bx fonksiyonunun verilen noktadaki turevi.
    a, b, x = random.randint(1, 6 * seviye), random.randint(-20, 20 * seviye), random.randint(-10, 10 * seviye)
    return (f"f(x)={a}x²+({b})x ise f'({x}) kaçtır?", 2 * a * x + b)


def soru_uret(sinif, zorluk, kullan_bank=True):
    """Soru üret. (soru_metni, cevap) döner. Cevap None ise banka sorusudur (AI hakem değerlendirir)."""
    global SON_SORU_META

    if kullan_bank and SORU_BANKASI and random.random() < 0.85:
        secilen = bankadan_soru_sec(sinif, zorluk)
        if secilen is not None:
            SON_SORU_META = {
                "bank": True, "sinif": sinif, "zorluk": zorluk,
                "no": secilen["no"], "soru": secilen["soru"],
            }
            return secilen["soru"], None

    soru, cevap = prosedurel_soru_uret(sinif, zorluk)
    SON_SORU_META = {
        "bank": False, "sinif": sinif, "zorluk": zorluk,
        "no": None, "soru": soru,
    }
    return soru, cevap


# Modül yüklenirken soru bankasını yüklemeyi dene
soru_bankasi_yukle()