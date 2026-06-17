from flask import Flask, request, send_file
import io, json, re
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
from reportlab.pdfgen import canvas as rl_canvas
from flask_cors import CORS
import os

try:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    pdfmetrics.registerFont(TTFont('LiberationSerif',        '/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('LiberationSerif-Bold',   '/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf'))
    pdfmetrics.registerFont(TTFont('LiberationSerif-Italic', '/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf'))
    pdfmetrics.registerFont(TTFont('LiberationSans',         '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('LiberationSans-Bold',    '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'))
    pdfmetrics.registerFont(TTFont('LiberationSans-Italic',  '/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf'))
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
    registerFontFamily('LiberationSerif',
        normal='LiberationSerif', bold='LiberationSerif-Bold',
        italic='LiberationSerif-Italic', boldItalic='LiberationSerif-Bold')
    registerFontFamily('LiberationSans',
        normal='LiberationSans', bold='LiberationSans-Bold',
        italic='LiberationSans-Italic', boldItalic='LiberationSans-Bold')
    FONT_SERIF      = 'LiberationSerif'
    FONT_SERIF_BOLD = 'LiberationSerif-Bold'
    FONT_SERIF_IT   = 'LiberationSerif-Italic'
    FONT_SANS       = 'LiberationSans'
    FONT_SANS_BOLD  = 'LiberationSans-Bold'
except Exception:
    FONT_SERIF      = 'Times-Roman'
    FONT_SERIF_BOLD = 'Times-Bold'
    FONT_SERIF_IT   = 'Times-Italic'
    FONT_SANS       = 'Helvetica'
    FONT_SANS_BOLD  = 'Helvetica-Bold'

app = Flask(__name__)
CORS(app)

try:
    from reportlab.graphics.charts.piecharts import Pie as RLPie
    HAS_PIE = True
except ImportError:
    HAS_PIE = False

W, H = A4
NAVY      = colors.HexColor('#0F1F3D')
TEAL      = colors.HexColor('#0E8A7A')
TEAL_LITE = colors.HexColor('#E6F4F2')
GOLD      = colors.HexColor('#C9A84C')
WHITE     = colors.white
OFFWHITE  = colors.HexColor('#F7F8FA')
BORDER    = colors.HexColor('#DDE3ED')
GRAY      = colors.HexColor('#6B7280')
DARK      = colors.HexColor('#1F2937')
RED_SOFT  = colors.HexColor('#FEE2E2')
RED_TEXT  = colors.HexColor('#B91C1C')
GREEN_SOFT= colors.HexColor('#DCFCE7')
GREEN_TEXT= colors.HexColor('#15803D')
AMBER_SOFT= colors.HexColor('#FEF9C3')
AMBER_TEXT= colors.HexColor('#92400E')

def s(name, **kw):
    base = dict(fontName=FONT_SANS, fontSize=9, textColor=DARK, leading=14, spaceAfter=0, spaceBefore=0)
    base.update(kw)
    return ParagraphStyle(name, **base)

ST_SECTION = s('sec', fontName=FONT_SANS_BOLD, fontSize=8, textColor=TEAL, leading=11)
ST_BODY    = s('body', fontName=FONT_SANS, fontSize=9, textColor=colors.HexColor('#374151'), leading=15)
ST_SMALL   = s('sm', fontName=FONT_SANS, fontSize=7.5, textColor=GRAY, leading=11)
ST_TH      = s('th', fontName=FONT_SANS_BOLD, fontSize=8, textColor=WHITE, alignment=TA_RIGHT, leading=11)
ST_TH_L    = s('thl', fontName=FONT_SANS_BOLD, fontSize=8, textColor=WHITE, leading=11)
ST_TD      = s('td', fontName=FONT_SANS, fontSize=8, textColor=DARK, alignment=TA_RIGHT, leading=11)
ST_TD_L    = s('tdl', fontName=FONT_SANS, fontSize=8, textColor=DARK, leading=11)
ST_BOLD    = s('bold', fontName=FONT_SANS_BOLD, fontSize=8, textColor=NAVY, leading=11)
ST_BOLD_R  = s('boldr', fontName=FONT_SANS_BOLD, fontSize=8, textColor=NAVY, alignment=TA_RIGHT, leading=11)
ST_FOOTER  = s('foot', fontName=FONT_SANS, fontSize=7, textColor=GRAY, alignment=TA_CENTER, leading=10)
ST_KPI_V   = s('kpiv', fontName=FONT_SERIF_BOLD, fontSize=17, textColor=NAVY, leading=21, alignment=TA_CENTER)
ST_KPI_L   = s('kpil', fontName=FONT_SANS, fontSize=7, textColor=GRAY, leading=9, alignment=TA_CENTER)
ST_FLAG_B  = s('flagb', fontName=FONT_SANS, fontSize=8, textColor=colors.HexColor('#374151'), leading=12)

def clean(n):
    if n is None: return None
    txt = str(n).strip().upper()
    if txt in ('NA','N/A','','NONE','NULL','-','—'): return None
    try: return float(str(n).replace(',','').replace('£','').replace('%','').replace('$','').strip())
    except: return None

def has_val(n):
    return clean(n) is not None

def fmt(n):
    v = clean(n)
    return f'£{v:,.0f}' if v is not None else 'N/A'

def fmtp(n):
    v = clean(n)
    if v is None: return 'N/A'
    if v > 1: v = v/100
    return f'{v:.1%}'

_MONTH_CORRECTIONS = {
    'mur': 'Mar', 'jab': 'Jan', 'fab': 'Feb', 'arp': 'Apr', 'mei': 'May',
    'jly': 'Jul', 'agu': 'Aug', 'okt': 'Oct',
}

def normalise_period_label(label):
    if label is None:
        return ''
    lbl = str(label).strip()
    if not lbl:
        return lbl
    lbl = lbl[0].upper() + lbl[1:].lower() if len(lbl) > 1 else lbl.upper()
    key = lbl[:3].lower()
    if key in _MONTH_CORRECTIONS:
        lbl = _MONTH_CORRECTIONS[key] + lbl[3:]
    return lbl[:6]

def get_list(d, key):
    raw = d.get(key)
    if raw is None: return []
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw or raw.upper() in ('NA','N/A','NONE','NULL'): return []
        try: raw = json.loads(raw)
        except: return []
    if isinstance(raw, dict): raw = [raw]
    if not isinstance(raw, list): return []
    return [item for item in raw if isinstance(item, dict)]

# ── Chart helpers ────────────────────────────────────────────────────────────

def bar_chart(labels, values, w=100, h=50, show_trend=False, C_ACCENT=None):
    vals = [clean(v) or 0 for v in values]
    avg = sum(vals) / len(vals) if vals else 0
    has_peak = avg > 0 and any(v > avg * 1.2 for v in vals)
    maxv = max(vals + [1]) * (1.25 if has_peak else 1.15)
    dw = Drawing(w*mm, h*mm)
    n = max(len(vals), 1)
    avail = (w - 20) * mm
    bw = min(14*mm, avail / (n*1.8))
    gap = (avail - bw*n) / max(n, 1)
    base_y = 10*mm; chart_h = (h-16)*mm
    if C_ACCENT is not None:
        try:
            r, g, b = C_ACCENT.red, C_ACCENT.green, C_ACCENT.blue
            palette = [
                C_ACCENT,
                colors.Color(max(r*0.78,0), max(g*0.78,0), max(b*0.78,0)),
                colors.Color(max(r*0.60,0), max(g*0.60,0), max(b*0.60,0)),
                colors.Color(max(r*0.90,0), max(g*0.90,0), max(b*0.90,0)),
                colors.Color(max(r*0.48,0), max(g*0.48,0), max(b*0.48,0)),
                colors.Color(max(r*0.70,0), max(g*0.70,0), max(b*0.70,0)),
            ]
        except Exception:
            palette = [TEAL, colors.HexColor('#0B6E60'), colors.HexColor('#084F45'),
                       colors.HexColor('#0A8A78'), colors.HexColor('#063D35'), colors.HexColor('#0D9E89')]
    else:
        palette = [TEAL, colors.HexColor('#0B6E60'), colors.HexColor('#084F45'),
                   colors.HexColor('#0A8A78'), colors.HexColor('#063D35'), colors.HexColor('#0D9E89')]
    for i,(v,l) in enumerate(zip(vals, labels)):
        c = palette[i % len(palette)]
        x = 10*mm + i*(bw+gap)
        bh = (v/maxv)*chart_h if maxv > 0 else 1
        dw.add(Rect(x, base_y, bw, max(bh,1), fillColor=c, strokeColor=None))
        dw.add(String(x+bw/2, base_y-8*mm, normalise_period_label(l), fontSize=6.5, fillColor=GRAY, textAnchor='middle'))
        lab = f'£{v/1000:.0f}k' if v >= 1000 else f'£{v:.0f}'
        dw.add(String(x+bw/2, base_y+max(bh,1)+1.5*mm, lab, fontSize=6.5, fillColor=NAVY, textAnchor='middle', fontName=FONT_SANS_BOLD))
        if has_peak and avg > 0 and v > avg * 1.2:
            dw.add(String(x+bw/2, base_y+max(bh,1)+5*mm, '★ Peak',
                          fontSize=6, fillColor=GOLD, textAnchor='middle', fontName=FONT_SANS_BOLD))
    dw.add(Line(8*mm, base_y, w*mm-5*mm, base_y, strokeColor=BORDER, strokeWidth=0.5))
    if show_trend and len(vals) >= 2:
        try:
            overall_up = vals[-1] >= vals[0]
            tc = GREEN_TEXT if overall_up else RED_TEXT
            tops_x = [10*mm + i*(bw+gap) + bw/2 for i in range(len(vals))]
            tops_y = [base_y + (v/maxv)*chart_h if maxv > 0 else base_y for v in vals]
            for i in range(len(vals) - 1):
                tl = Line(tops_x[i], tops_y[i], tops_x[i+1], tops_y[i+1],
                          strokeColor=tc, strokeWidth=1.5)
                tl.strokeDashArray = [4, 3]
                dw.add(tl)
        except Exception:
            pass
    return dw

def margin_bar(pct_val, label, color, w=65, h=10):
    v = clean(pct_val)
    if v is None: v = 0
    if v > 1: v = v/100
    dw = Drawing(w*mm, h*mm); track_w=(w-4)*mm; fill_w=track_w*min(max(v,0),1.0)
    dw.add(Rect(2*mm,3*mm,track_w,4*mm,fillColor=BORDER,strokeColor=None,rx=2,ry=2))
    dw.add(Rect(2*mm,3*mm,fill_w,4*mm,fillColor=color,strokeColor=None,rx=2,ry=2))
    dw.add(String(2*mm,0.5*mm,str(label),fontSize=6,fillColor=GRAY,textAnchor='start'))
    dw.add(String((w-2)*mm,0.5*mm,f'{v:.1%}',fontSize=6.5,fillColor=color,textAnchor='end',fontName=FONT_SANS_BOLD))
    return dw

def kpi_card(value, label, sub):
    sub_s   = s('cs', fontName=FONT_SANS_BOLD, fontSize=7.5, textColor=TEAL, leading=10, alignment=TA_CENTER)
    empty_s = s('ke', fontSize=7, leading=9, alignment=TA_CENTER)
    data=[[Paragraph(str(value),ST_KPI_V)],[Paragraph(str(label),ST_KPI_L)],[Paragraph(str(sub),sub_s)],[Paragraph('',empty_s)]]
    t=Table(data,colWidths=[38*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),WHITE),('BOX',(0,0),(-1,-1),0.75,BORDER),
        ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
        ('LEFTPADDING',(0,0),(-1,-1),2),('RIGHTPADDING',(0,0),(-1,-1),2),
    ]))
    return t

def section_header(title, accent=None):
    ac = accent if accent is not None else TEAL
    data=[[Paragraph(title.upper().replace('&','&amp;'),ST_SECTION)]]
    t=Table(data,colWidths=[175*mm])
    t.setStyle(TableStyle([
        ('LINEBELOW',(0,0),(-1,-1),1,ac),
        ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),3),
        ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
    ]))
    return t

def flag_card(num, title, body, severity='WATCH'):
    color_map = {
        'POSITIVE': (GREEN_TEXT, GREEN_SOFT,  '+', 'Positive'),
        'WATCH':    (AMBER_TEXT, AMBER_SOFT,  '!', 'Watch'),
        'RISK':     (RED_TEXT,   RED_SOFT,    'X', 'Risk'),
        'INFO':     (TEAL,       TEAL_LITE,   'i', 'Info'),
    }
    tc,bg,icon,label = color_map.get(severity.upper(), (AMBER_TEXT,AMBER_SOFT,'!','Watch'))
    icon_s = s('ico',fontName=FONT_SANS_BOLD,fontSize=10,textColor=tc,alignment=TA_CENTER,leading=12)
    sev_s  = s('sev',fontName=FONT_SANS_BOLD,fontSize=7, textColor=tc,alignment=TA_CENTER,leading=9)
    head_s = s('fh', fontName=FONT_SANS_BOLD,fontSize=8, textColor=DARK,leading=12)
    data=[[[Paragraph(icon,icon_s),Paragraph(label,sev_s)],
            [Paragraph(f'{num}. {title}',head_s),Spacer(1,2),Paragraph(body,ST_FLAG_B)]]]
    t=Table(data,colWidths=[14*mm,161*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(0,0),bg),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
        ('LEFTPADDING',(0,0),(0,0),3),('RIGHTPADDING',(0,0),(0,0),3),
        ('LEFTPADDING',(1,0),(1,0),8),('RIGHTPADDING',(1,0),(1,0),4),
        ('BOX',(0,0),(-1,-1),0.5,BORDER),
    ]))
    return t

def exp_card(lbl, val, pct_rev):
    data=[
        [Paragraph(str(lbl),s('el',fontName=FONT_SANS_BOLD,fontSize=8,textColor=NAVY,leading=11))],
        [Paragraph(fmt(val),s('ev',fontName=FONT_SANS_BOLD,fontSize=13,textColor=NAVY,leading=17))],
        [Paragraph(f'{pct_rev:.1f}% of revenue' if pct_rev is not None else '',s('ep',fontSize=7,textColor=GRAY,leading=10))],
    ]
    t=Table(data,colWidths=[33*mm])
    t.setStyle(TableStyle([
        ('BOX',(0,0),(-1,-1),0.5,BORDER),
        ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
        ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),4),
        ('BACKGROUND',(0,0),(-1,-1),OFFWHITE),
    ]))
    return t

def comparison_kpi_card(label, current_val, prev_val, is_pct=False):
    def fv(v):
        if not has_val(v): return 'N/A'
        return fmtp(v) if is_pct else fmt(v)
    curr_display = fv(current_val)
    prev_display = fv(prev_val)
    try:
        cv = clean(current_val); pv = clean(prev_val)
        if cv is not None and pv is not None and pv != 0:
            growth = ((cv - pv) / abs(pv)) * 100
            pos = growth >= 0
            arrow = '▲' if pos else '▼'
            growth_str = f"{arrow} {abs(growth):.1f}%"
            gc = GREEN_TEXT if pos else RED_TEXT
        else:
            growth_str = '—'; gc = GRAY
    except:
        growth_str = '—'; gc = GRAY
    growth_s = s('ckg', fontName=FONT_SANS_BOLD, fontSize=7.5, textColor=gc, leading=10, alignment=TA_CENTER)
    prev_s   = s('ckp', fontSize=7, textColor=GRAY, leading=9, alignment=TA_CENTER)
    data = [
        [Paragraph(curr_display, ST_KPI_V)],
        [Paragraph(label, ST_KPI_L)],
        [Paragraph(growth_str, growth_s)],
        [Paragraph(f"vs {prev_display}", prev_s)],
    ]
    t = Table(data, colWidths=[38*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),WHITE),('BOX',(0,0),(-1,-1),0.75,BORDER),
        ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
        ('LEFTPADDING',(0,0),(-1,-1),2),('RIGHTPADDING',(0,0),(-1,-1),2),
    ]))
    return t

# ── Expense pie chart ─────────────────────────────────────────────────────────

def expense_pie_chart(labels, values, w=80, h=85):
    if not HAS_PIE:
        return None
    try:
        vals = [max(clean(v) or 0, 0) for v in values]
        filtered = [(l, v) for l, v in zip(labels, vals) if v > 0]
        if len(filtered) < 2:
            return None
        labels_f, vals_f = zip(*filtered)
        total = sum(vals_f)
        if total <= 0:
            return None
        dw = Drawing(w*mm, h*mm)
        pie = RLPie()
        pie.x = 5*mm
        pie.y = 12*mm          # more bottom clearance for legend text
        pie.width  = (w-10)*mm
        pie.height = (h-20)*mm  # extra top clearance so labels don't clip
        pie.data = list(vals_f)
        pie.labels = [f'{v/total*100:.0f}%' for v in vals_f]
        palette = [TEAL, GOLD, colors.HexColor('#0B6E60'), NAVY, GRAY,
                   colors.HexColor('#0D9E89'), RED_TEXT, colors.HexColor('#084F45')]
        for i in range(len(vals_f)):
            pie.slices[i].fillColor = palette[i % len(palette)]
            pie.slices[i].strokeColor = WHITE
            pie.slices[i].strokeWidth = 0.5
            pie.slices[i].labelRadius = 1.15   # slightly tighter so labels stay inside drawing
            pie.slices[i].fontSize = 6.5
            pie.slices[i].fontName = FONT_SANS_BOLD
        dw.add(pie)
        dw.add(String(w/2*mm, 4*mm, 'Expense Mix',
                     fontSize=7, fillColor=GRAY, textAnchor='middle', fontName=FONT_SANS_BOLD))
        return dw
    except Exception:
        return None

# ── Waterfall chart — stacked bars ───────────────────────────────────────────

def waterfall_chart(total_revenue, total_cogs, total_opex, net_profit, w=175, h=90):
    try:
        rev  = clean(total_revenue)
        if not rev or rev <= 0: return None
        cogs  = clean(total_cogs)  or 0
        opex  = clean(total_opex)  or 0
        np_v  = clean(net_profit)
        gross = rev - cogs
        net   = np_v if np_v is not None else (gross - opex)

        AMBER     = colors.HexColor('#D97706')
        COGS_FADE = colors.HexColor('#6B2D2D')

        dw      = Drawing(w*mm, h*mm)
        base_y  = 18*mm
        chart_h = (h - 30)*mm

        def ht(val): return (max(val, 0) / rev) * chart_h if rev > 0 else 0

        legend_w = 28*mm
        avail    = w*mm - legend_w - 8*mm
        bw       = min(36*mm, avail / 4)
        gap      = (avail - bw * 3) / 2
        def bx(i): return legend_w + i*(bw + gap)

        def label_in(x, y_bot, bar_h, text, color=WHITE):
            if bar_h > 7*mm:
                dw.add(String(x + bw/2, y_bot + bar_h/2 - 1*mm, text,
                              fontSize=6.5, fillColor=color,
                              textAnchor='middle', fontName=FONT_SANS_BOLD))

        def axis_label(x, text):
            dw.add(String(x + bw/2, base_y - 10*mm, text, fontSize=6.5,
                          fillColor=GRAY, textAnchor='middle', fontName=FONT_SANS_BOLD))

        full_h = ht(rev); gp_h = ht(gross); cogs_h = ht(cogs)
        net_h  = ht(max(net, 0)); opex_h = ht(opex); pad_h = full_h - net_h - opex_h

        # Bar 1: Revenue
        dw.add(Rect(bx(0), base_y, bw, full_h, fillColor=TEAL, strokeColor=None))
        label_in(bx(0), base_y, full_h, f'Revenue £{rev/1000:.0f}k')
        axis_label(bx(0), 'Revenue')

        # Bar 2: GP (teal) + COGS (red)
        dw.add(Rect(bx(1), base_y,       bw, gp_h,   fillColor=TEAL,    strokeColor=None))
        dw.add(Rect(bx(1), base_y+gp_h,  bw, cogs_h, fillColor=RED_TEXT, strokeColor=None))
        label_in(bx(1), base_y,      gp_h,   f'GP £{gross/1000:.0f}k')
        label_in(bx(1), base_y+gp_h, cogs_h, f'COGS £{cogs/1000:.0f}k')
        axis_label(bx(1), 'Cost Breakdown')

        # Bar 3: NP (navy) + OpEx (amber) + faded COGS pad
        dw.add(Rect(bx(2), base_y,                   bw, net_h,  fillColor=NAVY,      strokeColor=None))
        dw.add(Rect(bx(2), base_y+net_h,             bw, opex_h, fillColor=AMBER,     strokeColor=None))
        if pad_h > 0:
            dw.add(Rect(bx(2), base_y+net_h+opex_h, bw, pad_h,  fillColor=COGS_FADE, strokeColor=None))
        label_in(bx(2), base_y,               net_h,  f'NP £{net/1000:.0f}k')
        label_in(bx(2), base_y+net_h,         opex_h, f'OpEx £{opex/1000:.0f}k')
        if pad_h > 7*mm:
            label_in(bx(2), base_y+net_h+opex_h, pad_h, f'COGS £{cogs/1000:.0f}k')
        axis_label(bx(2), 'Profit Breakdown')

        # Baseline
        dw.add(Line(legend_w, base_y, (w-3)*mm, base_y, strokeColor=BORDER, strokeWidth=0.5))

        # Legend — vertical, left side, top-aligned with bars
        items = [
            (TEAL,     'Revenue / GP'),
            (RED_TEXT, 'COGS'),
            (AMBER,    'OpEx'),
            (NAVY,     'Net Profit'),
        ]
        swatch = 2*mm; row_h = 5.5*mm
        start_y = base_y + full_h - row_h
        for i, (col, lbl) in enumerate(items):
            ly = start_y - i * row_h
            dw.add(Rect(1*mm, ly+0.3*mm, swatch, swatch, fillColor=col, strokeColor=None))
            dw.add(String(1*mm+swatch+1.5*mm, ly+0.3, lbl,
                          fontSize=6, fillColor=GRAY, textAnchor='start'))

        return dw
    except Exception:
        return None

# ── Tax estimate ──────────────────────────────────────────────────────────────

def tax_estimate_section(net_profit, C_ACCENT):
    try:
        np_val = clean(net_profit)
        if not np_val or np_val <= 0:
            return None
        if np_val <= 50000:
            rate = 0.19; rate_note = '19% small profits rate'
        elif np_val >= 250000:
            rate = 0.25; rate_note = '25% main rate'
        else:
            rate = 0.19 + ((np_val - 50000) / 200000) * 0.06
            rate_note = f'{rate:.1%} (marginal relief applies)'
        tax_est = np_val * rate
        after_tax = np_val - tax_est
        rows = [
            [Paragraph('Corporation Tax Estimate (UK)', s('txh', fontName=FONT_SANS_BOLD, fontSize=8, textColor=WHITE, leading=12)),
             Paragraph('', ST_TD), Paragraph('', ST_TD)],
            [Paragraph('Net Profit', ST_TD_L),
             Paragraph(fmt(np_val), ST_TD), Paragraph('', ST_TD)],
            [Paragraph(f'Estimated Tax ({rate_note})', ST_TD_L),
             Paragraph(f'({fmt(tax_est)})', s('txr', fontSize=8, textColor=RED_TEXT, alignment=TA_RIGHT, leading=11)),
             Paragraph('', ST_TD)],
            [Paragraph('Estimated Profit After Tax', s('txb', fontName=FONT_SANS_BOLD, fontSize=9, textColor=NAVY, leading=13)),
             Paragraph(fmt(after_tax), s('txbr', fontName=FONT_SANS_BOLD, fontSize=9, textColor=NAVY, alignment=TA_RIGHT, leading=13)),
             Paragraph('Estimate only — consult your accountant for exact liability.',
                      s('txn', fontSize=7, textColor=GRAY, leading=10))],
        ]
        t = Table(rows, colWidths=[75*mm, 50*mm, 50*mm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), NAVY),
            ('SPAN', (0,0), (-1,0)),
            ('ROWBACKGROUNDS', (0,1), (-1,2), [WHITE, OFFWHITE]),
            ('BACKGROUND', (0,3), (-1,3), TEAL_LITE),
            ('LINEABOVE', (0,3), (-1,3), 1.5, NAVY),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        return t
    except Exception:
        return None

# ── Cover page — full A4 height ───────────────────────────────────────────────

def cover_page_elements(d, C_PRIMARY, prepared_by, is_wl, wl_logo, wl_tagline, report_ref):
    try:
        bname  = str(d.get('business_name', 'Client Business'))
        period = str(d.get('period', ''))
        bg_word = bname.split()[0].upper() if is_wl else 'FIN'
        has_tag = is_wl and wl_tagline and wl_tagline.upper() not in ('NA','N/A','NONE','')

        from reportlab.platypus import Flowable as _Flowable

        class CoverPage(_Flowable):
            def wrap(self, *args):
                return 175*mm, 257*mm

            def draw(self):
                c   = self.canv
                pw  = 175*mm
                ph  = 278*mm

                # ── Background ─────────────────────────────────────────────
                c.setFillColor(C_PRIMARY)
                c.rect(0, 0, pw, ph, fill=1, stroke=0)

                # Left teal accent bar
                c.setFillColor(TEAL)
                c.rect(0, 0, 4, ph, fill=1, stroke=0)

                # Teal angular shapes — bottom right
                c.setFillColor(colors.Color(14/255, 138/255, 122/255, 0.13))
                p = c.beginPath()
                p.moveTo(pw, 0); p.lineTo(pw, ph*0.45); p.lineTo(pw*0.32, 0)
                p.close(); c.drawPath(p, fill=1, stroke=0)

                c.setFillColor(colors.Color(14/255, 138/255, 122/255, 0.09))
                p2 = c.beginPath()
                p2.moveTo(pw, 0); p2.lineTo(pw, ph*0.28); p2.lineTo(pw*0.55, 0)
                p2.close(); c.drawPath(p2, fill=1, stroke=0)

                # Faint background watermark word
                c.setFillColor(colors.Color(14/255, 138/255, 122/255, 0.055))
                c.setFont(FONT_SERIF_BOLD, 95)
                c.drawString(8*mm, 62*mm, bg_word)

                # ── ZONE 1 — Firm header (top) ─────────────────────────────
                firm_y = ph - 20*mm   # baseline ~258mm from bottom

                if is_wl and wl_logo and wl_logo.upper() not in ('NA','N/A','','NONE'):
                    try:
                        import urllib.request, tempfile
                        from reportlab.platypus import Image as RLImage
                        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                        urllib.request.urlretrieve(wl_logo, tmp.name)
                        img = RLImage(tmp.name, width=50*mm, height=10*mm, kind='proportional')
                        img.wrapOn(c, 50*mm, 12*mm)
                        img.drawOn(c, 14*mm, firm_y)
                    except:
                        c.setFillColor(WHITE)
                        c.setFont(FONT_SERIF_BOLD, 16)
                        c.drawString(14*mm, firm_y, prepared_by)
                else:
                    fn_text  = prepared_by if is_wl else 'FinReportAI'
                    fn_color = WHITE if is_wl else GOLD
                    c.setFillColor(fn_color)
                    c.setFont(FONT_SERIF_BOLD, 16)
                    c.drawString(14*mm, firm_y, fn_text)

                if has_tag:
                    c.setFillColor(colors.HexColor('#9BB5D4'))
                    c.setFont(FONT_SANS, 8.5)
                    c.drawString(14*mm, firm_y - 10*mm, wl_tagline)
                    rule_y = firm_y - 20*mm   # double rule below tagline
                else:
                    rule_y = firm_y - 12*mm   # double rule just below firm name

                c.setStrokeColor(colors.Color(14/255, 138/255, 122/255, 0.35))
                c.setLineWidth(0.5)
                c.line(14*mm, rule_y, pw - 8*mm, rule_y)
                c.setStrokeColor(colors.Color(201/255, 168/255, 76/255, 0.55))
                c.setLineWidth(0.8)
                c.line(14*mm, rule_y - 1.5*mm, pw - 8*mm, rule_y - 1.5*mm)

                # ── ZONE 2 — Content identifier (mid-upper) ───────────────
                accent_y = 185*mm
                c.setFillColor(GOLD)
                c.rect(14*mm, accent_y, 20*mm, 2, fill=1, stroke=0)

                pill_y = accent_y - 16*mm   # ~169mm
                c.setFillColor(TEAL)
                c.roundRect(14*mm, pill_y, 44*mm, 7*mm, 1.5*mm, fill=1, stroke=0)
                c.setFillColor(WHITE)
                c.setFont(FONT_SANS_BOLD, 6.5)
                c.drawCentredString(14*mm + 22*mm, pill_y + 2.5*mm, 'FINANCIAL REPORT')

                # ── ZONE 3 — Business name block (dominant, lower-middle) ──
                prep_y = pill_y - 20*mm     # ~149mm — PREPARED FOR label
                c.setFillColor(GOLD)
                c.setFont(FONT_SANS_BOLD, 7)
                c.drawString(14*mm, prep_y, 'PREPARED FOR')

                # Business name: font size scales down for long names
                bname_size = 30 if len(bname) <= 22 else (24 if len(bname) <= 32 else 19)
                bname_y = prep_y - 14*mm    # ~135mm — dominant text baseline
                c.setFillColor(WHITE)
                c.setFont(FONT_SERIF_BOLD, bname_size)
                c.drawString(14*mm, bname_y, bname)

                underline_y = bname_y - 8*mm  # ~127mm — gold underline
                c.setFillColor(GOLD)
                c.rect(14*mm, underline_y, 26*mm, 2.5, fill=1, stroke=0)

                period_y = underline_y - 13*mm  # ~114mm — period text
                c.setFillColor(colors.HexColor('#9BB5D4'))
                c.setFont(FONT_SERIF_IT, 13)
                c.drawString(14*mm, period_y, period)

                currency_y = period_y - 11*mm   # ~103mm — currency line
                c.setFillColor(colors.HexColor('#5B7A9A'))
                c.setFont(FONT_SANS, 8)
                c.drawString(14*mm, currency_y, 'Currency: GBP (\xa3)')

                # ── ZONE 4 — Report type badge ────────────────────────────
                period_lower = period.lower()
                if any(q in period_lower for q in ['q1','q2','q3','q4','quarter']):
                    badge_txt = 'QUARTERLY REPORT'
                elif 'annual' in period_lower or 'year' in period_lower or ('fy' in period_lower and len(period_lower) < 10):
                    badge_txt = 'ANNUAL REPORT'
                elif 'month' in period_lower or any(m in period_lower for m in ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']):
                    badge_txt = 'MONTHLY REPORT'
                elif 'vs ' in period_lower or ' vs ' in period_lower or 'comparison' in period_lower:
                    badge_txt = 'COMPARISON REPORT'
                else:
                    badge_txt = 'FINANCIAL REPORT'
                badge_w = min(len(badge_txt) * 2 + 8, 46) * mm
                badge_y = currency_y - 17*mm    # ~86mm
                c.setFillColor(GOLD)
                c.roundRect(14*mm, badge_y, badge_w, 6*mm, 1.2*mm, fill=1, stroke=0)
                c.setFillColor(NAVY)
                c.setFont(FONT_SANS_BOLD, 5.5)
                c.drawCentredString(14*mm + badge_w/2, badge_y + 2*mm, badge_txt)

                # ── ZONE 5 — CONFIDENTIAL badge ───────────────────────────
                conf_y = badge_y - 20*mm        # ~66mm
                c.setFillColor(GOLD)
                c.roundRect(14*mm, conf_y, 30*mm, 7*mm, 2*mm, fill=1, stroke=0)
                c.setFillColor(NAVY)
                c.setFont(FONT_SANS_BOLD, 6)
                c.drawCentredString(14*mm + 15*mm, conf_y + 2.5*mm, 'CONFIDENTIAL')

                # ── ZONE 6 — Bottom rule & ref ────────────────────────────
                c.setStrokeColor(colors.Color(14/255, 138/255, 122/255, 0.3))
                c.setLineWidth(0.5)
                c.line(0, 30*mm, pw, 30*mm)
                c.setFillColor(colors.HexColor('#5B7A9A'))
                c.setFont(FONT_SANS, 6)
                c.drawString(14*mm, 24*mm,
                    f'Ref: {report_ref}   \xb7   Prepared by {prepared_by}   \xb7   Confidential')

        return [CoverPage(), PageBreak()]
    except Exception:
        return []

# ── Table of contents ─────────────────────────────────────────────────────────

def toc_elements(sections, C_ACCENT):
    try:
        items = [
            Paragraph('Contents', s('toch', fontName=FONT_SANS_BOLD, fontSize=14, textColor=NAVY, leading=20)),
            Spacer(1, 5*mm),
        ]
        for i, sec in enumerate(sections, 1):
            row_t = Table([[
                Paragraph(str(i), s(f'tocn{i}', fontName=FONT_SANS_BOLD, fontSize=9, textColor=C_ACCENT, leading=15)),
                Paragraph(sec.replace('&','&amp;'), s(f'tocl{i}', fontSize=9, textColor=DARK, leading=15)),
            ]], colWidths=[10*mm, 165*mm])
            row_t.setStyle(TableStyle([
                ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
                ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
                ('LINEBELOW',(0,0),(-1,-1),0.3,BORDER),
            ]))
            items.append(row_t)
            items.append(Spacer(1,1*mm))
        items.append(PageBreak())
        return items
    except Exception:
        return []

# ── Glossary ──────────────────────────────────────────────────────────────────

def glossary_section(C_ACCENT, active_terms=None):
    try:
        core_names = {'Revenue', 'Gross Profit', 'Gross Margin', 'Net Profit', 'Net Margin'}
        all_terms = [
            ('Revenue', 'Total income from sales of goods or services before any costs are deducted.'),
            ('Cost of Goods Sold (COGS)', 'Direct costs tied to production — materials, direct labour, packaging.'),
            ('Gross Profit', 'Revenue minus COGS. Profitability before operating expenses.'),
            ('Gross Margin', 'Gross Profit as a percentage of Revenue. Indicates production efficiency.'),
            ('Operating Expenses (OpEx)', 'Costs of running the business not directly tied to production: rent, salaries, marketing, software.'),
            ('Net Profit', 'What remains after all costs (COGS and OpEx) are deducted from revenue. The bottom line.'),
            ('Net Margin', 'Net Profit as a percentage of Revenue. The core bottom-line profitability indicator.'),
            ('EBITDA', 'Earnings Before Interest, Tax, Depreciation and Amortisation. Core operational profitability.'),
            ('Working Capital', 'Current assets minus current liabilities. Measures short-term liquidity.'),
            ('Period-over-Period', 'Comparison between two equivalent time periods (e.g. Q1 2024 vs Q1 2025).'),
            ('Corporation Tax', 'UK tax on company profits. Main rate 25%. Small profits rate 19% (profits under £50,000).'),
        ]
        if active_terms is not None:
            active_lower = {a.lower() for a in active_terms}
            def _include(term_name):
                if term_name in core_names:
                    return True
                tn = term_name.lower()
                return any(key in tn or tn in key for key in active_lower)
            terms = [(t, defn) for t, defn in all_terms if _include(t)]
        else:
            terms = all_terms
        rows = [[Paragraph('Term', ST_TH_L), Paragraph('Definition', ST_TH_L)]]
        for i, (term, defn) in enumerate(terms):
            rows.append([
                Paragraph(term, s(f'gt{i}', fontName=FONT_SANS_BOLD, fontSize=8, textColor=NAVY, leading=13)),
                Paragraph(defn, s(f'gd{i}', fontSize=8, textColor=colors.HexColor('#374151'), leading=13)),
            ])
        t = Table(rows, colWidths=[60*mm, 115*mm], repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),NAVY),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE,OFFWHITE]),
            ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
            ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
            ('VALIGN',(0,0),(-1,-1),'TOP'),
            ('LINEBELOW',(0,0),(-1,0),1,TEAL),
        ]))
        return t
    except Exception:
        return None

def health_kpi_card(score):
    """Health score as a KPI card — coloured to match severity."""
    try:
        sv = clean(score)
        if sv is None: return None
        sv = max(1, min(10, sv))
        if sv >= 8:   tc, bg, label = GREEN_TEXT, GREEN_SOFT,  'Excellent'
        elif sv >= 5: tc, bg, label = AMBER_TEXT, AMBER_SOFT,  'Good'
        else:         tc, bg, label = RED_TEXT,   RED_SOFT,    'Needs Attention'
        val_s = s('hv', fontName=FONT_SERIF_BOLD, fontSize=17, textColor=tc, leading=21, alignment=TA_CENTER)
        lbl_s = s('hl', fontName=FONT_SANS, fontSize=7, textColor=tc, leading=9, alignment=TA_CENTER)
        sub_s = s('hs2', fontName=FONT_SANS_BOLD, fontSize=7.5, textColor=tc, leading=10, alignment=TA_CENTER)
        empty_s = s('hke', fontSize=7, leading=9, alignment=TA_CENTER)
        data = [
            [Paragraph(f'{sv:.0f}/10', val_s)],
            [Paragraph('Health Score', lbl_s)],
            [Paragraph(label, sub_s)],
            [Paragraph('', empty_s)],
        ]
        t = Table(data, colWidths=[38*mm])
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,-1), bg),
            ('BOX',(0,0),(-1,-1), 0.75, tc),
            ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
            ('LEFTPADDING',(0,0),(-1,-1),2),('RIGHTPADDING',(0,0),(-1,-1),2),
        ]))
        return t
    except Exception:
        return None

# ── Health score gauge ────────────────────────────────────────────────────────

def health_score_section(score, C_ACCENT):
    """Draw a speedometer-style gauge showing health score 1-10."""
    try:
        import math
        score_val = clean(score)
        if score_val is None: return None
        score_val = max(1, min(10, score_val))

        w, h = 90, 56
        dw = Drawing(w*mm, h*mm)

        # Centre high so the downward arc fits
        cx = (w/2)*mm
        cy = 40*mm
        r  = 30*mm
        stroke_w = 9
        steps = 80

        if score_val <= 3:   fill_col = RED_TEXT
        elif score_val <= 6: fill_col = colors.HexColor('#D97706')
        else:                fill_col = GREEN_TEXT

        filled     = score_val / 10
        fill_steps = int(steps * filled)

        # Gray background arc (pi → 2pi = left, down, right)
        for i in range(steps):
            a1 = math.pi + (i/steps)*math.pi
            a2 = math.pi + ((i+1)/steps)*math.pi
            x1 = cx + r*math.cos(a1); y1 = cy + r*math.sin(a1)
            x2 = cx + r*math.cos(a2); y2 = cy + r*math.sin(a2)
            dw.add(Line(x1,y1,x2,y2, strokeColor=BORDER, strokeWidth=stroke_w+2, strokeLineCap=1))

        # Coloured filled arc
        for i in range(fill_steps):
            a1 = math.pi + (i/steps)*math.pi
            a2 = math.pi + ((i+1)/steps)*math.pi
            x1 = cx + r*math.cos(a1); y1 = cy + r*math.sin(a1)
            x2 = cx + r*math.cos(a2); y2 = cy + r*math.sin(a2)
            dw.add(Line(x1,y1,x2,y2, strokeColor=fill_col, strokeWidth=stroke_w, strokeLineCap=1))

        # Needle — thin line with a clean circle pivot
        needle_angle = math.pi + filled*math.pi
        nx = cx + (r-6*mm)*math.cos(needle_angle)
        ny = cy + (r-6*mm)*math.sin(needle_angle)
        dw.add(Line(cx, cy, nx, ny, strokeColor=NAVY, strokeWidth=1.5, strokeLineCap=1))
        dw.add(Rect(cx-3, cy-3, 6, 6, fillColor=NAVY, strokeColor=WHITE, strokeWidth=1))

        # Score value only — no label inside the wheel
        dw.add(String(cx, cy+5*mm, f'{score_val:.0f}/10',
                     fontSize=20, fillColor=fill_col, textAnchor='middle', fontName=FONT_SERIF_BOLD))

        return dw
    except Exception:
        return None

# ── Traffic light dashboard ───────────────────────────────────────────────────

def traffic_light_dashboard(d, C_ACCENT, period_revs=None):
    """3-column grid of RAG metric indicators."""
    try:
        def tl_card(name, value_str, status, color):
            name_s = s(f'tln{name}', fontSize=7, textColor=GRAY, leading=10)
            val_s  = s(f'tlv{name}', fontName=FONT_SANS_BOLD, fontSize=10, textColor=DARK, leading=13, alignment=TA_CENTER)
            st_s   = s(f'tls{name}', fontName=FONT_SANS_BOLD, fontSize=7, textColor=color, leading=10, alignment=TA_CENTER)
            cw = 175*mm / 3
            t = Table([
                [Paragraph(name, name_s)],
                [Paragraph(value_str, val_s)],
                [Paragraph(f'● {status}', st_s)],
            ], colWidths=[cw])
            t.setStyle(TableStyle([
                ('BOX',          (0,0),(-1,-1), 0.5,  BORDER),
                ('BACKGROUND',   (0,0),(-1,-1), OFFWHITE),
                ('LINEABOVE',    (0,0),(-1,0),  2,    color),
                ('TOPPADDING',   (0,0),(-1,-1), 5),
                ('BOTTOMPADDING',(0,0),(-1,-1), 5),
                ('LEFTPADDING',  (0,0),(-1,-1), 6),
                ('RIGHTPADDING', (0,0),(-1,-1), 6),
            ]))
            return t

        cards = []

        # Revenue Trend
        if period_revs:
            pr = [clean(v) for v in period_revs if clean(v) is not None]
            if len(pr) >= 2 and pr[0]:
                pct = (pr[-1] - pr[0]) / abs(pr[0]) * 100
                if pct >= 5:
                    cards.append(tl_card('Revenue Trend', f'▲ {abs(pct):.1f}%', 'Growing', GREEN_TEXT))
                elif pct <= -5:
                    cards.append(tl_card('Revenue Trend', f'▼ {abs(pct):.1f}%', 'Declining', RED_TEXT))
                else:
                    cards.append(tl_card('Revenue Trend', f'≈ {pct:+.1f}%', 'Stable', AMBER_TEXT))

        # Gross Margin vs 60% benchmark
        gm = clean(d.get('gross_margin'))
        if gm is not None:
            gm100 = gm if gm > 1 else gm * 100
            if gm100 >= 60:
                cards.append(tl_card('Gross Margin', fmtp(gm), 'Strong', GREEN_TEXT))
            elif gm100 >= 40:
                cards.append(tl_card('Gross Margin', fmtp(gm), 'Moderate', AMBER_TEXT))
            else:
                cards.append(tl_card('Gross Margin', fmtp(gm), 'Low', RED_TEXT))

        # Net Margin vs 10% benchmark
        nm = clean(d.get('net_margin'))
        if nm is not None:
            nm100 = nm if nm > 1 else nm * 100
            if nm100 >= 10:
                cards.append(tl_card('Net Margin', fmtp(nm), 'Healthy', GREEN_TEXT))
            elif nm100 >= 5:
                cards.append(tl_card('Net Margin', fmtp(nm), 'Watch', AMBER_TEXT))
            else:
                cards.append(tl_card('Net Margin', fmtp(nm), 'Low', RED_TEXT))

        # OpEx Control vs 40% of revenue
        opex_v = clean(d.get('total_opex'))
        rev_v  = clean(d.get('total_revenue'))
        if opex_v is not None and rev_v and rev_v > 0:
            op_pct = opex_v / rev_v * 100
            if op_pct <= 40:
                cards.append(tl_card('OpEx Control', f'{op_pct:.1f}% of rev', 'Controlled', GREEN_TEXT))
            elif op_pct <= 55:
                cards.append(tl_card('OpEx Control', f'{op_pct:.1f}% of rev', 'Watch', AMBER_TEXT))
            else:
                cards.append(tl_card('OpEx Control', f'{op_pct:.1f}% of rev', 'High', RED_TEXT))

        # Cash Position
        cash_op = clean(d.get('cash_operating'))
        if cash_op is not None:
            if cash_op >= 0:
                cards.append(tl_card('Cash (Operating)', fmt(cash_op), 'Positive', GREEN_TEXT))
            else:
                cards.append(tl_card('Cash (Operating)', fmt(cash_op), 'Negative', RED_TEXT))

        # Health Score
        hs = clean(d.get('health_score'))
        if hs is not None:
            hs = max(1, min(10, hs))
            if hs >= 8:
                cards.append(tl_card('Health Score', f'{hs:.0f}/10', 'Excellent', GREEN_TEXT))
            elif hs >= 5:
                cards.append(tl_card('Health Score', f'{hs:.0f}/10', 'Good', AMBER_TEXT))
            else:
                cards.append(tl_card('Health Score', f'{hs:.0f}/10', 'Review', RED_TEXT))

        if not cards:
            return None

        # Pad to multiple of 3 with empty spacers
        cw = 175*mm / 3
        while len(cards) % 3 != 0:
            cards.append(Spacer(cw, 1))

        rows = [cards[i:i+3] for i in range(0, len(cards), 3)]
        grid = Table(rows, colWidths=[cw] * 3)
        grid.setStyle(TableStyle([
            ('LEFTPADDING',  (0,0),(-1,-1), 2),
            ('RIGHTPADDING', (0,0),(-1,-1), 2),
            ('TOPPADDING',   (0,0),(-1,-1), 2),
            ('BOTTOMPADDING',(0,0),(-1,-1), 2),
            ('VALIGN',       (0,0),(-1,-1), 'TOP'),
        ]))
        return grid
    except Exception:
        return None


# ── Management summary box ────────────────────────────────────────────────────

def management_summary_box(d, C_ACCENT):
    """KEY TAKEAWAYS box with first 3 recommendations as bullets."""
    try:
        recs = d.get('key_takeaways')
        if not recs:
            return None
        if isinstance(recs, str):
            try:
                recs = json.loads(recs)
            except Exception:
                recs = [r.strip() for r in recs.split('|') if r.strip()]
        if not recs or not isinstance(recs, list):
            return None
        bullets = []
        for rec in recs[:3]:
            text = str(rec).strip()
            # Truncate to first sentence
            for sep in ['. ', '! ', '? ']:
                idx = text.find(sep)
                if 0 < idx < len(text) - 1:
                    text = text[:idx + 1]
                    break
            # Cap at 80 chars so Key Takeaways always reads shorter than full Recommendations
            if len(text) > 80:
                text = text[:77].rstrip() + '...'
            if text:
                bullets.append(text)
        if not bullets:
            return None
        hdr_s = s('msh', fontName=FONT_SANS_BOLD, fontSize=8, textColor=WHITE, leading=11)
        bul_s = s('msb', fontName=FONT_SANS, fontSize=8.5, textColor=DARK, leading=13)
        rows = [[Paragraph('KEY TAKEAWAYS', hdr_s)]]
        for b in bullets:
            rows.append([Paragraph(f'→  {b}', bul_s)])
        t = Table(rows, colWidths=[175*mm])
        style = [
            ('BACKGROUND',    (0,0),(-1,0),  NAVY),
            ('BACKGROUND',    (0,1),(-1,-1), OFFWHITE),
            ('BOX',           (0,0),(-1,-1), 0.75, C_ACCENT),
            ('LINEBEFORE',    (0,0),(0,-1),  3,    C_ACCENT),
            ('TOPPADDING',    (0,0),(-1,-1), 6),
            ('BOTTOMPADDING', (0,0),(-1,-1), 6),
            ('LEFTPADDING',   (0,0),(-1,0),  8),
            ('LEFTPADDING',   (0,1),(-1,-1), 12),
            ('RIGHTPADDING',  (0,0),(-1,-1), 8),
        ]
        for r in range(1, len(rows) - 1):
            style.append(('LINEBELOW', (0,r),(-1,r), 0.3, BORDER))
        t.setStyle(TableStyle(style))
        return t
    except Exception:
        return None


# ── Since last period banner ──────────────────────────────────────────────────

def since_last_period_banner(d, C_ACCENT):
    """Slim navy banner showing 3 headline changes vs previous period."""
    try:
        def compute(curr, prev, is_pct=False):
            cv, pv = clean(curr), clean(prev)
            if cv is None or pv is None:
                return None, GRAY
            if is_pct:
                cv2 = cv if cv > 1 else cv * 100
                pv2 = pv if pv > 1 else pv * 100
                diff = cv2 - pv2
                arrow = '▲' if diff >= 0 else '▼'
                col = GREEN_TEXT if diff >= 0 else RED_TEXT
                return f'{arrow} {abs(diff):.1f}pp', col
            else:
                if pv == 0:
                    return None, GRAY
                pct = (cv - pv) / abs(pv) * 100
                arrow = '▲' if pct >= 0 else '▼'
                col = GREEN_TEXT if pct >= 0 else RED_TEXT
                return f'{arrow} {abs(pct):.1f}%', col

        rev_str, rev_col = compute(d.get('total_revenue'), d.get('prev_total_revenue'))
        np_str,  np_col  = compute(d.get('net_profit'),    d.get('prev_net_profit'))
        gm_str,  gm_col  = compute(d.get('gross_margin'),  d.get('prev_gross_margin'), is_pct=True)

        if not any([rev_str, np_str, gm_str]):
            return None

        lbl_s = s('slbl', fontSize=6.5, textColor=colors.HexColor('#9BB5D4'), leading=9, alignment=TA_CENTER)
        cw = 175*mm / 3

        def metric_cell(label, val_str, col):
            vs = val_str or '—'
            val_s = s(f'sv{label}', fontName=FONT_SANS_BOLD, fontSize=12, textColor=col, leading=15, alignment=TA_CENTER)
            ct = Table([[Paragraph(label, lbl_s)], [Paragraph(vs, val_s)]], colWidths=[cw])
            ct.setStyle(TableStyle([
                ('TOPPADDING',   (0,0),(-1,-1), 5),
                ('BOTTOMPADDING',(0,0),(-1,-1), 5),
                ('LEFTPADDING',  (0,0),(-1,-1), 2),
                ('RIGHTPADDING', (0,0),(-1,-1), 2),
            ]))
            return ct

        cells = [
            metric_cell('Revenue',      rev_str, rev_col),
            metric_cell('Net Profit',   np_str,  np_col),
            metric_cell('Gross Margin', gm_str,  gm_col),
        ]
        hdr_s = s('slhdr', fontName=FONT_SANS_BOLD, fontSize=6.5,
                  textColor=colors.HexColor('#9BB5D4'), leading=9)
        banner = Table(
            [[Paragraph('SINCE LAST PERIOD', hdr_s), '', ''], cells],
            colWidths=[cw] * 3,
        )
        banner.setStyle(TableStyle([
            ('BACKGROUND',   (0,0),(-1,-1), NAVY),
            ('SPAN',         (0,0),(-1,0)),
            ('TOPPADDING',   (0,0),(-1,0),  5),
            ('BOTTOMPADDING',(0,0),(-1,0),  3),
            ('LEFTPADDING',  (0,0),(-1,0),  8),
            ('RIGHTPADDING', (0,0),(-1,0),  8),
            ('TOPPADDING',   (0,1),(-1,1),  0),
            ('BOTTOMPADDING',(0,1),(-1,1),  0),
            ('LEFTPADDING',  (0,1),(-1,1),  0),
            ('RIGHTPADDING', (0,1),(-1,1),  0),
            ('LINEAFTER',    (0,1),(1,1),   0.3, colors.HexColor('#2D4A7A')),
        ]))
        return banner
    except Exception:
        return None


# ── Recommendations section ───────────────────────────────────────────────────

def recommendations_elements(recommendations, C_ACCENT):
    """Numbered action-item cards from recommendations list."""
    try:
        if isinstance(recommendations, str):
            try: recommendations = json.loads(recommendations)
            except:
                recommendations = [r.strip() for r in recommendations.split('|') if r.strip()]
        if not recommendations: return []

        items = []
        for i, rec in enumerate(recommendations[:5], 1):
            num_s = s(f'rn{i}', fontName=FONT_SERIF_BOLD, fontSize=14, textColor=C_ACCENT,
                      leading=18, alignment=TA_CENTER)
            txt_s = s(f'rt{i}', fontName=FONT_SANS, fontSize=8.5, textColor=DARK, leading=13)
            row = Table([[
                Paragraph(str(i), num_s),
                Paragraph(str(rec), txt_s),
            ]], colWidths=[12*mm, 163*mm])
            row.setStyle(TableStyle([
                ('VALIGN',(0,0),(-1,-1),'TOP'),
                ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
                ('LEFTPADDING',(0,0),(0,0),0),('RIGHTPADDING',(0,0),(0,0),6),
                ('LEFTPADDING',(1,0),(1,0),8),
                ('LINEBELOW',(0,0),(-1,-1),0.3,BORDER),
            ]))
            items.append(row)
            items.append(Spacer(1, 1*mm))
        return items
    except Exception:
        return []

# ── Forecast section ──────────────────────────────────────────────────────────

def forecast_section(d, C_ACCENT):
    """Next period revenue + profit projection cards with narrative."""
    try:
        f_period  = str(d.get('forecast_period','')).strip()
        f_rev     = clean(d.get('forecast_revenue'))
        f_profit  = clean(d.get('forecast_profit'))
        f_text    = str(d.get('forecast_narrative','')).strip()

        if not f_period and not f_rev and not f_text:
            return []

        curr_rev = clean(d.get('total_revenue'))
        curr_np  = clean(d.get('net_profit'))

        items = []

        if f_rev or f_profit:
            cards = []
            if f_rev:
                growth = ((f_rev - curr_rev)/curr_rev*100) if curr_rev else None
                sub = f'+{growth:.1f}% vs current' if growth and growth >= 0 else (f'{growth:.1f}% vs current' if growth else '')
                cards.append(kpi_card(fmt(f_rev), f'Projected Revenue', f_period or 'Next Period'))
            if f_profit:
                cards.append(kpi_card(fmt(f_profit), f'Projected Net Profit', f_period or 'Next Period'))
            if cards:
                total_w = 38*mm * len(cards) + 2*mm * (len(cards)-1)
                pad = (175*mm - total_w) / 2
                row = Table([[Spacer(pad,1)] + cards + [Spacer(pad,1)]],
                            colWidths=[pad] + [38*mm]*len(cards) + [pad])
                row.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),1),('RIGHTPADDING',(0,0),(-1,-1),1),
                                         ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
                items += [row, Spacer(1,4*mm)]

        if f_text:
            items.append(Paragraph(f_text, ST_BODY))

        return items
    except Exception:
        return []

# ── Cash flow section ─────────────────────────────────────────────────────────

def cash_flow_section(d, C_ACCENT, ncols=1):
    """Simple 3-line cash flow summary: operating, investing, financing."""
    try:
        op  = clean(d.get('cash_operating'))
        inv = clean(d.get('cash_investing'))
        fin = clean(d.get('cash_financing'))
        net = clean(d.get('net_cash'))

        if op is None and inv is None and fin is None and net is None:
            return None

        if net is None and op is not None:
            net = (op or 0) + (inv or 0) + (fin or 0)

        def cf_row(label, val, indent=False):
            col = GREEN_TEXT if (val or 0) >= 0 else RED_TEXT
            prefix = '    ' if indent else ''
            v = clean(val)
            if v is not None:
                display = fmt(abs(v)) if v >= 0 else f'({fmt(abs(v))})'
            else:
                display = '—'
            return [
                Paragraph(prefix+label, s(f'cfl{label}', fontName=FONT_SANS, fontSize=8, textColor=DARK, leading=12)),
                Paragraph(display,
                         s(f'cfv{label}', fontName=FONT_SANS_BOLD if not indent else FONT_SANS,
                           fontSize=8, textColor=col, leading=12, alignment=TA_RIGHT)),
            ]

        rows = [
            [Paragraph('Activity', ST_TH_L), Paragraph('Amount', ST_TH)],
        ]
        if op  is not None: rows.append(cf_row('Operating Activities', op))
        if inv is not None: rows.append(cf_row('Investing Activities', inv))
        if fin is not None: rows.append(cf_row('Financing Activities', fin))

        net_row = [
            Paragraph('Net Cash Movement', s('cfn', fontName=FONT_SANS_BOLD, fontSize=9, textColor=NAVY, leading=13)),
            Paragraph(fmt(net) if net is not None else '—',
                     s('cfnv', fontName=FONT_SERIF_BOLD, fontSize=9,
                       textColor=GREEN_TEXT if (net or 0) >= 0 else RED_TEXT,
                       leading=13, alignment=TA_RIGHT)),
        ]
        rows.append(net_row)

        # Cash runway estimate
        if op is not None and op > 0:
            try:
                assets_v = clean(d.get('total_assets'))
                opex_v   = clean(d.get('total_opex'))
                n = max(ncols, 1)
                if opex_v and opex_v > 0 and assets_v and assets_v > 0:
                    monthly_burn = opex_v / n
                    runway = assets_v / monthly_burn
                    if runway > 6:
                        rw_col, rw_str = GREEN_TEXT, f'{runway:.0f} months'
                    elif runway >= 3:
                        rw_col, rw_str = AMBER_TEXT, f'{runway:.0f} months'
                    else:
                        rw_col, rw_str = RED_TEXT, f'{runway:.1f} months'
                else:
                    rw_col, rw_str = GRAY, 'Insufficient data'
            except Exception:
                rw_col, rw_str = GRAY, 'Insufficient data'
            rows.append([
                Paragraph('Estimated Cash Runway',
                          s('cfrl', fontName=FONT_SANS, fontSize=8, textColor=GRAY, leading=12)),
                Paragraph(rw_str,
                          s('cfrv', fontName=FONT_SANS_BOLD, fontSize=8,
                            textColor=rw_col, leading=12, alignment=TA_RIGHT)),
            ])

        t = Table(rows, colWidths=[130*mm, 45*mm], repeatRows=1)
        n_data_rows = len(rows) - 1
        t.setStyle(TableStyle([
            ('BACKGROUND',   (0,0), (-1,0),  NAVY),
            ('ROWBACKGROUNDS',(0,1),(-1,n_data_rows),[WHITE,OFFWHITE]),
            ('BACKGROUND',   (0,-1),(-1,-1), TEAL_LITE),
            ('LINEABOVE',    (0,-1),(-1,-1), 1.5, NAVY),
            ('TOPPADDING',   (0,0), (-1,-1), 5),
            ('BOTTOMPADDING',(0,0), (-1,-1), 5),
            ('LEFTPADDING',  (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
        ]))
        return t
    except Exception:
        return None

# ── Balance sheet snapshot ────────────────────────────────────────────────────

def balance_sheet_section(d, C_ACCENT):
    """Assets / Liabilities / Equity snapshot."""
    try:
        assets   = clean(d.get('total_assets'))
        curr_a   = clean(d.get('current_assets'))
        liab     = clean(d.get('total_liabilities'))
        curr_l   = clean(d.get('current_liabilities'))
        equity   = clean(d.get('total_equity'))

        if assets is None and liab is None and equity is None:
            return None

        # Auto-calc equity if missing
        if equity is None and assets is not None and liab is not None:
            equity = assets - liab

        # Current ratio
        curr_ratio = (curr_a / curr_l) if curr_a and curr_l and curr_l > 0 else None

        rows = [[Paragraph('Balance Sheet Item', ST_TH_L), Paragraph('Value', ST_TH)]]

        def bs_row(label, val, bold=False):
            ls = s(f'bs{label}', fontName=FONT_SANS_BOLD if bold else FONT_SANS,
                   fontSize=8, textColor=NAVY if bold else DARK, leading=12)
            vs = s(f'bsv{label}', fontName=FONT_SANS_BOLD if bold else FONT_SANS,
                   fontSize=8, textColor=NAVY if bold else DARK, leading=12, alignment=TA_RIGHT)
            rows.append([Paragraph(label, ls), Paragraph(fmt(val) if val is not None else '—', vs)])

        if curr_a  is not None: bs_row('Current Assets', curr_a)
        if assets  is not None: bs_row('Total Assets', assets, bold=True)
        if curr_l  is not None: bs_row('Current Liabilities', curr_l)
        if liab    is not None: bs_row('Total Liabilities', liab, bold=True)
        if equity  is not None: bs_row('Shareholders Equity', equity, bold=True)
        if curr_ratio is not None:
            rows.append([
                Paragraph('Current Ratio', s('crt', fontName=FONT_SANS, fontSize=8, textColor=GRAY, leading=12)),
                Paragraph(f'{curr_ratio:.2f}x',
                         s('crv', fontName=FONT_SANS_BOLD, fontSize=8,
                           textColor=GREEN_TEXT if curr_ratio >= 1.5 else (AMBER_TEXT if curr_ratio >= 1 else RED_TEXT),
                           leading=12, alignment=TA_RIGHT)),
            ])

        t = Table(rows, colWidths=[130*mm, 45*mm], repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),NAVY),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE,OFFWHITE]),
            ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
            ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('LINEBELOW',(0,0),(-1,0),1,C_ACCENT),
        ]))
        return t
    except Exception:
        return None

# ── Goals & targets ───────────────────────────────────────────────────────────

def goals_section(goals_raw, d, C_ACCENT):
    """RAG status table comparing targets vs actuals."""
    try:
        if isinstance(goals_raw, str):
            try: goals = json.loads(goals_raw)
            except: return None
        else:
            goals = goals_raw
        if not goals or not isinstance(goals, list): return None

        rows = [[
            Paragraph('Goal / KPI', ST_TH_L),
            Paragraph('Target', ST_TH),
            Paragraph('Actual', ST_TH),
            Paragraph('Status', ST_TH),
        ]]

        for g in goals:
            label  = str(g.get('label',''))
            target = clean(g.get('target'))
            actual = clean(g.get('actual'))
            is_pct = g.get('is_pct', False)

            if target is None: continue

            def fv(v): return fmtp(v) if is_pct else fmt(v)

            if actual is not None and target > 0:
                ratio = actual / target
                if ratio >= 0.95:   status, col, bg = 'On Track', GREEN_TEXT, GREEN_SOFT
                elif ratio >= 0.80: status, col, bg = 'Watch',    AMBER_TEXT, AMBER_SOFT
                else:               status, col, bg = 'Behind',   RED_TEXT,   RED_SOFT
            else:
                status, col, bg = 'No Data', GRAY, OFFWHITE

            status_para = Paragraph(status, s(f'gs{label}', fontName=FONT_SANS_BOLD, fontSize=8,
                                              textColor=col, alignment=TA_RIGHT, leading=11))
            rows.append([
                Paragraph(label, ST_TD_L),
                Paragraph(fv(target) if target is not None else '—', ST_TD),
                Paragraph(fv(actual) if actual is not None else '—', ST_TD),
                status_para,
            ])

        t = Table(rows, colWidths=[70*mm, 35*mm, 35*mm, 35*mm], repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),NAVY),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE,OFFWHITE]),
            ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
            ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('LINEBELOW',(0,0),(-1,0),1,C_ACCENT),
        ]))
        return t
    except Exception:
        return None

# ── Accountant notes box ──────────────────────────────────────────────────────

def accountant_notes_element(notes, C_ACCENT):
    """Styled box for accountant's own commentary."""
    try:
        if not notes or str(notes).strip().upper() in ('NA','N/A','NONE',''): return None
        note_s = s('an', fontName=FONT_SANS, fontSize=9, textColor=DARK, leading=14)
        t = Table([
            [Paragraph(str(notes), note_s)],
        ], colWidths=[175*mm])
        t.setStyle(TableStyle([
            ('BOX',(0,0),(-1,-1),1,C_ACCENT),
            ('LINEBEFORE',(0,0),(0,-1),4,C_ACCENT),
            ('BACKGROUND',(0,0),(-1,-1),TEAL_LITE),
            ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),
            ('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),8),
        ]))
        return t
    except Exception:
        return None

# ── Questions to discuss ──────────────────────────────────────────────────────

def questions_section(d, C_ACCENT):
    """Teal-bordered box with 3 discussion questions."""
    try:
        dq = d.get('discussion_questions')
        if dq:
            if isinstance(dq, str):
                try: dq = json.loads(dq)
                except Exception: dq = [q.strip() for q in dq.split('|') if q.strip()]
        if not dq or not isinstance(dq, list) or not any(str(q).strip() for q in dq):
            # Auto-generate from available data
            dq = []
            nm = clean(d.get('net_margin'))
            if nm is not None and (nm if nm > 1 else nm * 100) < 15:
                dq.append('What specific cost reduction opportunities are available to improve net margin?')
            raw_flags = str(d.get('flags', ''))
            risk_count = sum(1 for f in raw_flags.replace('FLAGSEP', '\n').split('\n')
                             if '|' in f and f.split('|')[0].strip().upper() == 'RISK')
            if risk_count > 0:
                dq.append('What immediate actions are planned to address the risk items identified in this report?')
            opex_v = clean(d.get('total_opex'))
            rev_v  = clean(d.get('total_revenue'))
            if opex_v and rev_v and rev_v > 0 and opex_v / rev_v > 0.5:
                dq.append('How can operating expenses be optimised relative to revenue over the next period?')
            if not dq:
                dq = [
                    'What are the key priorities for the next financial period?',
                    'Are there any upcoming capital expenditure plans that may impact cash flow?',
                    'Are there opportunities to improve gross margin through pricing or cost management?',
                ]
        dq = [str(q).strip() for q in dq if str(q).strip()][:3]
        if not dq:
            return None
        hdr_s = s('qhdr', fontName=FONT_SANS_BOLD, fontSize=8, textColor=WHITE, leading=11)
        q_s   = s('qbody', fontName=FONT_SANS, fontSize=8.5, textColor=DARK, leading=13)
        rows  = [[Paragraph('QUESTIONS TO DISCUSS', hdr_s)]]
        for i, q in enumerate(dq, 1):
            rows.append([Paragraph(f'{i}.  {q}', q_s)])
        t = Table(rows, colWidths=[175*mm])
        style = [
            ('BACKGROUND',   (0,0),(-1,0),  C_ACCENT),
            ('BACKGROUND',   (0,1),(-1,-1), TEAL_LITE),
            ('BOX',          (0,0),(-1,-1), 0.75, C_ACCENT),
            ('TOPPADDING',   (0,0),(-1,-1), 7),
            ('BOTTOMPADDING',(0,0),(-1,-1), 7),
            ('LEFTPADDING',  (0,0),(-1,0),  8),
            ('LEFTPADDING',  (0,1),(-1,-1), 12),
            ('RIGHTPADDING', (0,0),(-1,-1), 8),
        ]
        for r in range(1, len(rows) - 1):
            style.append(('LINEBELOW', (0,r), (-1,r), 0.3, C_ACCENT))
        t.setStyle(TableStyle(style))
        return t
    except Exception:
        return None


# ── Key wins section ──────────────────────────────────────────────────────────

def key_wins_section(flag_lines, C_ACCENT):
    """Green-accented box listing POSITIVE flags as wins."""
    try:
        wins = []
        for fl in flag_lines:
            parts = fl.split('|')
            if len(parts) >= 3 and parts[0].strip().upper() == 'POSITIVE':
                wins.append({'title': parts[1].strip(), 'body': parts[2].strip()})
        if not wins:
            return None
        hdr_s = s('kwh', fontName=FONT_SANS_BOLD, fontSize=8, textColor=WHITE, leading=11)
        win_s = s('kwb', fontName=FONT_SANS, fontSize=8.5, textColor=DARK, leading=13)
        rows  = [[Paragraph('KEY WINS THIS PERIOD', hdr_s)]]
        for w in wins:
            rows.append([Paragraph(f'✓  <b>{w["title"]}</b>  — {w["body"]}', win_s)])
        t = Table(rows, colWidths=[175*mm])
        style = [
            ('BACKGROUND',   (0,0),(-1,0),  GREEN_TEXT),
            ('BACKGROUND',   (0,1),(-1,-1), GREEN_SOFT),
            ('BOX',          (0,0),(-1,-1), 0.75, GREEN_TEXT),
            ('TOPPADDING',   (0,0),(-1,-1), 6),
            ('BOTTOMPADDING',(0,0),(-1,-1), 6),
            ('LEFTPADDING',  (0,0),(-1,0),  8),
            ('LEFTPADDING',  (0,1),(-1,-1), 12),
            ('RIGHTPADDING', (0,0),(-1,-1), 8),
        ]
        for r in range(1, len(rows) - 1):
            style.append(('LINEBELOW', (0,r), (-1,r), 0.3, GREEN_TEXT))
        t.setStyle(TableStyle(style))
        return t
    except Exception:
        return None


# ── Break-even calculator ─────────────────────────────────────────────────────

def breakeven_section(d, C_ACCENT):
    """3-row break-even table: fixed costs, gross margin, break-even revenue."""
    try:
        opex_v = clean(d.get('total_opex'))
        gm_v   = clean(d.get('gross_margin'))
        if opex_v is None or gm_v is None or opex_v <= 0:
            return None
        gm_dec = gm_v / 100 if gm_v > 1 else gm_v
        if gm_dec <= 0:
            return None
        be_rev = opex_v / gm_dec
        be_bold_s = s('beb', fontName=FONT_SANS_BOLD, fontSize=8, textColor=NAVY, leading=11)
        be_boldr_s = s('bebr', fontName=FONT_SANS_BOLD, fontSize=8, textColor=NAVY, leading=11, alignment=TA_RIGHT)
        note_s = s('ben', fontSize=7.5, textColor=GRAY, leading=11)
        rows = [
            [Paragraph('Item', ST_TH_L), Paragraph('Value', ST_TH)],
            [Paragraph('Fixed Operating Costs', ST_TD_L), Paragraph(fmt(opex_v), ST_TD)],
            [Paragraph('Gross Margin', ST_TD_L), Paragraph(fmtp(gm_v), ST_TD)],
            [Paragraph('Break-Even Revenue Required', be_bold_s), Paragraph(fmt(be_rev), be_boldr_s)],
            [Paragraph(f'Revenue above {fmt(be_rev)} generates profit.', note_s), ''],
        ]
        t = Table(rows, colWidths=[130*mm, 45*mm])
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,0),  NAVY),
            ('ROWBACKGROUNDS',(0,1), (-1,2),  [WHITE, OFFWHITE]),
            ('BACKGROUND',    (0,3), (-1,3),  TEAL_LITE),
            ('LINEABOVE',     (0,3), (-1,3),  1.5, NAVY),
            ('BACKGROUND',    (0,4), (-1,4),  OFFWHITE),
            ('SPAN',          (0,4), (-1,4)),
            ('TOPPADDING',    (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING',   (0,0), (-1,-1), 8),
            ('RIGHTPADDING',  (0,0), (-1,-1), 8),
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            ('LINEBELOW',     (0,0), (-1,0),  1, C_ACCENT),
        ]))
        return t
    except Exception:
        return None


# ── Assumptions & Limitations section ────────────────────────────────────────

def assumptions_section(C_ACCENT):
    """Static gray-bordered box with disclaimer text."""
    try:
        text = (
            'This report is based solely on the financial data provided and has not been independently verified. '
            'Forecasts are estimates based on historical trends and should not be relied upon as guarantees of '
            'future performance. Corporation tax estimates are indicative only — consult your accountant '
            'for exact liability. All figures are presented in GBP and are unaudited unless otherwise stated.'
        )
        t = Table([[Paragraph(text, s('asn', fontSize=8, textColor=GRAY, leading=13))]], colWidths=[175*mm])
        t.setStyle(TableStyle([
            ('BOX',           (0,0),(-1,-1), 0.5,  BORDER),
            ('BACKGROUND',    (0,0),(-1,-1), OFFWHITE),
            ('TOPPADDING',    (0,0),(-1,-1), 8),
            ('BOTTOMPADDING', (0,0),(-1,-1), 8),
            ('LEFTPADDING',   (0,0),(-1,-1), 10),
            ('RIGHTPADDING',  (0,0),(-1,-1), 10),
        ]))
        return t
    except Exception:
        return None


# ── Dynamic P&L table ─────────────────────────────────────────────────────────

def pl_table(d, periods, periods_keys, revenue_items, cogs_items, opex_items, periods_full=None):
    ncols = len(periods)
    show_periods = ncols > 0

    def th(txt, right=True): return Paragraph(txt, ST_TH if right else ST_TH_L)
    def td(txt, right=True): return Paragraph(str(txt), ST_TD if right else ST_TD_L)
    def money(v, bold=False): return Paragraph(fmt(v), ST_BOLD_R if bold else ST_TD)
    def label(txt, indent=False, bold=False, sub=False):
        p='    ' if indent else ''
        st=ST_BOLD if bold else (s('sub',fontSize=7.5,textColor=GRAY,leading=11) if sub else ST_TD_L)
        return Paragraph(p+str(txt),st)
    def cat(txt):
        _sp = s('sp', fontSize=2, leading=2)
        return [Paragraph(txt,s('cat',fontName=FONT_SANS_BOLD,fontSize=7.5,textColor=TEAL,leading=11))] + [Paragraph('', _sp)]*(ncols+2)
    def blank():
        _sp = s('sp', fontSize=2, leading=2)
        return [Paragraph('', _sp)] + [Paragraph('', _sp)] * (ncols + 2)

    hdr = [th('', False)]
    for p in periods: hdr.append(th(normalise_period_label(p)))
    hdr.append(th('Total'))
    hdr.append(th('Avg'))

    def item_row(item, bold=False, indent=True, lbl_override=None):
        vals = item.get('values', [])
        row = [lbl_override if lbl_override is not None else label(item.get('label','—'), indent=indent, bold=bold)]
        for i in range(ncols):
            v = vals[i] if i < len(vals) else None
            if bold and not has_val(v):
                row.append(Paragraph('—', ST_BOLD_R if bold else ST_TD))
            else:
                row.append(money(v, bold))
        _vsum    = sum(clean(v) or 0 for v in vals) if vals else 0
        _raw_tot = clean(item.get('total'))
        total_v  = (_raw_tot
                    if _raw_tot is None or not vals or abs(_raw_tot - _vsum) <= 1
                    else _vsum)
        row.append(money(total_v if total_v is not None else item.get('total'), bold or True))
        if total_v is not None and ncols > 0:
            row.append(money(total_v / ncols, bold))
        else:
            row.append(Paragraph('—', ST_BOLD_R if bold else ST_TD))
        return row

    # ── Period values: always derived from items, never from d scalars ───────
    def _pvs(items):
        return [sum(clean(it.get('values',[None]*99)[i]) or 0
                    for it in items if i < len(it.get('values',[])))
                for i in range(ncols)]
    rev_pvs  = _pvs(revenue_items) if show_periods else []
    cogs_pvs = _pvs(cogs_items)    if show_periods else []
    opex_pvs = _pvs(opex_items)    if show_periods else []
    gp_pvs   = [rev_pvs[i] - cogs_pvs[i] for i in range(ncols)] if show_periods else []
    np_pvs   = [rev_pvs[i] - cogs_pvs[i] - opex_pvs[i] for i in range(ncols)] if show_periods else []

    rows = [hdr]
    cat_rows = []
    teal_rows = []
    blank_rows = []

    if revenue_items:
        rows.append(cat('REVENUE')); cat_rows.append(len(rows)-1)
        for it in revenue_items: rows.append(item_row(it))
        rows.append(blank()); blank_rows.append(len(rows)-1)
        tr = {'label':'Total Revenue','values':rev_pvs,'total':d.get('total_revenue')}
        rows.append(item_row(tr, bold=True, indent=False)); teal_rows.append(len(rows)-1)
        rows.append(blank()); blank_rows.append(len(rows)-1)

    if cogs_items or has_val(d.get('total_cogs')):
        rows.append(cat('COST OF GOODS SOLD')); cat_rows.append(len(rows)-1)
        for it in cogs_items: rows.append(item_row(it))
        cogs_total = d.get('total_cogs') or (sum(cogs_pvs) if cogs_pvs else None)
        rows.append(blank()); blank_rows.append(len(rows)-1)
        rows.append(item_row({'label':'Total COGS','values':cogs_pvs,'total':cogs_total}, bold=True, indent=False))
        teal_rows.append(len(rows)-1)
        rows.append(blank()); blank_rows.append(len(rows)-1)

    if has_val(d.get('gross_profit')) or gp_pvs:
        gp_total = d.get('gross_profit') or (sum(gp_pvs) if gp_pvs else None)
        gp = {'label':'GROSS PROFIT','values':gp_pvs,'total':gp_total}
        rows.append(item_row(gp, bold=True, indent=False)); teal_rows.append(len(rows)-1)
        if has_val(d.get('gross_margin')):
            rows.append([label('Gross Margin %', sub=True)] + [td('—')]*ncols + [td(fmtp(d.get('gross_margin')))] + [td('—')])
        rows.append(blank()); blank_rows.append(len(rows)-1)

    if opex_items or has_val(d.get('total_opex')):
        rows.append(cat('OPERATING EXPENSES')); cat_rows.append(len(rows)-1)
        for it in opex_items: rows.append(item_row(it))
        opex_total = d.get('total_opex') or (sum(opex_pvs) if opex_pvs else None)
        opex_tv = clean(opex_total)
        total_rv = clean(d.get('total_revenue'))
        rows.append(blank()); blank_rows.append(len(rows)-1)
        rows.append(item_row({'label':'Total Operating Expenses','values':opex_pvs,'total':opex_total}, bold=True, indent=False))
        teal_rows.append(len(rows)-1)
        if opex_tv is not None and total_rv is not None and total_rv != 0:
            opex_pct = opex_tv / total_rv * 100
            rows.append([label('OpEx % of Revenue', sub=True)] + [td('—')]*ncols + [td(fmtp(opex_pct))] + [td('—')])
        rows.append(blank()); blank_rows.append(len(rows)-1)

    np_total = d.get('net_profit') or (sum(np_pvs) if np_pvs else None)
    np_row = {'label':'NET PROFIT','values':np_pvs,'total':np_total}
    rows.append(blank()); blank_rows.append(len(rows)-1)
    rows.append(item_row(np_row, bold=True, indent=False))
    net_row_idx = len(rows)-1
    if has_val(d.get('net_margin')):
        nm_pvs = []
        for i in range(ncols):
            _r = rev_pvs[i] if i < len(rev_pvs) else 0
            _n = np_pvs[i]  if i < len(np_pvs)  else 0
            nm_pvs.append(fmtp(_n / _r * 100) if _r > 0 else '—')
        rows.append([label('Net Margin %', sub=True)] + [td(x) for x in nm_pvs] + [td(fmtp(d.get('net_margin')))] + [td('—')])

    # Data sources footnote
    period_labels = ', '.join(periods_full if periods_full else periods)
    fn_text = f'Based on data provided for {period_labels}. Figures are unaudited management accounts.'
    rows.append([Paragraph(fn_text, s('plfn', fontSize=7, textColor=GRAY, leading=10, fontName=FONT_SANS))] + ['']*(ncols+2))
    fn_row_idx = len(rows)-1

    colw = [60*mm] + [(115*mm)/(ncols+2)]*(ncols+2)
    t = Table(rows, colWidths=colw, repeatRows=1)
    style = [
        ('BACKGROUND',(0,0),(-1,0),NAVY),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE,OFFWHITE]),
        ('LINEBELOW',(0,0),(-1,0),1,TEAL),
        ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
        ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('BACKGROUND',(0,net_row_idx),(-1,net_row_idx),colors.HexColor('#FFF7E6')),
        ('LINEABOVE',(0,net_row_idx),(-1,net_row_idx),1.5,NAVY),
        ('SPAN',(0,fn_row_idx),(-1,fn_row_idx)),
        ('BACKGROUND',(0,fn_row_idx),(-1,fn_row_idx),OFFWHITE),
        ('TOPPADDING',(0,fn_row_idx),(-1,fn_row_idx),4),
        ('BOTTOMPADDING',(0,fn_row_idx),(-1,fn_row_idx),4),
    ]
    for ci in cat_rows: style.append(('SPAN',(0,ci),(-1,ci)))
    for ti in teal_rows: style.append(('BACKGROUND',(0,ti),(-1,ti),TEAL_LITE))
    for bi in blank_rows:
        style.append(('TOPPADDING',(0,bi),(-1,bi),0))
        style.append(('BOTTOMPADDING',(0,bi),(-1,bi),0))
    t.setStyle(TableStyle(style))
    return t

def comparison_pl_table(d, periods, periods_keys, revenue_items, cogs_items, opex_items,
                         prev_revenue_items, prev_cogs_items, prev_opex_items, C_ACCENT):
    def th(txt, right=True): return Paragraph(txt, ST_TH if right else ST_TH_L)
    def td(txt, right=True): return Paragraph(str(txt), ST_TD if right else ST_TD_L)
    def money(v, bold=False):
        display = fmt(v) if has_val(v) else '—'
        return Paragraph(display, ST_BOLD_R if bold else ST_TD)
    def pct_change(curr, prev, bold=False):
        try:
            cv=clean(curr); pv=clean(prev)
            if cv is not None and pv is not None and pv!=0:
                ch=((cv-pv)/abs(pv))*100
                col = GREEN_TEXT if ch>=0 else RED_TEXT
                txt = f"{'▲' if ch>=0 else '▼'} {abs(ch):.1f}%"
                st = s('chg',fontName=FONT_SANS_BOLD if bold else FONT_SANS,fontSize=7.5,textColor=col,alignment=TA_RIGHT,leading=11)
                return Paragraph(txt,st)
        except: pass
        return Paragraph('—',ST_TD)
    def label(txt, indent=False, bold=False, sub=False):
        p='    ' if indent else ''
        st=ST_BOLD if bold else (s('sub',fontSize=7.5,textColor=GRAY,leading=11) if sub else ST_TD_L)
        return Paragraph(p+txt,st)
    def cat(txt):
        ncols_total = len(periods)+3
        _sp = s('sp', fontSize=2, leading=2)
        return [Paragraph(txt,s('cat',fontName=FONT_SANS_BOLD,fontSize=7.5,textColor=C_ACCENT,leading=11))] + [Paragraph('', _sp)]*(ncols_total-1)
    def blank():
        ncols_total = len(periods)+3
        _sp = s('sp', fontSize=2, leading=2)
        return [Paragraph('', _sp)] + [Paragraph('', _sp)] * (ncols_total - 1)

    ncols = len(periods)
    prev_period_label = str(d.get('previous_period','Prev'))[:8]

    def get_prev_item(items_list, label_text):
        for it in items_list:
            if it.get('label','').lower() == label_text.lower():
                return it
        return None

    def get_prev_total(items_list, label_text):
        it = get_prev_item(items_list, label_text)
        return it.get('total') if it else None

    hdr = [th('',False)]
    for p in periods: hdr.append(th(normalise_period_label(p)))
    hdr += [th('Current'), th(prev_period_label), th('Chg %')]

    gray_s    = s('rem_lbl', fontName=FONT_SANS, fontSize=8,
                  textColor=colors.HexColor('#9CA3AF'), leading=11)
    gray_v    = s('rem_val', fontName=FONT_SANS, fontSize=8,
                  textColor=colors.HexColor('#9CA3AF'), leading=11, alignment=TA_RIGHT)
    removed_s = s('rem_chg', fontName=FONT_SANS_BOLD, fontSize=7.5,
                  textColor=RED_TEXT, alignment=TA_RIGHT, leading=11)
    new_s     = s('new_tag', fontName=FONT_SANS_BOLD, fontSize=7,
                  textColor=GREEN_TEXT, leading=11)

    def item_row(item, prev_items, bold=False, indent=True):
        vals = item.get('values',[])
        lbl_txt = item.get('label','—')
        prev_it = get_prev_item(prev_items, lbl_txt)
        is_new  = not bold and prev_it is None

        # Build label cell — append ★ New badge for new items
        p_prefix = '    ' if indent else ''
        if is_new:
            lbl_cell = Paragraph(
                p_prefix + lbl_txt + '  <font size="7" color="#15803D">&#9733; New</font>',
                ST_BOLD if bold else ST_TD_L,
            )
        else:
            lbl_cell = label(lbl_txt, indent=indent, bold=bold)

        row = [lbl_cell]
        for i in range(ncols):
            v = vals[i] if i<len(vals) else None
            if bold and not has_val(v):
                row.append(Paragraph('—', ST_BOLD_R if bold else ST_TD))
            else:
                row.append(money(v, bold))
        curr_total = item.get('total')
        prev_total = prev_it.get('total') if prev_it else None
        row.append(money(curr_total, bold))
        row.append(money(prev_total, bold))
        row.append(pct_change(curr_total, prev_total, bold))
        return row

    def removed_rows(curr_items, prev_items):
        """Rows for items in previous period but absent from current."""
        result = []
        for pit in prev_items:
            if not any(ci.get('label','').lower() == pit.get('label','').lower()
                       for ci in curr_items):
                row = [Paragraph('    ' + pit.get('label','') + ' (Removed)', gray_s)]
                for _ in range(ncols): row.append(Paragraph('—', gray_v))
                row.append(Paragraph('—', gray_v))
                row.append(Paragraph(fmt(pit.get('total')) if has_val(pit.get('total')) else '—', gray_v))
                row.append(Paragraph('▼ Removed', removed_s))
                result.append(row)
        return result

    # ── Period values from items (never from d scalars) ──────────────────────
    def _cpvs(items):
        return [sum(clean(it.get('values',[None]*99)[i]) or 0
                    for it in items if i < len(it.get('values',[])))
                for i in range(ncols)]
    c_rev_pvs  = _cpvs(revenue_items)
    c_cogs_pvs = _cpvs(cogs_items)
    c_opex_pvs = _cpvs(opex_items)
    c_gp_pvs   = [c_rev_pvs[i] - c_cogs_pvs[i] for i in range(ncols)]
    c_np_pvs   = [c_rev_pvs[i] - c_cogs_pvs[i] - c_opex_pvs[i] for i in range(ncols)]

    rows = [hdr]
    teal_rows=[]
    blank_rows=[]

    if revenue_items:
        rows.append(cat('REVENUE'))
        for it in revenue_items: rows.append(item_row(it,prev_revenue_items))
        for rr in removed_rows(revenue_items, prev_revenue_items): rows.append(rr)
        tr_curr=d.get('total_revenue'); tr_prev=d.get('prev_total_revenue')
        tr_row=[label('Total Revenue',bold=True)]
        for i in range(ncols): tr_row.append(money(c_rev_pvs[i] if i < len(c_rev_pvs) else None,True))
        tr_row+=[money(tr_curr,True),money(tr_prev,True),pct_change(tr_curr,tr_prev,True)]
        rows.append(blank()); blank_rows.append(len(rows)-1)
        rows.append(tr_row); teal_rows.append(len(rows)-1)
        rows.append(blank()); blank_rows.append(len(rows)-1)

    if cogs_items or has_val(d.get('total_cogs')):
        rows.append(cat('COST OF GOODS SOLD'))
        for it in cogs_items: rows.append(item_row(it,prev_cogs_items))
        for rr in removed_rows(cogs_items, prev_cogs_items): rows.append(rr)
        tc_curr=d.get('total_cogs'); tc_prev=d.get('prev_total_cogs')
        rows.append(blank()); blank_rows.append(len(rows)-1)
        rows.append([label('Total COGS',bold=True)]+[money(c_cogs_pvs[i] if i < len(c_cogs_pvs) else None,True) for i in range(ncols)]+[money(tc_curr,True),money(tc_prev,True),pct_change(tc_curr,tc_prev,True)])
        teal_rows.append(len(rows)-1)
        rows.append(blank()); blank_rows.append(len(rows)-1)

    if has_val(d.get('gross_profit')) or c_gp_pvs:
        gp_curr=d.get('gross_profit'); gp_prev=d.get('prev_gross_profit')
        rows.append([label('GROSS PROFIT',bold=True)]+[money(c_gp_pvs[i] if i < len(c_gp_pvs) else None,True) for i in range(ncols)]+[money(gp_curr,True),money(gp_prev,True),pct_change(gp_curr,gp_prev,True)])
        teal_rows.append(len(rows)-1)
        if has_val(d.get('gross_margin')):
            rows.append([label('Gross Margin %',sub=True)]+['—']*ncols+[td(fmtp(d.get('gross_margin'))),td(fmtp(d.get('prev_gross_margin'))),td('—')])
        rows.append(blank()); blank_rows.append(len(rows)-1)

    if opex_items or has_val(d.get('total_opex')):
        rows.append(cat('OPERATING EXPENSES'))
        for it in opex_items: rows.append(item_row(it,prev_opex_items))
        for rr in removed_rows(opex_items, prev_opex_items): rows.append(rr)
        to_curr=d.get('total_opex'); to_prev=d.get('prev_total_opex')
        rows.append(blank()); blank_rows.append(len(rows)-1)
        rows.append([label('Total OpEx',bold=True)]+[money(c_opex_pvs[i] if i < len(c_opex_pvs) else None,True) for i in range(ncols)]+[money(to_curr,True),money(to_prev,True),pct_change(to_curr,to_prev,True)])
        teal_rows.append(len(rows)-1)
        rows.append(blank()); blank_rows.append(len(rows)-1)

    np_curr=d.get('net_profit'); np_prev=d.get('prev_net_profit')
    np_row=[label('NET PROFIT',bold=True)]
    for i in range(ncols): np_row.append(money(c_np_pvs[i] if i < len(c_np_pvs) else None,True))
    np_row+=[money(np_curr,True),money(np_prev,True),pct_change(np_curr,np_prev,True)]
    rows.append(blank()); blank_rows.append(len(rows)-1)
    rows.append(np_row)
    net_idx=len(rows)-1
    if has_val(d.get('net_margin')):
        c_nm_pvs = [fmtp(c_np_pvs[i] / c_rev_pvs[i] * 100) if i < len(c_rev_pvs) and c_rev_pvs[i] > 0 else '—'
                    for i in range(ncols)]
        rows.append([label('Net Margin %',sub=True)]+[td(x) for x in c_nm_pvs]+[td(fmtp(d.get('net_margin'))),td(fmtp(d.get('prev_net_margin'))),td('—')])

    # Data sources footnote
    ncols_total = ncols + 3
    fn_txt = f'Based on data provided. Figures are unaudited management accounts.'
    rows.append([Paragraph(fn_txt, s('cplfn', fontSize=7, textColor=GRAY, leading=10, fontName=FONT_SANS))] + ['']*(ncols_total-1))
    cplfn_idx = len(rows)-1

    period_cw = min(22*mm, 60*mm/max(ncols,1))
    cw = [60*mm]+[period_cw]*ncols+[24*mm,24*mm,20*mm]
    t=Table(rows,colWidths=cw,repeatRows=1)
    style_cmds=[
        ('BACKGROUND',(0,0),(-1,0),NAVY),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE,OFFWHITE]),
        ('LINEBELOW',(0,0),(-1,0),1,C_ACCENT),
        ('BACKGROUND',(0,net_idx),(-1,net_idx),colors.HexColor('#FFF7E6')),
        ('LINEABOVE',(0,net_idx),(-1,net_idx),1.5,NAVY),
        ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
        ('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('SPAN',(0,cplfn_idx),(-1,cplfn_idx)),
        ('BACKGROUND',(0,cplfn_idx),(-1,cplfn_idx),OFFWHITE),
        ('TOPPADDING',(0,cplfn_idx),(-1,cplfn_idx),4),
        ('BOTTOMPADDING',(0,cplfn_idx),(-1,cplfn_idx),4),
    ]
    for ti in teal_rows: style_cmds.append(('BACKGROUND',(0,ti),(-1,ti),TEAL_LITE))
    for bi in blank_rows:
        style_cmds.append(('TOPPADDING',(0,bi),(-1,bi),0))
        style_cmds.append(('BOTTOMPADDING',(0,bi),(-1,bi),0))
    t.setStyle(TableStyle(style_cmds))
    return t

# ── Comparison-only helpers ───────────────────────────────────────────────────

def comparison_executive_box(d, C_ACCENT):
    """Styled analyst paragraph for comparison executive summary."""
    try:
        curr_rev = clean(d.get('total_revenue'))
        prev_rev = clean(d.get('prev_total_revenue'))
        curr_np  = clean(d.get('net_profit'))
        prev_np  = clean(d.get('prev_net_profit'))
        curr_gm  = clean(d.get('gross_margin'))
        prev_gm  = clean(d.get('prev_gross_margin'))
        curr_nm  = clean(d.get('net_margin'))
        prev_nm  = clean(d.get('prev_net_margin'))
        period   = str(d.get('period', 'current period'))
        prev_per = str(d.get('previous_period', 'prior period'))

        parts = []
        metrics_up = 0; metrics_down = 0

        if curr_rev and prev_rev and prev_rev != 0:
            chg = ((curr_rev - prev_rev) / abs(prev_rev)) * 100
            word = 'increased' if chg >= 0 else 'decreased'
            parts.append(
                f"Revenue {word} {abs(chg):.1f}% from {fmt(prev_rev)} ({prev_per}) "
                f"to {fmt(curr_rev)} ({period})."
            )
            metrics_up += (1 if chg >= 0 else 0); metrics_down += (0 if chg >= 0 else 1)

        if curr_np is not None and prev_np is not None and prev_np != 0:
            chg = ((curr_np - prev_np) / abs(prev_np)) * 100
            word = 'improved' if chg >= 0 else 'declined'
            parts.append(f"Net profit {word} {abs(chg):.1f}% from {fmt(prev_np)} to {fmt(curr_np)}.")
            metrics_up += (1 if chg >= 0 else 0); metrics_down += (0 if chg >= 0 else 1)

        if curr_gm is not None and prev_gm is not None:
            chg = curr_gm - prev_gm
            if abs(chg) >= 0.5:
                word = 'expanded' if chg > 0 else 'contracted'
                parts.append(
                    f"Gross margin {word} by {abs(chg):.1f}pp from {fmtp(prev_gm)} to {fmtp(curr_gm)}."
                )
            else:
                parts.append(f"Gross margin held steady at {fmtp(curr_gm)} (prior: {fmtp(prev_gm)}).")
            metrics_up += (1 if chg >= 0 else 0); metrics_down += (0 if chg >= 0 else 1)

        if curr_nm is not None and prev_nm is not None:
            chg = curr_nm - prev_nm
            if abs(chg) >= 0.5:
                word = 'improved' if chg > 0 else 'compressed'
                parts.append(f"Net margin {word} from {fmtp(prev_nm)} to {fmtp(curr_nm)}.")
            else:
                parts.append(f"Net margin stable at {fmtp(curr_nm)}.")
            metrics_up += (1 if chg >= 0 else 0); metrics_down += (0 if chg >= 0 else 1)

        if metrics_down == 0 and metrics_up > 0:
            verdict = "Overall verdict: performance improved across all tracked metrics."
        elif metrics_up > metrics_down:
            verdict = "Overall verdict: positive period — the majority of key metrics improved."
        elif metrics_down > metrics_up:
            verdict = "Overall verdict: performance declined across most key metrics; management review recommended."
        else:
            verdict = "Overall verdict: mixed performance — gains in some areas offset by weakness in others."
        parts.append(verdict)

        if not parts: return None
        text = '  '.join(parts)
        inner_s = s('cexec_inner', fontName=FONT_SANS, fontSize=8.5,
                    textColor=colors.HexColor('#1A3A2A'), leading=14)
        t = Table([[Paragraph(text, inner_s)]], colWidths=[175*mm])
        t.setStyle(TableStyle([
            ('BOX',         (0,0),(-1,-1), 1,   C_ACCENT),
            ('LINEBEFORE',  (0,0),(0,-1),  4,   C_ACCENT),
            ('BACKGROUND',  (0,0),(-1,-1),      TEAL_LITE),
            ('TOPPADDING',  (0,0),(-1,-1), 8),
            ('BOTTOMPADDING',(0,0),(-1,-1),8),
            ('LEFTPADDING', (0,0),(-1,-1), 10),
            ('RIGHTPADDING',(0,0),(-1,-1), 8),
        ]))
        return t
    except Exception:
        return None


def comparison_summary_box(d, C_ACCENT):
    """Side-by-side period comparison summary table (after KPI cards)."""
    try:
        period_curr = str(d.get('period', 'Current'))[:14]
        period_prev = str(d.get('previous_period', 'Previous'))[:14]

        def prev_cell(v, is_pct=False, bold=False):
            fn = FONT_SANS_BOLD if bold else FONT_SANS
            disp = (fmtp if is_pct else fmt)(v) if has_val(v) else '—'
            return Paragraph(disp, s(f'csbp_{id(v)}', fontName=fn, fontSize=8,
                                     textColor=DARK, leading=12, alignment=TA_RIGHT))

        def curr_cell(curr_v, prev_v, is_pct=False, bold=False):
            cv = clean(curr_v); pv = clean(prev_v)
            fn = FONT_SANS_BOLD if bold else FONT_SANS
            disp = (fmtp if is_pct else fmt)(cv) if cv is not None else '—'
            if cv is not None and pv is not None and pv != 0:
                chg = ((cv - pv) / abs(pv)) * 100
                arrow = '▲' if chg >= 0 else '▼'
                col = GREEN_TEXT if chg >= 0 else RED_TEXT
                disp = f"{disp}  {arrow}{abs(chg):.1f}%"
            else:
                col = DARK
            return Paragraph(disp, s(f'csbc_{id(curr_v)}', fontName=fn, fontSize=8,
                                     textColor=col, leading=12, alignment=TA_RIGHT))

        hdr = [
            Paragraph('Metric', ST_TH_L),
            Paragraph(period_prev, ST_TH),
            Paragraph(f'{period_curr}  (change)', ST_TH),
        ]

        def mrow(metric, prev_v, curr_v, is_pct=False, bold=False):
            fn = FONT_SANS_BOLD if bold else FONT_SANS
            tc = NAVY if bold else DARK
            return [
                Paragraph(metric, s(f'csml_{metric[:10]}', fontName=fn, fontSize=8,
                                    textColor=tc, leading=12)),
                prev_cell(prev_v, is_pct, bold),
                curr_cell(curr_v, prev_v, is_pct, bold),
            ]

        rows = [hdr,
            mrow('Total Revenue',  d.get('prev_total_revenue'), d.get('total_revenue'),  bold=True),
            mrow('Gross Profit',   d.get('prev_gross_profit'),  d.get('gross_profit'),   bold=True),
            mrow('Gross Margin %', d.get('prev_gross_margin'),  d.get('gross_margin'),   is_pct=True),
            mrow('Net Profit',     d.get('prev_net_profit'),    d.get('net_profit'),     bold=True),
            mrow('Net Margin %',   d.get('prev_net_margin'),    d.get('net_margin'),     is_pct=True),
            mrow('Total OpEx',     d.get('prev_total_opex'),    d.get('total_opex')),
        ]

        t = Table(rows, colWidths=[55*mm, 55*mm, 65*mm], repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,0),  NAVY),
            ('ROWBACKGROUNDS',(0,1),(-1,-1), [WHITE, OFFWHITE]),
            ('TOPPADDING',    (0,0),(-1,-1), 5),
            ('BOTTOMPADDING', (0,0),(-1,-1), 5),
            ('LEFTPADDING',   (0,0),(-1,-1), 8),
            ('RIGHTPADDING',  (0,0),(-1,-1), 8),
            ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
            ('LINEBELOW',     (0,0),(-1,0),  1, C_ACCENT),
        ]))
        return t
    except Exception:
        return None


def margin_comparison_table(d, C_ACCENT):
    """Margin metrics: Metric | Previous | Current | Change | Trend."""
    try:
        curr_gm   = clean(d.get('gross_margin'))
        prev_gm   = clean(d.get('prev_gross_margin'))
        curr_nm   = clean(d.get('net_margin'))
        prev_nm   = clean(d.get('prev_net_margin'))
        curr_rev  = clean(d.get('total_revenue'))
        prev_rev  = clean(d.get('prev_total_revenue'))
        curr_cogs = clean(d.get('total_cogs'))
        prev_cogs = clean(d.get('prev_total_cogs'))
        curr_opex = clean(d.get('total_opex'))
        prev_opex = clean(d.get('prev_total_opex'))

        curr_cogs_pct = (curr_cogs/curr_rev*100) if curr_cogs and curr_rev and curr_rev>0 else None
        prev_cogs_pct = (prev_cogs/prev_rev*100) if prev_cogs and prev_rev and prev_rev>0 else None
        curr_opex_pct = (curr_opex/curr_rev*100) if curr_opex and curr_rev and curr_rev>0 else None
        prev_opex_pct = (prev_opex/prev_rev*100) if prev_opex and prev_rev and prev_rev>0 else None

        def chg_cells(curr_v, prev_v, lower_is_better=False):
            if curr_v is None or prev_v is None:
                return Paragraph('—', ST_TD), Paragraph('—', ST_TD)
            chg = curr_v - prev_v
            improved = (chg < 0) if lower_is_better else (chg >= 0)
            col = GREEN_TEXT if improved else RED_TEXT
            arrow = '▲' if chg >= 0 else '▼'
            chg_s  = s(f'mct_{id(curr_v)}', fontName=FONT_SANS_BOLD, fontSize=8,
                       textColor=col, alignment=TA_RIGHT, leading=11)
            trend_s = s(f'mcd_{id(curr_v)}', fontName=FONT_SANS_BOLD, fontSize=10,
                        textColor=col, alignment=TA_CENTER, leading=12)
            return (Paragraph(f"{arrow} {abs(chg):.1f}pp", chg_s),
                    Paragraph(arrow, trend_s))

        hdr = [Paragraph('Metric', ST_TH_L), Paragraph('Previous', ST_TH),
               Paragraph('Current', ST_TH), Paragraph('Change', ST_TH), Paragraph('Trend', ST_TH)]

        def mrow(lbl, prev_v, curr_v, lib=False):
            cp, tp = chg_cells(curr_v, prev_v, lib)
            return [Paragraph(lbl, ST_TD_L),
                    Paragraph(fmtp(prev_v) if prev_v is not None else '—', ST_TD),
                    Paragraph(fmtp(curr_v) if curr_v is not None else '—', ST_TD),
                    cp, tp]

        rows = [hdr]
        if curr_gm is not None or prev_gm is not None:
            rows.append(mrow('Gross Margin %', prev_gm, curr_gm))
        if curr_nm is not None or prev_nm is not None:
            rows.append(mrow('Net Margin %', prev_nm, curr_nm))
        if curr_cogs_pct is not None or prev_cogs_pct is not None:
            rows.append(mrow('COGS as % of Revenue', prev_cogs_pct, curr_cogs_pct, lib=True))
        if curr_opex_pct is not None or prev_opex_pct is not None:
            rows.append(mrow('OpEx as % of Revenue', prev_opex_pct, curr_opex_pct, lib=True))
        if len(rows) <= 1: return None

        t = Table(rows, colWidths=[65*mm, 28*mm, 28*mm, 32*mm, 22*mm], repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,0),  NAVY),
            ('ROWBACKGROUNDS',(0,1),(-1,-1), [WHITE, OFFWHITE]),
            ('TOPPADDING',    (0,0),(-1,-1), 5),
            ('BOTTOMPADDING', (0,0),(-1,-1), 5),
            ('LEFTPADDING',   (0,0),(-1,-1), 8),
            ('RIGHTPADDING',  (0,0),(-1,-1), 8),
            ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
            ('LINEBELOW',     (0,0),(-1,0),  1, C_ACCENT),
        ]))
        return t
    except Exception:
        return None


def single_waterfall(rev_v, cogs_v, opex_v, net_v, w=82, h=85, muted=False, title=''):
    """Compact single-period waterfall chart."""
    try:
        rev = clean(rev_v)
        if not rev or rev <= 0: return None
        cogs  = clean(cogs_v)  or 0
        opex  = clean(opex_v)  or 0
        np_v2 = clean(net_v)
        gross = rev - cogs
        net   = np_v2 if np_v2 is not None else (gross - opex)

        ct = colors.HexColor('#8CB8B3') if muted else TEAL
        cr = colors.HexColor('#E8A0A0') if muted else RED_TEXT
        cn = colors.HexColor('#8B97AA') if muted else NAVY
        ca = colors.HexColor('#E8C97A') if muted else colors.HexColor('#D97706')
        cf = colors.HexColor('#B8A0A0') if muted else colors.HexColor('#6B2D2D')
        lc = colors.HexColor('#5B6B7A') if muted else NAVY

        dw = Drawing(w*mm, h*mm)
        base_y  = 14*mm
        chart_h = (h - 28)*mm

        def ht(val): return (max(val, 0) / rev) * chart_h if rev > 0 else 0

        avail = (w - 6)*mm
        bw    = min(22*mm, avail / 3.6)
        gap   = (avail - bw * 3) / 2
        def bx(i): return 3*mm + i*(bw + gap)

        def smart_lbl(x, y_bot, bar_h, text):
            if bar_h > 6*mm:
                dw.add(String(x+bw/2, y_bot+bar_h/2-1*mm, text,
                              fontSize=5.5, fillColor=WHITE, textAnchor='middle', fontName=FONT_SANS_BOLD))
            elif bar_h > 0.5:
                dw.add(String(x+bw/2, y_bot+bar_h+1.5*mm, text,
                              fontSize=5.5, fillColor=lc, textAnchor='middle', fontName=FONT_SANS_BOLD))

        def ax_lbl(x, text):
            dw.add(String(x+bw/2, base_y-9*mm, text,
                          fontSize=6, fillColor=GRAY, textAnchor='middle', fontName=FONT_SANS_BOLD))

        full_h = ht(rev); gp_h = ht(gross); cogs_h = ht(cogs)
        net_h  = ht(max(net, 0)); opex_h = ht(opex)
        pad_h  = max(full_h - net_h - opex_h, 0)

        dw.add(Rect(bx(0), base_y, bw, full_h, fillColor=ct, strokeColor=None))
        smart_lbl(bx(0), base_y, full_h, f'£{rev/1000:.0f}k')
        ax_lbl(bx(0), 'Revenue')

        dw.add(Rect(bx(1), base_y,       bw, gp_h,   fillColor=ct, strokeColor=None))
        dw.add(Rect(bx(1), base_y+gp_h,  bw, cogs_h, fillColor=cr, strokeColor=None))
        smart_lbl(bx(1), base_y,      gp_h,   f'GP £{gross/1000:.0f}k')
        smart_lbl(bx(1), base_y+gp_h, cogs_h, 'COGS')
        ax_lbl(bx(1), 'Gross Profit')

        dw.add(Rect(bx(2), base_y,           bw, net_h,  fillColor=cn, strokeColor=None))
        dw.add(Rect(bx(2), base_y+net_h,     bw, opex_h, fillColor=ca, strokeColor=None))
        if pad_h > 0:
            dw.add(Rect(bx(2), base_y+net_h+opex_h, bw, pad_h, fillColor=cf, strokeColor=None))
        smart_lbl(bx(2), base_y,       net_h,  f'NP £{net/1000:.0f}k')
        smart_lbl(bx(2), base_y+net_h, opex_h, 'OpEx')
        ax_lbl(bx(2), 'Net Profit')

        dw.add(Line(1*mm, base_y, (w-1)*mm, base_y, strokeColor=BORDER, strokeWidth=0.5))

        if title:
            dw.add(String(w/2*mm, (h-5)*mm, title[:16],
                          fontSize=7, fillColor=lc, textAnchor='middle', fontName=FONT_SANS_BOLD))
        return dw
    except Exception:
        return None


def dual_waterfall_chart(d, C_ACCENT):
    """Two compact waterfalls side by side: previous (muted) left, current right."""
    try:
        prev_wf = single_waterfall(
            d.get('prev_total_revenue'), d.get('prev_total_cogs'),
            d.get('prev_total_opex'),    d.get('prev_net_profit'),
            w=82, h=85, muted=True,
            title=str(d.get('previous_period','Previous'))[:16],
        )
        curr_wf = single_waterfall(
            d.get('total_revenue'), d.get('total_cogs'),
            d.get('total_opex'),    d.get('net_profit'),
            w=82, h=85, muted=False,
            title=str(d.get('period','Current'))[:16],
        )
        if prev_wf is None and curr_wf is None: return None
        if prev_wf is None: return curr_wf
        if curr_wf is None: return prev_wf
        t = Table([[prev_wf, curr_wf]], colWidths=[86*mm, 89*mm])
        t.setStyle(TableStyle([
            ('VALIGN',       (0,0),(-1,-1),'TOP'),
            ('LEFTPADDING',  (0,0),(-1,-1),0),
            ('RIGHTPADDING', (0,0),(-1,-1),0),
            ('TOPPADDING',   (0,0),(-1,-1),0),
            ('BOTTOMPADDING',(0,0),(-1,-1),0),
        ]))
        return t
    except Exception:
        return None


# ── Report card section ───────────────────────────────────────────────────────

def report_card_section(d, C_ACCENT):
    """5 letter-grade cards: Revenue Growth, Gross Margin, Cost Control, Net Profitability, Overall Health."""
    try:
        def grade_card(dimension, grade, explanation, col):
            bg_map = {
                GREEN_TEXT: GREEN_SOFT,
                TEAL:       TEAL_LITE,
                GOLD:       AMBER_SOFT,
                AMBER_TEXT: AMBER_SOFT,
                RED_TEXT:   RED_SOFT,
            }
            bg = bg_map.get(col, OFFWHITE)
            dim_s  = s(f'rcd{grade}{dimension[:4]}', fontName=FONT_SANS_BOLD, fontSize=6.5, textColor=DARK, leading=9, alignment=TA_CENTER)
            grd_s  = s(f'rcg{grade}{dimension[:4]}', fontName=FONT_SERIF_BOLD, fontSize=28, textColor=col, leading=33, alignment=TA_CENTER)
            exp_s  = s(f'rce{grade}{dimension[:4]}', fontName=FONT_SANS, fontSize=6.5, textColor=GRAY, leading=9, alignment=TA_CENTER)
            data   = [
                [Paragraph(dimension, dim_s)],
                [Paragraph(grade, grd_s)],
                [Paragraph(explanation, exp_s)],
            ]
            cw = 175*mm / 5
            t = Table(data, colWidths=[cw])
            t.setStyle(TableStyle([
                ('BACKGROUND',    (0,0),(-1,-1), bg),
                ('BOX',           (0,0),(-1,-1), 1,   col),
                ('LINEABOVE',     (0,0),(-1,0),  3,   col),
                ('TOPPADDING',    (0,0),(-1,-1), 6),
                ('BOTTOMPADDING', (0,0),(-1,-1), 6),
                ('LEFTPADDING',   (0,0),(-1,-1), 3),
                ('RIGHTPADDING',  (0,0),(-1,-1), 3),
            ]))
            return t

        cards = []
        cw = 175*mm / 5

        # Revenue Growth (requires comparison data)
        curr_rev = clean(d.get('total_revenue'))
        prev_rev = clean(d.get('prev_total_revenue'))
        if curr_rev is not None and prev_rev is not None and prev_rev != 0:
            pct = (curr_rev - prev_rev) / abs(prev_rev) * 100
            if   pct >  20: g, col, exp = 'A', GREEN_TEXT, f'+{pct:.0f}% growth'
            elif pct >  10: g, col, exp = 'B', TEAL,       f'+{pct:.0f}% growth'
            elif pct >=  0: g, col, exp = 'C', GOLD,       f'+{pct:.0f}% growth'
            elif pct > -20: g, col, exp = 'D', AMBER_TEXT, f'{pct:.0f}% decline'
            else:           g, col, exp = 'F', RED_TEXT,   f'{pct:.0f}% decline'
            cards.append(grade_card('Revenue Growth', g, exp, col))

        # Gross Margin Quality
        gm = clean(d.get('gross_margin'))
        if gm is not None:
            gm100 = gm if gm > 1 else gm * 100
            if   gm100 > 70: g, col, exp = 'A', GREEN_TEXT, f'{gm100:.0f}% margin'
            elif gm100 > 60: g, col, exp = 'B', TEAL,       f'{gm100:.0f}% margin'
            elif gm100 > 50: g, col, exp = 'C', GOLD,       f'{gm100:.0f}% margin'
            elif gm100 > 40: g, col, exp = 'D', AMBER_TEXT, f'{gm100:.0f}% margin'
            else:            g, col, exp = 'F', RED_TEXT,   f'{gm100:.0f}% margin'
            cards.append(grade_card('Gross Margin', g, exp, col))

        # Cost Control
        opex_v = clean(d.get('total_opex'))
        rev_v  = clean(d.get('total_revenue'))
        if opex_v is not None and rev_v and rev_v > 0:
            op_pct = opex_v / rev_v * 100
            if   op_pct < 30: g, col, exp = 'A', GREEN_TEXT, f'{op_pct:.0f}% of rev'
            elif op_pct < 40: g, col, exp = 'B', TEAL,       f'{op_pct:.0f}% of rev'
            elif op_pct < 50: g, col, exp = 'C', GOLD,       f'{op_pct:.0f}% of rev'
            elif op_pct < 60: g, col, exp = 'D', AMBER_TEXT, f'{op_pct:.0f}% of rev'
            else:             g, col, exp = 'F', RED_TEXT,   f'{op_pct:.0f}% of rev'
            cards.append(grade_card('Cost Control', g, exp, col))

        # Net Profitability
        nm = clean(d.get('net_margin'))
        if nm is not None:
            nm100 = nm if nm > 1 else nm * 100
            if   nm100 >  25: g, col, exp = 'A', GREEN_TEXT, f'{nm100:.0f}% margin'
            elif nm100 >  15: g, col, exp = 'B', TEAL,       f'{nm100:.0f}% margin'
            elif nm100 >   8: g, col, exp = 'C', GOLD,       f'{nm100:.0f}% margin'
            elif nm100 >=  0: g, col, exp = 'D', AMBER_TEXT, f'{nm100:.0f}% margin'
            else:             g, col, exp = 'F', RED_TEXT,   f'{nm100:.0f}% margin'
            cards.append(grade_card('Net Profitability', g, exp, col))

        # Overall Health
        hs = clean(d.get('health_score'))
        if hs is not None:
            hs = max(1, min(10, hs))
            if   hs >= 9: g, col, exp = 'A', GREEN_TEXT, f'{hs:.0f}/10 score'
            elif hs >= 7: g, col, exp = 'B', TEAL,       f'{hs:.0f}/10 score'
            elif hs >= 5: g, col, exp = 'C', GOLD,       f'{hs:.0f}/10 score'
            elif hs >= 3: g, col, exp = 'D', AMBER_TEXT, f'{hs:.0f}/10 score'
            else:         g, col, exp = 'F', RED_TEXT,   f'{hs:.0f}/10 score'
            cards.append(grade_card('Overall Health', g, exp, col))

        if not cards:
            return None

        while len(cards) < 5:
            cards.append(Spacer(cw, 1))
        t = Table([cards[:5]], colWidths=[cw]*5)
        t.setStyle(TableStyle([
            ('LEFTPADDING',  (0,0),(-1,-1), 2),
            ('RIGHTPADDING', (0,0),(-1,-1), 2),
            ('TOPPADDING',   (0,0),(-1,-1), 0),
            ('BOTTOMPADDING',(0,0),(-1,-1), 0),
            ('VALIGN',       (0,0),(-1,-1), 'TOP'),
        ]))
        return t
    except Exception:
        return None


# ── Peer comparison section ───────────────────────────────────────────────────

def peer_comparison_section(d, C_ACCENT):
    """3-col benchmark table: Metric | Your Business | Industry Benchmark."""
    try:
        search_text = (str(d.get('business_name','')) + ' ' + str(d.get('executive_summary',''))).lower()
        # sector: (display_name, bench_gm%, bench_nm%)
        _sectors = [
            (['restaurant','hospitality','cafe','hotel','pub'],
             'Restaurant / Hospitality', 67.5, 8.0),
            (['retail','shop','store','ecommerce','e-commerce'],
             'Retail', 45.0, 5.5),
            (['consult','accountan','solicitor','law firm','architect','marketing agency'],
             'Professional Services', 67.5, 20.0),
            (['construction','build','contractor','housebuilder'],
             'Construction', 25.0, 5.5),
            (['tech','software','saas','digital agency','app','platform'],
             'Technology / SaaS', 75.0, 15.0),
        ]
        sector_name, bench_gm, bench_nm = 'Other / General', 55.0, 11.5
        for kws, name, bgm, bnm in _sectors:
            if any(kw in search_text for kw in kws):
                sector_name, bench_gm, bench_nm = name, bgm, bnm
                break

        gm = clean(d.get('gross_margin'))
        nm = clean(d.get('net_margin'))
        if gm is None and nm is None:
            return None

        gm100 = (gm if gm > 1 else gm * 100) if gm is not None else None
        nm100 = (nm if nm > 1 else nm * 100) if nm is not None else None

        def _status(actual, benchmark):
            diff = actual - benchmark
            if diff >= 0:
                return GREEN_TEXT, f'▲ {abs(diff):.1f}pp above'
            elif diff >= -5:
                return AMBER_TEXT, f'▼ {abs(diff):.1f}pp below'
            else:
                return RED_TEXT,   f'▼ {abs(diff):.1f}pp below'

        hdr  = [Paragraph('Metric', ST_TH_L), Paragraph('Your Business', ST_TH), Paragraph('Industry Benchmark', ST_TH)]
        rows = [hdr]

        if gm100 is not None:
            gc, gnote = _status(gm100, bench_gm)
            rows.append([
                Paragraph('Gross Margin %', ST_TD_L),
                Paragraph(f'{gm100:.1f}%', s('pcgmv', fontName=FONT_SANS_BOLD, fontSize=8, textColor=gc, alignment=TA_RIGHT, leading=11)),
                Paragraph(f'~{bench_gm:.0f}%  ({gnote})', s('pcgmb', fontSize=7.5, textColor=gc, alignment=TA_RIGHT, leading=11)),
            ])
        if nm100 is not None:
            nc, nnote = _status(nm100, bench_nm)
            rows.append([
                Paragraph('Net Margin %', ST_TD_L),
                Paragraph(f'{nm100:.1f}%', s('pcnmv', fontName=FONT_SANS_BOLD, fontSize=8, textColor=nc, alignment=TA_RIGHT, leading=11)),
                Paragraph(f'~{bench_nm:.0f}%  ({nnote})', s('pcnmb', fontSize=7.5, textColor=nc, alignment=TA_RIGHT, leading=11)),
            ])

        fn_s  = s('pcfn', fontSize=7, textColor=GRAY, leading=10)
        fn_txt = f'Benchmarks based on UK SME industry averages ({sector_name}). Individual business performance varies.'
        rows.append([Paragraph(fn_txt, fn_s), '', ''])
        fn_idx = len(rows) - 1

        t = Table(rows, colWidths=[60*mm, 55*mm, 60*mm])
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),  (-1,0),       NAVY),
            ('ROWBACKGROUNDS',(0,1),  (-1,fn_idx-1),[WHITE, OFFWHITE]),
            ('BACKGROUND',    (0,fn_idx),(-1,fn_idx), OFFWHITE),
            ('SPAN',          (0,fn_idx),(-1,fn_idx)),
            ('TOPPADDING',    (0,0),  (-1,-1), 5),
            ('BOTTOMPADDING', (0,0),  (-1,-1), 5),
            ('LEFTPADDING',   (0,0),  (-1,-1), 8),
            ('RIGHTPADDING',  (0,0),  (-1,-1), 8),
            ('VALIGN',        (0,0),  (-1,-1), 'MIDDLE'),
            ('LINEBELOW',     (0,0),  (-1,0),  1, C_ACCENT),
        ]))
        return t
    except Exception:
        return None


# ── Next 90 days action plan ──────────────────────────────────────────────────

def next_90_days_section(d, C_ACCENT):
    """3 monthly action cards from next_90_days field (timeline_90_days alias supported)."""
    try:
        import re as _re
        actions = d.get('timeline_90_days')
        if actions:
            if isinstance(actions, str):
                try:
                    actions = json.loads(actions)
                except Exception:
                    # Try pipe separator
                    pipe_parts = [a.strip() for a in actions.split('|') if a.strip()]
                    if len(pipe_parts) >= 2:
                        actions = pipe_parts
                    else:
                        # Try splitting on "Month N:" pattern for timeline strings
                        month_parts = [p.strip() for p in _re.split(r'(?=\bMonth\s+\d)', actions.strip()) if p.strip()]
                        actions = month_parts if len(month_parts) >= 2 else [actions.strip()]
        if not actions or not isinstance(actions, list) or not any(str(a).strip() for a in actions):
            return []
        actions = [str(a).strip() for a in actions if str(a).strip()][:3]
        if not actions:
            return []

        items = []
        for i, action in enumerate(actions, 1):
            month_lbl = f'Month {i}'
            num_s = s(f'nd{i}num', fontName=FONT_SANS_BOLD, fontSize=7, textColor=GOLD, leading=10, alignment=TA_CENTER)
            txt_s = s(f'nd{i}txt', fontName=FONT_SANS, fontSize=8.5, textColor=DARK, leading=13)
            row = Table([[
                Paragraph(month_lbl, num_s),
                Paragraph(action, txt_s),
            ]], colWidths=[14*mm, 161*mm])
            row.setStyle(TableStyle([
                ('VALIGN',       (0,0),(-1,-1), 'TOP'),
                ('TOPPADDING',   (0,0),(-1,-1), 7),
                ('BOTTOMPADDING',(0,0),(-1,-1), 7),
                ('LEFTPADDING',  (0,0),(0,0),   0),
                ('RIGHTPADDING', (0,0),(0,0),   6),
                ('LEFTPADDING',  (1,0),(1,0),   8),
                ('LINEBEFORE',   (0,0),(0,-1),  3, GOLD),
                ('BACKGROUND',   (0,0),(-1,-1), OFFWHITE),
                ('BOX',          (0,0),(-1,-1), 0.5, BORDER),
            ]))
            items.append(row)
            items.append(Spacer(1, 2*mm))
        return items
    except Exception:
        return []


# ── Introduction letter ───────────────────────────────────────────────────────

def intro_letter(d, prepared_by, is_wl, wl_contact, C_PRIMARY):
    """Formal introduction letter page for white label reports only."""
    if not is_wl:
        return []
    try:
        import datetime as _dt
        bname        = str(d.get('business_name', 'the Client'))
        period       = str(d.get('period', ''))
        today        = _dt.datetime.now().strftime('%d %B %Y')
        contact_clean = wl_contact if wl_contact and wl_contact.upper() not in ('NA','N/A','NONE','') else ''

        items = []

        # Letterhead strip
        hdr_rows = [[Paragraph(prepared_by, s('ltfirm', fontName=FONT_SERIF_BOLD, fontSize=16, textColor=WHITE, leading=21))]]
        if contact_clean:
            hdr_rows.append([Paragraph(contact_clean, s('ltcon', fontName=FONT_SANS, fontSize=8, textColor=colors.HexColor('#9BB5D4'), leading=11))])
        hdr_t = Table(hdr_rows, colWidths=[175*mm])
        top_pad = [('TOPPADDING',(0,0),(-1,0), 12), ('BOTTOMPADDING',(0,-1),(-1,-1), 12)]
        hdr_t.setStyle(TableStyle([
            ('BACKGROUND', (0,0),(-1,-1), C_PRIMARY),
            ('LEFTPADDING',(0,0),(-1,-1), 10),
            ('RIGHTPADDING',(0,0),(-1,-1), 10),
            ('TOPPADDING', (0,0),(-1,-1), 3),
            ('BOTTOMPADDING',(0,0),(-1,-1),3),
            ('TOPPADDING', (0,0),(-1,0),  12),
            ('BOTTOMPADDING',(0,-1),(-1,-1),12),
        ]))
        items.append(hdr_t)
        items.append(Spacer(1, 10*mm))

        # Date right-aligned
        items.append(Paragraph(today, s('ltdate', fontName=FONT_SANS, fontSize=9, textColor=DARK, alignment=TA_RIGHT, leading=13)))
        items.append(Spacer(1, 8*mm))

        # Salutation
        items.append(Paragraph(f'Dear {bname} Team,', s('ltsal', fontName=FONT_SERIF, fontSize=11, textColor=DARK, leading=16)))
        items.append(Spacer(1, 6*mm))

        # Body paragraph 1
        p1 = (
            f'Please find enclosed your financial report for <b>{period}</b>, prepared by {prepared_by}. '
            f'This report provides a detailed review of your business\'s financial performance, '
            f'including profit &amp; loss analysis, key performance indicators, and strategic observations '
            f'designed to support informed business decisions.'
        )
        items.append(Paragraph(p1, s('ltb1', fontName=FONT_SERIF, fontSize=10, textColor=DARK, leading=17)))
        items.append(Spacer(1, 5*mm))

        # Body paragraph 2
        contact_suffix = f' You can reach us at {contact_clean}.' if contact_clean else ''
        p2 = (
            'If you have any questions about the contents of this report, or would like to discuss '
            'any of the findings in more detail, please do not hesitate to get in touch.'
            + contact_suffix
        )
        items.append(Paragraph(p2, s('ltb2', fontName=FONT_SERIF, fontSize=10, textColor=DARK, leading=17)))
        items.append(Spacer(1, 14*mm))

        # Sign off
        items.append(Paragraph('Yours sincerely,', s('ltso', fontName=FONT_SANS, fontSize=10, textColor=DARK, leading=15)))
        items.append(Spacer(1, 10*mm))
        items.append(Paragraph(prepared_by, s('ltsig', fontName=FONT_SERIF_BOLD, fontSize=12, textColor=DARK, leading=17)))

        items.append(PageBreak())
        return items
    except Exception:
        return []


# ── Build report ──────────────────────────────────────────────────────────────

def build_report(d):
    buf=io.BytesIO()

    wl_name     = str(d.get('white_label_firm','')).strip()
    wl_logo     = str(d.get('wl_logo','')).strip()
    wl_primary  = str(d.get('white_label_primary_colour','')).strip()
    wl_accent   = str(d.get('white_label_accent_colour','')).strip()
    wl_tagline  = str(d.get('white_label_tagline','')).strip()
    wl_contact  = str(d.get('white_label_contact','')).strip()
    wl_disclaimer = str(d.get('white_label_disclaimer','')).strip()
    is_wl = bool(wl_name and wl_name.upper() not in ('NA','N/A','NONE',''))
    prepared_by = wl_name if is_wl else 'FinReportAI'

    def safe_colour(hex_val, fallback):
        try:
            if hex_val and hex_val.upper() not in ('NA','N/A','','NONE'):
                h = hex_val.strip().lstrip('#')
                if len(h) == 6:
                    return colors.HexColor('#'+h)
        except: pass
        return fallback
    C_PRIMARY = safe_colour(wl_primary, NAVY)
    C_ACCENT  = safe_colour(wl_accent,  TEAL)

    import hashlib, datetime
    ref_hash = hashlib.md5(f"{d.get('business_name','')}{datetime.datetime.now().isoformat()}".encode()).hexdigest()[:8].upper()
    report_ref = f"REF-{ref_hash}"

    bname = str(d.get('business_name','Report')).replace(' ','_').replace('&','and')
    period_safe = str(d.get('period','')).split('—')[0].strip().replace(' ','_')
    firm_safe = prepared_by.replace(' ','_').replace('&','and')
    download_name = f"{firm_safe}_{bname}_{period_safe}.pdf" if is_wl else f"FinReportAI_{bname}_{period_safe}.pdf"
    d['_download_name'] = download_name

    doc=SimpleDocTemplate(buf,pagesize=A4,leftMargin=17*mm,rightMargin=17*mm,topMargin=11*mm,bottomMargin=14*mm)
    doc.title   = f"{d.get('business_name','Report')} — Financial Report — {d.get('period','')}"
    doc.author  = prepared_by
    doc.subject = f"Financial Report for {d.get('business_name','')}"

    # ── Step 8: Parse periods from d['periods'] only ─────────────────────────
    periods_raw = d.get('periods', '')
    if isinstance(periods_raw, list):
        periods_full = [str(p).strip() for p in periods_raw if str(p).strip()]
        if len(periods_full) == 1 and ',' in periods_full[0]:
            periods_full = [p.strip() for p in periods_full[0].split(',') if p.strip()]
    elif isinstance(periods_raw, (int, float)) or str(periods_raw).strip().lstrip('-').isdigit():
        periods_full = []
    else:
        _ps = str(periods_raw).strip()
        periods_full = [p.strip() for p in _ps.split(',')
                        if p.strip() and not p.strip().lstrip('-').isdigit()]
    periods_full = periods_full[:6]
    periods = [normalise_period_label(p) for p in periods_full]
    periods_keys = [p.lower().replace(' ', '').replace('-', '') for p in periods_full]

    # ── Step 1: Parse items arrays ────────────────────────────────────────────
    revenue_items = get_list(d, 'revenue_items')
    cogs_items    = get_list(d, 'cogs_items')
    opex_items    = get_list(d, 'opex_items')
    prev_revenue_items = get_list(d, 'prev_revenue_items')
    prev_cogs_items    = get_list(d, 'prev_cogs_items')
    prev_opex_items    = get_list(d, 'prev_opex_items')
    is_comparison = has_val(d.get('prev_total_revenue')) and str(d.get('prev_total_revenue','')).upper() not in ('NA','N/A','NONE','')

    # ── Step 2: Deduplicate items by label (merge values element-wise, sum totals) ──
    def _dedup(items):
        seen_order = []
        merged = {}
        for it in items:
            lbl = str(it.get('label', '')).strip().lower()
            if lbl not in merged:
                merged[lbl] = {'label': it.get('label', ''),
                               'values': [clean(v) or 0 for v in it.get('values', [])],
                               'total': clean(it.get('total'))}
                seen_order.append(lbl)
            else:
                ex = merged[lbl]
                ev = ex['values']
                nv = [clean(v) or 0 for v in it.get('values', [])]
                ln = max(len(ev), len(nv))
                ex['values'] = [(ev[j] if j < len(ev) else 0) + (nv[j] if j < len(nv) else 0)
                                for j in range(ln)]
                nt = clean(it.get('total'))
                ex['total'] = (ex['total'] or 0) + (nt or 0)
        return [merged[lbl] for lbl in seen_order]

    revenue_items = _dedup(revenue_items)
    cogs_items    = _dedup(cogs_items)
    opex_items    = _dedup(opex_items)

    # ── Step 3: Reclassify misplaced line items ───────────────────────────────
    _COGS_KW = ('inventory', 'stock', 'parts', 'components', 'materials',
                'beans', 'packaging', 'cost', 'raw')
    _OPEX_KW = ('utilities', 'power', 'insurance', 'rent', 'wages', 'salary',
                'advertising', 'marketing', 'software', 'subscriptions', 'misc',
                'professional', 'telephone', 'legal')

    def _label_lower(it):
        return str(it.get('label', '')).lower()

    _new_rev, _bump_cogs = [], []
    for _it in revenue_items:
        _ll = _label_lower(_it)
        (_bump_cogs if any(kw in _ll for kw in _COGS_KW) else _new_rev).append(_it)
    revenue_items = _new_rev
    cogs_items = cogs_items + _bump_cogs

    _new_cogs, _bump_opex = [], []
    for _it in cogs_items:
        _ll = _label_lower(_it)
        (_bump_opex if any(kw in _ll for kw in _OPEX_KW) else _new_cogs).append(_it)
    cogs_items = _new_cogs
    opex_items = opex_items + _bump_opex

    # ── Step 4: Canonical totals from item.total fields ───────────────────────
    canonical_revenue = sum(clean(it.get('total')) or 0 for it in revenue_items) or None
    canonical_cogs    = sum(clean(it.get('total')) or 0 for it in cogs_items)    or None
    canonical_opex    = sum(clean(it.get('total')) or 0 for it in opex_items)    or None
    _cr = canonical_revenue or 0
    _cc = canonical_cogs    or 0
    _co = canonical_opex    or 0
    canonical_gross_profit = (_cr - _cc)       if canonical_revenue is not None else None
    canonical_net_profit   = (_cr - _cc - _co) if canonical_revenue is not None else None
    canonical_gross_margin = ((_cr - _cc) / _cr * 100)       if _cr > 0 else None
    canonical_net_margin   = ((_cr - _cc - _co) / _cr * 100) if _cr > 0 else None

    # ── Step 5: Per-period values unconditionally from items ──────────────────
    for i, k in enumerate(periods_keys):
        _pv_rev  = sum(clean(it.get('values', [])[i]) or 0 for it in revenue_items if i < len(it.get('values', [])))
        _pv_cogs = sum(clean(it.get('values', [])[i]) or 0 for it in cogs_items    if i < len(it.get('values', [])))
        _pv_opex = sum(clean(it.get('values', [])[i]) or 0 for it in opex_items    if i < len(it.get('values', [])))
        _pv_gp   = _pv_rev - _pv_cogs
        _pv_np   = _pv_rev - _pv_cogs - _pv_opex
        _pv_nm   = (_pv_np / _pv_rev * 100) if _pv_rev > 0 else 0
        d['revenue_'      + k] = _pv_rev
        d['cogs_'         + k] = _pv_cogs
        d['opex_'         + k] = _pv_opex
        d['gross_profit_' + k] = _pv_gp
        d['net_profit_'   + k] = _pv_np
        d['net_margin_'   + k] = _pv_nm

    # ── Step 6: Write canonical totals back to d (overwrite Claude's values) ──
    if canonical_revenue      is not None: d['total_revenue'] = canonical_revenue
    if canonical_cogs         is not None: d['total_cogs']    = canonical_cogs
    if canonical_opex         is not None: d['total_opex']    = canonical_opex
    if canonical_gross_profit is not None: d['gross_profit']  = canonical_gross_profit
    if canonical_net_profit   is not None: d['net_profit']    = canonical_net_profit
    if canonical_gross_margin is not None: d['gross_margin']  = canonical_gross_margin
    if canonical_net_margin   is not None: d['net_margin']    = canonical_net_margin

    # ── Step 7: Update each item's .total = sum of its values ─────────────────
    for _it in revenue_items + cogs_items + opex_items:
        _it['total'] = sum(clean(v) or 0 for v in _it.get('values', []))

    period_rev = [d.get('revenue_'+k) for k in periods_keys]
    opex_with_totals = [it for it in opex_items if has_val(it.get('total'))]
    total_r = clean(d.get('total_revenue'))

    # ── New field extraction ──────────────────────────────────────────────────
    health_score          = clean(d.get('health_score'))
    recommendations       = d.get('strategic_recommendations')
    plain_english_summary = str(d.get('plain_english_summary','')).strip()
    forecast_period  = str(d.get('forecast_period','')).strip()
    forecast_rev     = clean(d.get('forecast_revenue'))
    forecast_profit  = clean(d.get('forecast_profit'))
    forecast_text    = str(d.get('forecast_narrative','')).strip()
    industry_context = str(d.get('industry_context','')).strip()
    accountant_notes = str(d.get('accountant_notes','')).strip()
    goals_raw        = d.get('client_targets')
    client_logo      = str(d.get('client_logo','')).strip()
    client_accent    = str(d.get('client_accent_colour','')).strip()
    has_cashflow     = any(has_val(d.get(k)) for k in ['cash_operating','cash_investing','cash_financing','net_cash'])
    has_balsheet     = any(has_val(d.get(k)) for k in ['total_assets','total_liabilities','total_equity'])
    has_forecast     = bool(forecast_rev or forecast_profit or forecast_text)
    has_goals        = bool(goals_raw and str(goals_raw).strip() not in ('','NA','N/A','NONE','[]'))
    has_industry     = bool(industry_context and industry_context.upper() not in ('NA','N/A','NONE',''))
    has_notes        = bool(accountant_notes and accountant_notes.upper() not in ('NA','N/A','NONE',''))
    has_recs         = bool(recommendations and str(recommendations).strip() not in ('','NA','N/A','NONE','[]'))
    has_health       = health_score is not None
    has_plain_summary = bool(plain_english_summary and plain_english_summary.upper() not in ('NA','N/A','NONE',''))

    # Per-client accent colour (overrides firm accent if provided)
    def safe_colour(hex_val, fallback):
        try:
            if hex_val and hex_val.upper() not in ('NA','N/A','','NONE'):
                h = hex_val.strip().lstrip('#')
                if len(h) == 6: return colors.HexColor('#'+h)
        except: pass
        return fallback
    if client_accent:
        C_ACCENT = safe_colour(client_accent, C_ACCENT)

    # ── TOC section list ─────────────────────────────────────────────────────
    toc_sections = ['Executive Summary']
    if periods and any(has_val(v) for v in period_rev):
        toc_sections.append('Revenue Performance & Margins')
    if opex_with_totals:
        toc_sections.append('Operating Expense Breakdown')
    if revenue_items or cogs_items or opex_items or has_val(d.get('total_revenue')):
        toc_sections.append('Profit & Loss Statement')
        if has_val(d.get('total_cogs')) or has_val(d.get('total_opex')):
            toc_sections.append('P&L Waterfall')
    if has_cashflow:
        toc_sections.append('Cash Flow Summary')
    if has_balsheet:
        toc_sections.append('Balance Sheet Snapshot')
    if has_val(d.get('net_profit')) and (clean(d.get('net_profit')) or 0) > 0:
        toc_sections.append('Corporation Tax Estimate')
    if has_goals:
        toc_sections.append('Goals & Targets')
    if has_industry:
        toc_sections.append('Industry Context')
    if d.get('analysis'):
        toc_sections.append('Key Trends & Analysis')
    if has_recs:
        toc_sections.append('Recommendations')
    if has_forecast:
        toc_sections.append('Forecast')

    raw_flags = str(d.get('flags',''))
    flag_lines = [f.strip() for f in raw_flags.replace('FLAGSEP','\n').split('\n') if '|' in f and len(f.strip())>3]
    if flag_lines:
        toc_sections.append('Flags & Items to Watch')
    if has_notes:
        toc_sections.append("Accountant's Notes")
    if d.get('outlook'):
        toc_sections.append('Outlook')
    toc_sections.append('Glossary')

    story = []

    # ── Cover page ────────────────────────────────────────────────────────────
    try:
        cover_els = cover_page_elements(d, C_PRIMARY, prepared_by, is_wl, wl_logo, wl_tagline, report_ref)
        story.extend(cover_els)
    except Exception:
        pass

    # ── Table of contents ─────────────────────────────────────────────────────
    try:
        toc_els = toc_elements(toc_sections, C_ACCENT)
        story.extend(toc_els)
    except Exception:
        pass

    # ── Introduction letter (item 5, white label only) ────────────────────────
    try:
        letter_els = intro_letter(d, prepared_by, is_wl, wl_contact, C_PRIMARY)
        story.extend(letter_els)
    except Exception:
        pass

    # The per-page header is drawn by PageNumCanvas on pages 2+ via canvas overlay.
    story.append(Spacer(1,2*mm))

    # ── Glossary callout (item 4) ─────────────────────────────────────────────
    try:
        gco_t = Table([[Paragraph(
            'New to financial reports? Key terms are explained in the <b>Glossary</b> on the final page.',
            s('gco', fontName=FONT_SANS, fontSize=7.5, textColor=WHITE, leading=11, alignment=TA_CENTER),
        )]], colWidths=[175*mm])
        gco_t.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,-1), TEAL),
            ('TOPPADDING',    (0,0),(-1,-1), 5),
            ('BOTTOMPADDING', (0,0),(-1,-1), 5),
            ('LEFTPADDING',   (0,0),(-1,-1), 8),
            ('RIGHTPADDING',  (0,0),(-1,-1), 8),
        ]))
        story.append(gco_t)
        story.append(Spacer(1, 3*mm))
    except Exception:
        pass

    # ── Executive Summary ─────────────────────────────────────────────────────
    story.append(KeepTogether([section_header('Executive Summary', C_ACCENT), Spacer(1,3*mm)]))
    if is_wl:
        intro_text = f"This report has been prepared by {wl_name} for {d.get('business_name','the client')} covering the period {str(d.get('period','')).split('—')[0].strip()}. It is intended for internal management use only."
        story.append(Paragraph(intro_text, s('intro',fontSize=8.5,textColor=colors.HexColor('#6B7280'),leading=13,fontName=FONT_SANS)))
        story.append(Spacer(1,2*mm))
    if is_comparison:
        try:
            cex = comparison_executive_box(d, C_ACCENT)
            if cex: story.append(KeepTogether([cex, Spacer(1,3*mm)]))
        except Exception:
            pass
    # Health score verdict sentence (item 8)
    if has_health:
        if health_score >= 8:
            verdict_txt = '<b>Overall:</b> Strong period — the business is performing well across key indicators.'
        elif health_score >= 5:
            verdict_txt = '<b>Overall:</b> Solid period with some areas for improvement identified.'
        else:
            verdict_txt = '<b>Overall:</b> This period requires management attention across several key metrics.'
        story.append(Paragraph(verdict_txt, s('verdict', fontName=FONT_SANS, fontSize=9, textColor=DARK, leading=13)))
        story.append(Spacer(1,2*mm))
    story.append(Paragraph(str(d.get('executive_summary','No summary provided.')),ST_BODY))
    # Confidence indicator (item 6)
    try:
        _n_per = len([v for v in period_rev if has_val(v)]) or max(len(periods), 1)
        if _n_per >= 3:
            _conf_txt = f'Analysis confidence: High — based on {_n_per} periods of data.'
        elif _n_per == 2:
            _conf_txt = f'Analysis confidence: Moderate — based on {_n_per} periods of data.'
        else:
            _conf_txt = 'Analysis confidence: Low — based on single period data.'
        story.append(Paragraph(_conf_txt, s('conf', fontName=FONT_SERIF_IT, fontSize=7.5, textColor=GRAY, leading=11)))
    except Exception:
        pass
    story.append(Spacer(1,3*mm))
    # "What this means for you" plain-English callout (item 5)
    if has_plain_summary:
        try:
            pes_box = Table(
                [[Paragraph(plain_english_summary, s('pes', fontName=FONT_SANS, fontSize=9, textColor=colors.HexColor('#1A3A2A'), leading=14))]],
                colWidths=[175*mm],
            )
            pes_box.setStyle(TableStyle([
                ('BOX',          (0,0),(-1,-1), 1,   C_ACCENT),
                ('LINEBEFORE',   (0,0),(0,-1),  4,   C_ACCENT),
                ('BACKGROUND',   (0,0),(-1,-1),      TEAL_LITE),
                ('TOPPADDING',   (0,0),(-1,-1), 8),
                ('BOTTOMPADDING',(0,0),(-1,-1), 8),
                ('LEFTPADDING',  (0,0),(-1,-1), 10),
                ('RIGHTPADDING', (0,0),(-1,-1), 8),
            ]))
            story.append(KeepTogether([
                Paragraph('What This Means for You', s('wms', fontName=FONT_SANS_BOLD, fontSize=8.5, textColor=C_ACCENT, leading=12)),
                Spacer(1,2*mm), pes_box, Spacer(1,3*mm),
            ]))
        except Exception:
            pass

    # ── KPI Cards ─────────────────────────────────────────────────────────────
    if is_comparison:
        kpis = [
            comparison_kpi_card('Total Revenue', d.get('total_revenue'), d.get('prev_total_revenue'), False),
            comparison_kpi_card('Net Profit', d.get('net_profit'), d.get('prev_net_profit'), False),
            comparison_kpi_card('Gross Margin', d.get('gross_margin'), d.get('prev_gross_margin'), True),
            comparison_kpi_card('Net Margin', d.get('net_margin'), d.get('prev_net_margin'), True),
        ]
    else:
        kpi_defs = [
            (fmt(d.get('total_revenue')),'Total Revenue',d.get('period','')),
            (fmt(d.get('net_profit')),'Net Profit',d.get('period','')),
            (fmtp(d.get('gross_margin')),'Gross Margin','Average'),
            (fmtp(d.get('net_margin')),'Net Margin','Average'),
        ]
        kpis = [kpi_card(v,l,sub) for (v,l,sub) in kpi_defs]

    # Add health score as 5th card if available
    if has_health:
        try:
            hc = health_kpi_card(health_score)
            if hc: kpis.append(hc)
        except Exception:
            pass

    ncards = len(kpis)
    kpi_row = Table([kpis], colWidths=[38*mm]*ncards)
    kpi_row.setStyle(TableStyle([
        ('LEFTPADDING',(0,0),(-1,-1),2),('RIGHTPADDING',(0,0),(-1,-1),2),
        ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
    ]))
    story.append(KeepTogether([kpi_row, Spacer(1,3*mm)]))

    # ── Traffic Light Dashboard ───────────────────────────────────────────────
    try:
        tld = traffic_light_dashboard(d, C_ACCENT, period_revs=period_rev)
        if tld:
            story.append(KeepTogether([
                section_header('At a Glance', C_ACCENT),
                Spacer(1,3*mm), tld, Spacer(1,3*mm),
            ]))
    except Exception:
        pass

    # ── Report Card (item 1) ──────────────────────────────────────────────────
    try:
        rc = report_card_section(d, C_ACCENT)
        if rc:
            story.append(KeepTogether([
                section_header('Report Card', C_ACCENT),
                Spacer(1,3*mm), rc, Spacer(1,3*mm),
            ]))
    except Exception:
        pass

    # ── Management Summary Box ────────────────────────────────────────────────
    try:
        msb = management_summary_box(d, C_ACCENT)
        if msb:
            story.append(KeepTogether([msb, Spacer(1,3*mm)]))
    except Exception:
        pass

    # ── Since Last Period Banner (comparison only) ────────────────────────────
    if is_comparison:
        try:
            slp = since_last_period_banner(d, C_ACCENT)
            if slp:
                story.append(KeepTogether([slp, Spacer(1,3*mm)]))
        except Exception:
            pass

    # ── Period Comparison Summary (comparison reports only) ───────────────────
    if is_comparison:
        try:
            csb = comparison_summary_box(d, C_ACCENT)
            if csb:
                story.append(KeepTogether([
                    section_header('Period Comparison Summary', C_ACCENT),
                    Spacer(1,3*mm), csb, Spacer(1,3*mm),
                ]))
        except Exception:
            pass

    # ── Revenue Performance & Margins ─────────────────────────────────────────
    if periods and any(has_val(v) for v in period_rev):
        chart = bar_chart(periods, period_rev, show_trend=True, C_ACCENT=C_ACCENT)
        nm_period = [(p, d.get('net_margin_'+k)) for p,k in zip(periods,periods_keys) if has_val(d.get('net_margin_'+k))]
        nm_vals_clean = [clean(v) for _,v in nm_period if clean(v) is not None]
        if len(nm_vals_clean) >= 2:
            nm_diff = nm_vals_clean[-1] - nm_vals_clean[0]
            if nm_diff > 0.5:
                mt_txt = '▲ Margins improving'; mt_col = GREEN_TEXT
            elif nm_diff < -0.5:
                mt_txt = '▼ Margins declining'; mt_col = RED_TEXT
            else:
                mt_txt = '● Margins stable'; mt_col = GRAY
            margin_trend_para = Paragraph(mt_txt, s('mtrend', fontSize=7, textColor=mt_col, leading=10))
        else:
            margin_trend_para = None
        margin_rows=[
            [Paragraph('Margin Analysis',s('ma',fontName=FONT_SANS_BOLD,fontSize=8,textColor=NAVY,leading=12))],
            [Spacer(1,2*mm)],
        ]
        if has_val(d.get('gross_margin')):
            margin_rows += [[Paragraph('Gross Margin',ST_SMALL)],[margin_bar(d.get('gross_margin'),'Average',TEAL)],[Spacer(1,1*mm)]]
            if margin_trend_para:
                margin_rows += [[margin_trend_para],[Spacer(1,1*mm)]]
        if nm_period:
            margin_rows += [[Paragraph('Net Margin by Period',ST_SMALL)]]
            palette=[RED_TEXT,GOLD,GREEN_TEXT,TEAL,colors.HexColor('#0B6E60'),NAVY]
            for i,(p,v) in enumerate(nm_period):
                margin_rows += [[margin_bar(v, normalise_period_label(p), palette[i%len(palette)])],[Spacer(1,1*mm)]]
        rev_with_totals = [it for it in revenue_items if has_val(it.get('total'))]
        if len(rev_with_totals) >= 2:
            grand = sum(clean(it.get('total')) for it in rev_with_totals)
            if grand>0:
                margin_rows += [[Spacer(1,1*mm)],[Paragraph('Revenue Mix',ST_SMALL)]]
                palette2=[TEAL,colors.HexColor('#0B6E60'),colors.HexColor('#084F45'),colors.HexColor('#0D9E89')]
                for i,it in enumerate(rev_with_totals[:4]):
                    pctv = clean(it.get('total'))/grand
                    margin_rows += [[margin_bar(pctv, f"{it.get('label','')[:18]} {pctv:.0%}", palette2[i%len(palette2)])],[Spacer(1,1*mm)]]
        m_t=Table(margin_rows,colWidths=[70*mm])
        m_t.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
        combined=Table([[chart,m_t]],colWidths=[100*mm,75*mm])
        combined.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
        rev_section_els = [
            section_header('Revenue Performance & Margins', C_ACCENT),
            Spacer(1,3*mm), combined, Spacer(1,3*mm),
        ]
        if is_comparison:
            try:
                mct = margin_comparison_table(d, C_ACCENT)
                if mct:
                    rev_section_els += [
                        section_header('Margin Comparison', C_ACCENT),
                        Spacer(1,3*mm), mct, Spacer(1,3*mm),
                    ]
            except Exception:
                pass
        story.append(KeepTogether(rev_section_els[:4]))  # keep first block together
        for el in rev_section_els[4:]: story.append(el)

        # Seasonal trend note (item 7)
        try:
            _pr_clean = [clean(v) for v in period_rev if clean(v) is not None]
            if len(_pr_clean) >= 3:
                _mean_r = sum(_pr_clean) / len(_pr_clean)
                _std    = (sum((v - _mean_r)**2 for v in _pr_clean) / len(_pr_clean)) ** 0.5
                if _mean_r > 0 and _std / _mean_r > 0.25:
                    _existing_titles = {fl.split('|')[1].lower() for fl in flag_lines if len(fl.split('|')) >= 2}
                    if not any('season' in t for t in _existing_titles):
                        _seas_body = (
                            'Revenue shows significant variation across periods. '
                            'This may reflect normal seasonal trading patterns. '
                            'Consider whether seasonal cash flow planning strategies are in place.'
                        )
                        story.append(KeepTogether([
                            flag_card('★', 'Seasonal Variation Detected', _seas_body, 'INFO'),
                            Spacer(1, 2*mm),
                        ]))
        except Exception:
            pass

    # ── Expense Breakdown + Pie chart ─────────────────────────────────────────
    if opex_with_totals:
        cards = []
        for it in opex_with_totals[:5]:
            tv  = clean(it.get('total'))
            pct = (tv/total_r*100) if (total_r and total_r > 0) else None
            raw_lbl = it.get('label','')
            # Truncate at word boundary max 16 chars
            if len(raw_lbl) > 16:
                words = raw_lbl.split()
                lbl = ''
                for w in words:
                    if len(lbl) + len(w) + (1 if lbl else 0) <= 15:
                        lbl += (' ' if lbl else '') + w
                    else:
                        break
                if not lbl: lbl = raw_lbl[:15]
            else:
                lbl = raw_lbl
            cards.append(exp_card(lbl, tv, pct))

        row1_cards = cards[:3]; row2_cards = cards[3:]
        row1 = Table([row1_cards], colWidths=[38*mm]*len(row1_cards))
        row1.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),1),('RIGHTPADDING',(0,0),(-1,-1),1),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))

        cards_block_rows = [[row1]]
        if row2_cards:
            row2 = Table([row2_cards], colWidths=[38*mm]*len(row2_cards))
            row2.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),1),('RIGHTPADDING',(0,0),(-1,-1),1),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
            cards_block_rows += [[Spacer(1,2*mm)],[row2]]

        cards_block = Table(cards_block_rows, colWidths=[116*mm])
        cards_block.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))

        try:
            pie = expense_pie_chart(
                [it.get('label','') for it in opex_with_totals],
                [it.get('total') for it in opex_with_totals],
                w=55, h=65,
            ) if (HAS_PIE and len(opex_with_totals) >= 2) else None
        except Exception:
            pie = None

        if pie:
            combined_exp = Table([[cards_block, pie]], colWidths=[118*mm, 57*mm])
            combined_exp.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
            content = combined_exp
        else:
            content = cards_block

        story.append(KeepTogether([
            section_header('Operating Expense Breakdown', C_ACCENT),
            Spacer(1, 3*mm),
            content,
            Spacer(1, 3*mm),
        ]))

    # ── P&L Table ─────────────────────────────────────────────────────────────
    if revenue_items or cogs_items or opex_items or has_val(d.get('total_revenue')):
        story.append(KeepTogether([section_header('Full Profit & Loss Statement', C_ACCENT),Spacer(1,3*mm)]))
        if is_comparison:
            story.append(comparison_pl_table(d, periods, periods_keys, revenue_items, cogs_items, opex_items, prev_revenue_items, prev_cogs_items, prev_opex_items, C_ACCENT))
        else:
            story.append(pl_table(d, periods, periods_keys, revenue_items, cogs_items, opex_items, periods_full=periods_full))
        story.append(Spacer(1,3*mm))

        # Waterfall
        try:
            if is_comparison:
                wf = dual_waterfall_chart(d, C_ACCENT)
            else:
                wf = waterfall_chart(d.get('total_revenue'), d.get('total_cogs'), d.get('total_opex'), d.get('net_profit'))
            if wf:
                story.append(section_header('P&L Waterfall', C_ACCENT))
                story.append(Spacer(1,3*mm))
                story.append(wf)
                story.append(Spacer(1,3*mm))
        except Exception:
            pass

        # ── Peer Comparison (item 2) ──────────────────────────────────────────
        try:
            pc_t = peer_comparison_section(d, C_ACCENT)
            if pc_t:
                story.append(KeepTogether([
                    section_header('Peer Comparison', C_ACCENT),
                    Spacer(1,3*mm), pc_t, Spacer(1,3*mm),
                ]))
        except Exception:
            pass

        # ── Corporation Tax Estimate (after P&L) ─────────────────────────────
        try:
            tax_t = tax_estimate_section(d.get('net_profit'), C_ACCENT)
            if tax_t:
                story.append(KeepTogether([
                    section_header('Corporation Tax Estimate', C_ACCENT),
                    Spacer(1,3*mm), tax_t, Spacer(1,3*mm),
                ]))
        except Exception:
            pass

        # ── Salary optimisation note (item 9) ────────────────────────────────
        try:
            _sal_np = clean(d.get('net_profit'))
            if _sal_np is not None and _sal_np > 50000:
                _sal_txt = (
                    '<b>Owner-Managed Business Note:</b> With net profit exceeding £50,000, there may be '
                    'opportunities to optimise your salary and dividend split to reduce overall tax liability. '
                    'Discuss with your accountant.'
                )
                _sal_t = Table(
                    [[Paragraph(_sal_txt, s('saln', fontName=FONT_SANS, fontSize=8.5, textColor=DARK, leading=13))]],
                    colWidths=[175*mm],
                )
                _sal_t.setStyle(TableStyle([
                    ('BACKGROUND',    (0,0),(-1,-1), OFFWHITE),
                    ('LINEBEFORE',    (0,0),(0,-1),  4, GOLD),
                    ('BOX',           (0,0),(-1,-1), 0.5, BORDER),
                    ('TOPPADDING',    (0,0),(-1,-1), 8),
                    ('BOTTOMPADDING', (0,0),(-1,-1), 8),
                    ('LEFTPADDING',   (0,0),(-1,-1), 12),
                    ('RIGHTPADDING',  (0,0),(-1,-1), 10),
                ]))
                story.append(KeepTogether([_sal_t, Spacer(1, 3*mm)]))
        except Exception:
            pass

        # ── Break-Even Analysis (item 4) ──────────────────────────────────────
        try:
            be_t = breakeven_section(d, C_ACCENT)
            if be_t:
                story.append(KeepTogether([
                    section_header('Break-Even Analysis', C_ACCENT),
                    Spacer(1,3*mm), be_t, Spacer(1,3*mm),
                ]))
        except Exception:
            pass

    # ── Cash Flow ─────────────────────────────────────────────────────────────
    if has_cashflow:
        try:
            cf = cash_flow_section(d, C_ACCENT, ncols=max(len(periods), 1))
            if cf:
                story.append(KeepTogether([
                    section_header('Cash Flow Summary', C_ACCENT),
                    Spacer(1,3*mm), cf, Spacer(1,3*mm),
                ]))
        except Exception:
            pass

    # ── Balance Sheet ─────────────────────────────────────────────────────────
    if has_balsheet:
        try:
            bs = balance_sheet_section(d, C_ACCENT)
            if bs:
                story.append(KeepTogether([
                    section_header('Balance Sheet Snapshot', C_ACCENT),
                    Spacer(1,3*mm), bs, Spacer(1,3*mm),
                ]))
        except Exception:
            pass

    # ── Goals & Targets ───────────────────────────────────────────────────────
    if has_goals:
        try:
            goals_t = goals_section(goals_raw, d, C_ACCENT)
            if goals_t:
                story.append(KeepTogether([
                    section_header('Goals & Targets', C_ACCENT),
                    Spacer(1,3*mm), goals_t, Spacer(1,3*mm),
                ]))
        except Exception:
            pass

    # ── Industry Context ──────────────────────────────────────────────────────
    if has_industry:
        story.append(KeepTogether([
            section_header('Industry Context', C_ACCENT), Spacer(1,3*mm),
            Paragraph(industry_context, ST_BODY), Spacer(1,3*mm),
        ]))

    # ── Key Trends ────────────────────────────────────────────────────────────
    if d.get('analysis'):
        story.append(KeepTogether([
            section_header('Key Trends & Analysis', C_ACCENT),Spacer(1,3*mm),
            Paragraph(str(d.get('analysis')),ST_BODY),
            Spacer(1,3*mm),
        ]))

    # ── Recommendations ───────────────────────────────────────────────────────
    if has_recs:
        try:
            rec_els = recommendations_elements(recommendations, C_ACCENT)
            if rec_els:
                story.append(section_header('Recommendations', C_ACCENT))
                story.append(Spacer(1,3*mm))
                for el in rec_els: story.append(el)
                story.append(Spacer(1,3*mm))
        except Exception:
            pass

    # ── Next 90 Days Action Plan (item 3) ────────────────────────────────────
    try:
        nd_els = next_90_days_section(d, C_ACCENT)
        if nd_els:
            story.append(section_header('Your Next 90 Days', C_ACCENT))
            story.append(Spacer(1,3*mm))
            for el in nd_els: story.append(el)
            story.append(Spacer(1,3*mm))
    except Exception:
        pass

    # ── Questions to Discuss (item 2) ────────────────────────────────────────
    try:
        qs = questions_section(d, C_ACCENT)
        if qs:
            story.append(KeepTogether([
                section_header('Questions to Discuss', C_ACCENT),
                Spacer(1,3*mm), qs, Spacer(1,3*mm),
            ]))
    except Exception:
        pass

    # ── Forecast ──────────────────────────────────────────────────────────────
    if has_forecast:
        try:
            fc_els = forecast_section(d, C_ACCENT)
            if fc_els:
                story.append(section_header('Forecast', C_ACCENT))
                story.append(Spacer(1,3*mm))
                for el in fc_els: story.append(el)
                story.append(Spacer(1,3*mm))
        except Exception:
            pass

    # ── Key Wins (item 3) ─────────────────────────────────────────────────────
    if flag_lines:
        try:
            kw = key_wins_section(flag_lines, C_ACCENT)
            if kw:
                story.append(KeepTogether([kw, Spacer(1,3*mm)]))
        except Exception:
            pass

    # ── Flags ─────────────────────────────────────────────────────────────────
    if flag_lines:
        pos_count   = sum(1 for fl in flag_lines if fl.split('|')[0].strip().upper() == 'POSITIVE')
        watch_count = sum(1 for fl in flag_lines if fl.split('|')[0].strip().upper() in ('WATCH', 'INFO'))
        risk_count  = sum(1 for fl in flag_lines if fl.split('|')[0].strip().upper() == 'RISK')
        fsum_parts = []
        if pos_count:   fsum_parts.append(f'<font color="#15803D"><b>{pos_count} positive</b></font>')
        if watch_count: fsum_parts.append(f'<font color="#92400E"><b>{watch_count} watch</b></font>')
        if risk_count:  fsum_parts.append(f'<font color="#B91C1C"><b>{risk_count} risk</b></font>')
        fsum_para = Paragraph(' · '.join(fsum_parts), s('flagsum', fontSize=8, leading=12)) if fsum_parts else None
        hdr_block = [section_header('Flags & Items to Watch', C_ACCENT), Spacer(1,2*mm)]
        if fsum_para:
            hdr_block += [fsum_para, Spacer(1,3*mm)]
        else:
            hdr_block.append(Spacer(1,3*mm))
        story.append(KeepTogether(hdr_block))
        for i,fl in enumerate(flag_lines):
            parts = fl.split('|')
            if len(parts) >= 3:
                severity=parts[0].strip(); title=parts[1].strip(); body=parts[2].strip()
            elif len(parts) == 2:
                severity='WATCH'; title='Flag'; body=parts[1].strip()
            else:
                severity='WATCH'; title='Flag'; body=fl.strip()
            story.append(KeepTogether([flag_card(i+1,title,body,severity),Spacer(1,2*mm)]))
        # VAT threshold alert (item 6)
        try:
            rev_v = clean(d.get('total_revenue'))
            if rev_v is not None and 70000 <= rev_v <= 90000:
                vat_body = (
                    f'Revenue of {fmt(rev_v)} is approaching the UK VAT registration threshold of £85,000. '
                    'If turnover exceeds this threshold in any 12-month rolling period, VAT registration '
                    'becomes mandatory. Consider reviewing pricing strategy and cash flow implications in advance.'
                )
                story.append(KeepTogether([
                    flag_card(len(flag_lines)+1, 'VAT Registration Threshold Alert', vat_body, 'INFO'),
                    Spacer(1,2*mm),
                ]))
        except Exception:
            pass
        story.append(Spacer(1,3*mm))

    # ── Accountant's Notes ────────────────────────────────────────────────────
    if has_notes:
        try:
            notes_el = accountant_notes_element(accountant_notes, C_ACCENT)
            if notes_el:
                story.append(KeepTogether([
                    section_header("Accountant's Notes", C_ACCENT),
                    Spacer(1,3*mm), notes_el, Spacer(1,3*mm),
                ]))
        except Exception:
            pass

    # ── Outlook ───────────────────────────────────────────────────────────────
    if d.get('outlook'):
        story.append(KeepTogether([
            section_header('Outlook', C_ACCENT),Spacer(1,3*mm),
            Paragraph(str(d.get('outlook')),ST_BODY),
            Spacer(1,3*mm),
        ]))

    # ── Assumptions & Limitations (item 9) ───────────────────────────────────
    try:
        asn = assumptions_section(C_ACCENT)
        if asn:
            story.append(KeepTogether([
                section_header('Assumptions & Limitations', C_ACCENT),
                Spacer(1,3*mm), asn, Spacer(1,3*mm),
            ]))
    except Exception:
        pass

    # ── Glossary ──────────────────────────────────────────────────────────────
    try:
        gloss_active = {'revenue', 'gross profit', 'gross margin', 'net profit', 'net margin'}
        if has_val(d.get('total_cogs')) or cogs_items: gloss_active.update({'cogs', 'goods', 'sold'})
        if has_val(d.get('total_opex')) or opex_items: gloss_active.update({'opex', 'operating', 'expenses'})
        if is_comparison: gloss_active.update({'period', 'period-over-period'})
        if has_balsheet: gloss_active.update({'working', 'capital'})
        if has_val(d.get('net_profit')) and (clean(d.get('net_profit')) or 0) > 0: gloss_active.update({'corporation', 'tax'})
        if has_val(d.get('ebitda')): gloss_active.add('ebitda')
        gloss = glossary_section(C_ACCENT, active_terms=gloss_active)
        if gloss:
            from reportlab.platypus import CondPageBreak
            story.append(CondPageBreak(60*mm))
            story.append(KeepTogether([section_header('Glossary of Financial Terms', C_ACCENT), Spacer(1,3*mm)]))
            story.append(gloss)
            story.append(Spacer(1,3*mm))
    except Exception:
        pass

    # ── Footer ────────────────────────────────────────────────────────────────
    contact_str = f" &nbsp;·&nbsp; {wl_contact}" if wl_contact and wl_contact.upper() not in ('NA','N/A','NONE','') else ''
    disclaimer_row = []
    if wl_disclaimer and wl_disclaimer.upper() not in ('NA','N/A','NONE',''):
        disclaimer_row = [Paragraph(wl_disclaimer,s('disc',fontSize=7,textColor=colors.HexColor('#9CA3AF'),alignment=TA_CENTER,leading=10))]
    period_short = str(d.get('period','')).split('—')[0].strip()
    gen_date = datetime.datetime.now().strftime('%d %b %Y')
    if is_wl and contact_str:
        line1 = f"Prepared by {prepared_by}{contact_str}"
        line2 = f"{period_short} &nbsp;·&nbsp; Ref: {report_ref} &nbsp;·&nbsp; Generated {gen_date} &nbsp;·&nbsp; Confidential"
        main_footer = [
            Paragraph(line1,s('ftxt',fontSize=6,textColor=colors.HexColor('#6B7280'),alignment=TA_CENTER,leading=9)),
            Paragraph(line2,s('ftxt2',fontSize=6,textColor=colors.HexColor('#6B7280'),alignment=TA_CENTER,leading=9)),
        ]
    else:
        main_footer = [Paragraph(f"Prepared by {prepared_by} &nbsp;·&nbsp; {period_short} &nbsp;·&nbsp; Ref: {report_ref} &nbsp;·&nbsp; Generated {gen_date} &nbsp;·&nbsp; Confidential",s('ftxt',fontSize=6,textColor=colors.HexColor('#6B7280'),alignment=TA_CENTER,leading=9))]
    ft_rows = []
    if disclaimer_row:
        for item in disclaimer_row: ft_rows.append([item])
    for item in main_footer: ft_rows.append([item])
    ft=Table(ft_rows,colWidths=[175*mm])
    ft.setStyle(TableStyle([('LINEABOVE',(0,0),(-1,0),0.5,BORDER),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),4),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
    story.append(ft)

    _canvas_bname    = str(d.get('business_name', ''))
    _canvas_period   = str(d.get('period', ''))
    _canvas_prep_by  = prepared_by

    class PageNumCanvas(rl_canvas.Canvas):
        def __init__(self, *args, **kwargs):
            rl_canvas.Canvas.__init__(self, *args, **kwargs)
            self._saved_page_states = []
            # Fill full A4 page with cover colour so side margins aren't white
            self.saveState()
            self.setFillColor(C_PRIMARY)
            self.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
            self.restoreState()
        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()
        def save(self):
            num_pages = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self.draw_page_number(num_pages)
                rl_canvas.Canvas.showPage(self)
            rl_canvas.Canvas.save(self)
        def draw_page_number(self, page_count):
            if self._pageNumber > 1:
                # ── Slim header bar ───────────────────────────────────────
                self.saveState()
                self.setFillColor(C_PRIMARY)
                self.rect(0, A4[1] - 8*mm, A4[0], 8*mm, fill=1, stroke=0)
                self.setFillColor(WHITE)
                self.setFont(FONT_SANS_BOLD, 7)
                self.drawString(17*mm, A4[1] - 5.2*mm, _canvas_bname)
                self.setFont(FONT_SANS, 7)
                self.setFillColor(colors.HexColor('#9BB5D4'))
                self.drawRightString(A4[0] - 17*mm, A4[1] - 5.2*mm,
                                     f'{_canvas_period}  \xb7  {_canvas_prep_by}')
                self.restoreState()
            # ── Footer rule ───────────────────────────────────────────
            self.saveState()
            self.setStrokeColor(BORDER)
            self.setLineWidth(0.3)
            self.line(0, 14*mm, A4[0], 14*mm)
            self.restoreState()
            # ── Page number ───────────────────────────────────────────
            self.setFont(FONT_SANS, 7)
            self.setFillColor(colors.HexColor('#6B7280'))
            self.drawCentredString(A4[0]/2, 5*mm, f'Page {self._pageNumber} of {page_count}')

    doc.build(story, canvasmaker=PageNumCanvas)
    buf.seek(0)
    return buf

# ── Claude prompt schema for the three insight keys ──────────────────────────
_KEY_SCHEMA = {
    "key_takeaways": (
        "A JSON array of exactly 3 strings. Each string is one punchy sentence summarising "
        "what actually happened in the historical data this period — specific to the actual "
        "numbers, past tense, no generic advice. "
        'Example: "E-Bike rentals scaled to 26% of March revenue following a strong launch month."'
    ),
    "strategic_recommendations": (
        "A JSON array of exactly 3 strings. Each string is one specific forward-looking strategic "
        "action the business should take based on the data. Be specific to the actual numbers — "
        "not generic advice. "
        'Example: "Secure 5-10 additional e-bikes ahead of peak summer season to capitalise on the 312% March revenue surge."'
    ),
    "timeline_90_days": (
        "A JSON array of exactly 3 strings. Each string represents one month of an execution plan "
        'in chronological order. Format each as "Month X: [specific action]". Base the actions on '
        "the actual data findings. "
        'Example: "Month 1: Investigate the February cafe footfall dip and identify whether it was '
        "weather, marketing, or operational. Month 2: Negotiate supplier terms for expanded e-bike "
        "inventory based on March demand data. Month 3: Deploy targeted local marketing tracking "
        'customer acquisition cost against the new revenue baseline."'
    ),
}

@app.route('/prompt-schema', methods=['GET'])
def prompt_schema():
    """Returns the three required insight key descriptions to paste into your Claude prompt."""
    lines = []
    for key, desc in _KEY_SCHEMA.items():
        lines.append(f'{key}: {desc}')
    return {'keys': _KEY_SCHEMA, 'prompt_additions': '\n\n'.join(lines)}, 200

@app.route('/generate', methods=['POST'])
def generate():
    data=request.get_json(force=True)
    buf=build_report(data)
    dn = data.get('_download_name','report.pdf')
    return send_file(buf,mimetype='application/pdf',as_attachment=True,download_name=dn)

@app.route('/healthz')
def health():
    return {'status':'ok'}

if __name__=='__main__':
    app.run(host='0.0.0.0',port=8000)

import requests as req
import stripe

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    try:
        event = stripe.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception:
        return {'error': 'invalid'}, 400

    if event['type'] == 'customer.subscription.created':
        handle_subscription(event['data']['object'], 'active')
    elif event['type'] == 'customer.subscription.deleted':
        handle_subscription(event['data']['object'], 'inactive')
    elif event['type'] == 'invoice.payment_failed':
        handle_subscription(event['data']['object'].get('subscription'), 'payment_failed')

    return {'status': 'ok'}, 200

def handle_subscription(subscription, status):
    try:
        customer_id = subscription.get('customer') if isinstance(subscription, dict) else subscription
        customer = stripe.Customer.retrieve(customer_id)
        email = customer.get('email')
        price_id = None
        if isinstance(subscription, dict):
            items = subscription.get('items', {}).get('data', [])
            if items:
                price_id = items[0].get('price', {}).get('id')

        _wl_price_ids = {
            os.environ.get('STRIPE_WHITE_LABEL_PRICE_ID'),
            os.environ.get('STRIPE_WL_6MONTH_PRICE_ID'),
            os.environ.get('STRIPE_WL_ANNUAL_PRICE_ID'),
        }
        _std_price_ids = {
            os.environ.get('STRIPE_STD_MONTHLY_PRICE_ID'),
            os.environ.get('STRIPE_STD_6MONTH_PRICE_ID'),
            os.environ.get('STRIPE_STD_ANNUAL_PRICE_ID'),
        }
        if price_id and price_id in _wl_price_ids:
            plan = 'white_label'
        elif price_id and price_id in _std_price_ids:
            plan = 'standard'
        else:
            plan = 'standard'

        active = status == 'active'

        supabase_url = os.environ.get('SUPABASE_URL')
        service_key = os.environ.get('SUPABASE_SERVICE_KEY')

        req.patch(
            f"{supabase_url}/rest/v1/firms?email=eq.{email}",
            headers={
                'apikey': service_key,
                'Authorization': f'Bearer {service_key}',
                'Content-Type': 'application/json',
            },
            json={'active': active, 'plan': plan},
        )
    except Exception as e:
        print(f"handle_subscription error: {e}")

@app.route('/ai-chat', methods=['POST', 'OPTIONS'])
def ai_chat():
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        return response
    data = request.get_json(force=True)
    response = req.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'x-api-key': os.environ.get('ANTHROPIC_API_KEY'),
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        },
        json=data,
        timeout=30,
    )
    return response.json(), response.status_code
