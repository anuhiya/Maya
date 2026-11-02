"""Dark navy theme and the eDelta logo (P2 as changed by A6): contrast, logo sizing, and the fallback."""
import re
import shutil
from pathlib import Path

from PIL import Image
from streamlit.testing.v1 import AppTest

from maya.ui import style

ROOT = Path(__file__).resolve().parent.parent
HEX = r"#[0-9A-Fa-f]{6}"


def luminance(color):
    r, g, b = (int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def css_pairs():
    """Every CSS rule that sets both a text colour and a background, plus text rules on the page background."""
    pairs = []
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", style.CSS):
        fg = re.search(rf"(?<![-\w])color:\s*({HEX})", body)
        bg = re.search(rf"background(?:-color)?:\s*({HEX})", body)
        if fg:
            fallback = style.BG  # a rule with no background sits on the page background
            if "stBaseButton-primary" in selector:  # text inside a primary button sits on its fill
                fallback = "#151A52" if ":disabled" in selector else style.ACCENT
            pairs.append((selector.strip(), fg.group(1), bg.group(1) if bg else fallback))
    return pairs


def test_every_text_and_background_pair_in_the_css_meets_contrast():
    pairs = css_pairs()
    assert len(pairs) > 30
    low = [(s, fg, bg, round(ratio(fg, bg), 2)) for s, fg, bg in pairs if ratio(fg, bg) < 4.5]
    assert not low, low


def test_text_on_cards_and_theme_tokens_meet_contrast():
    for fg in (style.INK, style.MUTED, style.ACCENT):
        assert ratio(fg, style.BG) >= 4.5 and ratio(fg, style.SURFACE) >= 4.5
    assert ratio(style.ACCENT_TEXT, style.ACCENT) >= 4.5  # primary button: dark text on the blue fill
    for fg in (style.GOOD, style.WARN, style.BAD):
        assert ratio(fg, style.BG) >= 4.5 and ratio(fg, style.SURFACE) >= 4.5
    theme = (ROOT / ".streamlit/config.toml").read_text()
    assert 'base = "dark"' in theme and f'backgroundColor = "{style.BG}"' in theme


def test_logo_file_is_the_unchanged_original_and_the_icon_is_the_e_mark_only():
    assert (ROOT / "assets/edelta-logo.png").read_bytes() == (ROOT / "assets/image.png").read_bytes()
    assert Image.open(style.LOGO).size == (258, 236)
    icon = Image.open(style.ICON)
    assert icon.size[0] < 258 and icon.size[1] < 236 and abs(icon.size[0] - icon.size[1]) <= 2


def test_logo_sizes_keep_the_aspect_ratio():
    side = style.logo_html(width=style.SIDEBAR_LOGO_WIDTH)
    assert "width:120px;height:auto" in side
    assert side.count("<img") == 1 and "data:image/png;base64," in side


def test_without_the_logo_the_text_wordmark_is_used(tmp_path):
    missing = tmp_path / "none.png"
    html = style.logo_html(width=120, path=missing)
    assert "<img" not in html and f'<span style="color:{style.ACCENT}">Delta</span>' in html and ">e<" in html


def test_without_the_icon_the_tab_icon_falls_back(monkeypatch, tmp_path):
    monkeypatch.setattr(style, "ICON", tmp_path / "none.png")
    assert style.page_icon() == ":material/circle:"


def test_app_starts_with_the_logo_and_without_it(monkeypatch, tmp_path):
    with_logo = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    assert not with_logo.exception
    shown = " ".join(m.value for m in with_logo.markdown)
    assert shown.count('class="mq-logo"') == 1 and 'class="mq-product">Maya<' in shown  # sidebar only

    monkeypatch.setattr(style, "LOGO", tmp_path / "none.png")
    monkeypatch.setattr(style, "ICON", tmp_path / "none.png")
    without = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    assert not without.exception
    shown = " ".join(m.value for m in without.markdown)
    assert "<img" not in shown and shown.count("Delta</span>") == 1 and 'class="mq-product">Maya<' in shown


def test_headings_use_montserrat_and_tables_do_not_break_words():
    heads = re.findall(r"\.mq-(?:title|head|sub|group)\s*\{([^}]*)\}", style.CSS)
    assert len(heads) == 4 and all("Montserrat" in h for h in heads)
    assert "Fraunces" not in style.CSS and 'headingFont = "Montserrat:' in (ROOT / ".streamlit/config.toml").read_text()
    table_rules = " ".join(re.findall(r"\.mq-table[^{]*\{[^}]*\}", style.CSS))
    assert "anywhere" not in table_rules and "break-word" not in table_rules and "word-break: normal" in table_rules
    assert "td:first-child" in style.CSS and "stMainBlockContainer" in style.CSS and "stHeader" in style.CSS


def test_footer_kicker_buttons_and_title():
    assert style.FOOTER_TEXT.startswith("eDelta Maya. Prototype built for eDelta Consulting. Synthetic, illustrative data.")
    assert "Place names are real; wage rates, rules and dates are illustrative, not the actual law." in style.FOOTER_TEXT
    assert style.FOOTER_TEXT in style.footer_html() and chr(0x2014) not in style.CSS
    assert "text-transform: uppercase" in re.search(r"\.mq-kicker \{[^}]*\}", style.CSS).group(0)
    assert 'content: "\\203A"' in style.CSS and "border-radius: 72px" in style.CSS
    assert "border-radius: 16px" in style.CSS and "Asta Sans" in (ROOT / ".streamlit/config.toml").read_text()


def test_every_page_ends_with_the_footer_and_the_tab_title_is_set():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    assert not at.exception
    assert style.FOOTER_TEXT in " ".join(m.value for m in at.markdown)
    assert 'page_title="eDelta Maya"' in (ROOT / "app.py").read_text()
