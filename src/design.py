"""Design system de l'étude « La data derrière la Blue Wall » et rendu des fonds de page Power BI.

Rapport d'analyse (pas un diaporama) : le fond ne porte que la structure (en-tête, cadres,
libellés, sources). Tous les chiffres sont calculés en direct par les visuels Power BI.
Noir, blanc et gris, avec UN seul accent bleu. Titres : Bahnschrift Bold Condensed. Texte : Segoe UI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
MARGE = 64

NOIR = (0, 0, 0)
NOIR_2 = (16, 17, 21)
CARTE = (22, 23, 27)
BORD = (46, 47, 53)
BLANC = (255, 255, 255)
GRIS_1 = (170, 170, 170)
GRIS_2 = (118, 118, 118)
BLEU = (47, 107, 214)
HEX = lambda c: "#%02X%02X%02X" % c

FONTS = Path(r"C:\Windows\Fonts")


def bahn(size: int, style: str = "Bold Condensed") -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONTS / "bahnschrift.ttf"), size)
    f.set_variation_by_name(style)
    return f


def segoe(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / ("segoeuib.ttf" if bold else "segoeui.ttf")), size)


# --- Grille ------------------------------------------------------------------------------
GAP = 16
LARGEUR = W - 2 * MARGE                     # 1792
Y_FILTRES, H_FILTRES = 182, 62
H_KPI = 112


def colonnes(fractions: list[float], x0: int = MARGE, largeur: int = LARGEUR) -> list[tuple[int, int]]:
    """Découpe la largeur en colonnes proportionnelles (avec gouttières)."""
    utile = largeur - GAP * (len(fractions) - 1)
    tot = sum(fractions)
    out, x = [], x0
    for i, f in enumerate(fractions):
        w = round(utile * f / tot) if i < len(fractions) - 1 else x0 + largeur - x
        out.append((x, w))
        x += w + GAP
    return out


@dataclass
class Carte:
    x: int
    y: int
    w: int
    h: int
    titre: str = ""
    legende: str = ""
    tags: tuple = ()
    style: str = "visuel"         # visuel | kpi | texte | filtres
    visuel: str = ""              # identifiant du visuel Power BI posé dans la carte
    filtres: list = field(default_factory=list)   # style filtres : identifiants des segments

    @property
    def zone_visuel(self) -> tuple[int, int, int, int]:
        if self.style == "kpi":
            return self.x + 14, self.y + 40, self.w - 28, self.h - 46
        if self.style == "texte":
            return self.x + 14, self.y + 46, self.w - 28, self.h - 54
        return self.x + 12, self.y + 70, self.w - 24, self.h - 78

    def zones_filtres(self) -> list[tuple[str, tuple[int, int, int, int]]]:
        x, larg = self.x + 150, 300
        return [(fid, (x + i * (larg + GAP), self.y + 6, larg, self.h - 12)) for i, fid in enumerate(self.filtres)]


@dataclass
class Page:
    numero: int
    rubrique: str
    titre: str
    question: str
    tags: tuple
    sources: str
    cartes: list[Carte] = field(default_factory=list)
    nom_onglet: str = ""
    total_pages: int = 6
    textes: dict = field(default_factory=dict)    # contenu des zones de texte Power BI


def texte_espace(d, xy, txt, font, fill, espacement=0.0, anchor="la"):
    x, y = xy
    if anchor[0] == "r":
        x -= largeur_espace(txt, font, espacement)
    for ch in txt:
        d.text((x, y), ch, font=font, fill=fill, anchor="l" + anchor[1])
        x += font.getlength(ch) + espacement * font.size
    return x


def largeur_espace(txt, font, espacement=0.0):
    return sum(font.getlength(c) for c in txt) + espacement * font.size * len(txt)


def ajuster(txt: str, taille_max: int, largeur: int, style="Bold Condensed"):
    t = taille_max
    while t > 24 and bahn(t, style).getlength(txt) > largeur:
        t -= 2
    return bahn(t, style)


def pastille(d, x_droite: int, y: int, label: str, taille: int = 15) -> int:
    f = bahn(taille, "SemiBold")
    tw = largeur_espace(label, f, .08)
    pad_x, h = 10, taille + 12
    x0 = x_droite - tw - 2 * pad_x
    if label == "RÉEL":
        d.rounded_rectangle((x0, y, x_droite, y + h), radius=h // 2, fill=BLANC)
        col = NOIR
    else:
        col = GRIS_1 if label == "SIMULÉ" else GRIS_2
        d.rounded_rectangle((x0, y, x_droite, y + h), radius=h // 2, outline=col, width=2)
    texte_espace(d, (x0 + pad_x, y + h / 2 + 1), label, f, col, .08, anchor="lm")
    return x0


def fond(seed: int) -> Image.Image:
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:H, 0:W]
    t = np.clip(1 - (xx / W * .6 + yy / H * .4), 0, 1) ** 2.2
    base = np.array(NOIR, float) + (np.array(NOIR_2, float) - np.array(NOIR, float)) * t[..., None] * 1.7
    img = np.clip(base + rng.normal(0, 7.0, (H, W, 1)), 0, 255).astype(np.uint8)
    return Image.fromarray(img, "RGB")


def dessiner_page(p: Page, avec_zones: bool = False) -> Image.Image:
    img = fond(p.numero).convert("RGBA")
    calque = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(calque)
    d.text((W - MARGE + 20, -36), f"{p.numero:02d}", font=bahn(230), fill=(255, 255, 255, 10), anchor="ra")
    texte_espace(d, (MARGE, 42), f"[ {p.rubrique.upper()} ]", bahn(19, "SemiBold"), GRIS_1, .14, "lm")
    x = W - MARGE
    for tag in reversed(p.tags):
        x = pastille(d, x, 28, tag) - 10
    d.text((MARGE - 3, 60), p.titre.upper(), font=ajuster(p.titre.upper(), 62, LARGEUR - 40), fill=BLANC)
    d.text((MARGE, 136), p.question, font=segoe(21), fill=GRIS_1)
    for c in p.cartes:
        dessiner_carte(d, c, avec_zones)
    d.line((MARGE, 1012, W - MARGE, 1012), fill=BORD, width=1)
    d.text((MARGE, 1042), "Étude indépendante - non affiliée à la Karmine Corp",
           font=segoe(16), fill=GRIS_2, anchor="lm")
    texte_espace(d, (W - MARGE, 1042), f"{p.numero:02d} / {p.total_pages:02d}", bahn(18, "SemiBold"), GRIS_1, .1, "rm")
    d.text((W - MARGE - 100, 1042), p.sources, font=segoe(16), fill=GRIS_2, anchor="rm")
    return Image.alpha_composite(img, calque).convert("RGB")


def dessiner_carte(d, c: Carte, avec_zones: bool):
    d.rounded_rectangle((c.x, c.y, c.x + c.w, c.y + c.h), radius=8, fill=CARTE + (235,), outline=BORD, width=1)
    xr = c.x + c.w - 14
    for tag in reversed(c.tags):
        xr = pastille(d, xr, c.y + 12, tag, 12) - 6
    if c.style == "filtres":
        texte_espace(d, (c.x + 22, c.y + c.h / 2), "[ FILTRES ]", bahn(16, "SemiBold"), GRIS_1, .14, "lm")
    elif c.style in ("kpi", "texte"):
        f = bahn(15, "SemiBold")
        lab = f"[ {c.titre.upper()} ]"
        while largeur_espace(lab, f, .12) > xr - c.x - 30 and f.size > 11:
            f = bahn(f.size - 1, "SemiBold")
        texte_espace(d, (c.x + 18, c.y + 24), lab, f, GRIS_1, .12, "lm")
    else:
        dispo = xr - (c.x + 18) - 10
        t = 22
        while t > 15 and bahn(t, "SemiBold SemiCondensed").getlength(c.titre.upper()) > dispo:
            t -= 1
        d.text((c.x + 18, c.y + 14 + (22 - t) // 2), c.titre.upper(), font=bahn(t, "SemiBold SemiCondensed"), fill=BLANC)
        d.text((c.x + 18, c.y + 44), c.legende, font=segoe(15), fill=GRIS_1)
    if avec_zones:
        zones = [z for _, z in c.zones_filtres()] if c.style == "filtres" else [c.zone_visuel]
        for x, y, w, h in zones:
            d.rectangle((x, y, x + w, y + h), outline=(80, 80, 90), width=1)


def sauver(p: Page, dossier: Path, avec_zones: bool = False) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"fond_page_{p.numero:02d}.png"
    dessiner_page(p, avec_zones).save(chemin, optimize=True)
    return chemin
