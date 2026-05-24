from flask import Flask, request, send_file
import io, json
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.pdfgen import canvas as rl_canvas

try:
    from reportlab.graphics.charts.piecharts import Pie as RLPie
    HAS_PIE = True
except ImportError:
    HAS_PIE = False

app = Flask(__name__)

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
    base = dict(fontName='Helvetica', fontSize=9, textColor=DARK, leading=14, spaceAfter=0, spaceBefore=0)
    base.update(kw)
    return ParagraphStyle(name, **base)

ST_SECTION = s('sec', fontName='Helvetica-Bold', fontSize=8, textColor=TEAL, leading=11)
ST_BODY    = s('body', fontSize=9, textColor=colors.HexColor('#374151'), leading=15)
ST_SMALL   = s('sm', fontSize=7.5, textColor=GRAY, leading=11)
ST_TH      = s('th', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE, alignment=TA_RIGHT, leading=11)
ST_TH_L    = s('thl', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE, leading=11)
ST_TD      = s('td', fontSize=8, textColor=DARK, alignment=TA_RIGHT, leading=11)
ST_TD_L    = s('tdl', fontSize=8, textColor=DARK, leading=11)
ST_BOLD    = s('bold', fontName='Helvetica-Bold', fontSize=8, textColor=NAVY, leading=11)
ST_BOLD_R  = s('boldr', fontName='Helvetica-Bold', fontSize=8, textColor=NAVY, alignment=TA_RIGHT, leading=11)
ST_FOOTER  = s('foot', fontSize=7, textColor=GRAY, alignment=TA_CENTER, leading=10)
ST_KPI_V   = s('kpiv', fontName='Helvetica-Bold', fontSize=17, textColor=NAVY, leading=21, alignment=TA_CENTER)
ST_KPI_L   = s('kpil', fontSize=7, textColor=GRAY, leading=9, alignment=TA_CENTER)
ST_FLAG_B  = s('flagb', fontSize=8, textColor=colors.HexColor('#374151'), leading=12)

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

def bar_chart(labels, values, w=100, h=44, show_trend=False):
    vals = [clean(v) or 0 for v in values]
    maxv = max(vals + [1]) * 1.15
    dw = Drawing(w*mm, h*mm)
    n = max(len(vals), 1)
    avail = (w - 20) * mm
    bw = min(14*mm, avail / (n*1.8))
    gap = (avail - bw*n) / max(n, 1)
    base_y = 8*mm; chart_h = (h-12)*mm
    palette = [TEAL, colors.HexColor('#0B6E60'), colors.HexColor('#084F45'),
               colors.HexColor('#0A8A78'), colors.HexColor('#063D35'), colors.HexColor('#0D9E89')]
    for i,(v,l) in enumerate(zip(vals, labels)):
        c = palette[i % len(palette)]
        x = 10*mm + i*(bw+gap)
        bh = (v/maxv)*chart_h if maxv > 0 else 1
        dw.add(Rect(x, base_y, bw, max(bh,1), fillColor=c, strokeColor=None))
        dw.add(String(x+bw/2, base_y-7*mm, str(l)[:6], fontSize=6.5, fillColor=GRAY, textAnchor='middle'))
        lab = f'£{v/1000:.0f}k' if v >= 1000 else f'£{v:.0f}'
        dw.add(String(x+bw/2, base_y+max(bh,1)+1.5*mm, lab, fontSize=6.5, fillColor=NAVY, textAnchor='middle', fontName='Helvetica-Bold'))
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
    dw.add(String((w-2)*mm,0.5*mm,f'{v:.1%}',fontSize=6.5,fillColor=color,textAnchor='end',fontName='Helvetica-Bold'))
    return dw

def kpi_card(value, label, sub):
    sub_s = s('cs', fontName='Helvetica-Bold', fontSize=7.5, textColor=TEAL, leading=10, alignment=TA_CENTER)
    data=[[Paragraph(str(value),ST_KPI_V)],[Paragraph(str(label),ST_KPI_L)],[Paragraph(str(sub),sub_s)]]
    t=Table(data,colWidths=[38*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),WHITE),('BOX',(0,0),(-1,-1),0.75,BORDER),
        ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
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
        'POSITIVE': (GREEN_TEXT, GREEN_SOFT,  '✓', 'Positive'),
        'WATCH':    (AMBER_TEXT, AMBER_SOFT,  '!', 'Watch'),
        'RISK':     (RED_TEXT,   RED_SOFT,    '✕', 'Risk'),
        'INFO':     (TEAL,       TEAL_LITE,   'i', 'Info'),
    }
    tc,bg,icon,label = color_map.get(severity.upper(), (AMBER_TEXT,AMBER_SOFT,'!','Watch'))
    icon_s = s('ico',fontName='Helvetica-Bold',fontSize=10,textColor=tc,alignment=TA_CENTER,leading=12)
    sev_s  = s('sev',fontName='Helvetica-Bold',fontSize=7, textColor=tc,alignment=TA_CENTER,leading=9)
    head_s = s('fh', fontName='Helvetica-Bold',fontSize=8, textColor=DARK,leading=12)
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
        [Paragraph(str(lbl),s('el',fontName='Helvetica-Bold',fontSize=8,textColor=NAVY,leading=11))],
        [Paragraph(fmt(val),s('ev',fontName='Helvetica-Bold',fontSize=13,textColor=NAVY,leading=17))],
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
    growth_s = s('ckg', fontName='Helvetica-Bold', fontSize=7.5, textColor=gc, leading=10, alignment=TA_CENTER)
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
            pie.slices[i].fontName = 'Helvetica-Bold'
        dw.add(pie)
        dw.add(String(w/2*mm, 4*mm, 'Expense Mix',
                     fontSize=7, fillColor=GRAY, textAnchor='middle', fontName='Helvetica-Bold'))
        return dw
    except Exception:
        return None

# ── Waterfall chart — stacked bars ───────────────────────────────────────────

def waterfall_chart(total_revenue, total_cogs, total_opex, net_profit, w=175, h=90):
    try:
        rev  = clean(total_revenue)
        if not rev or rev <= 0: return None
        cogs  = clean(total_cogs) or 0
        opex  = clean(total_opex) or 0
        np_v  = clean(net_profit)
        gross = rev - cogs
        net   = np_v if np_v is not None else (gross - opex)

        AMBER     = colors.HexColor('#D97706')
        COGS_FADE = colors.HexColor('#6B2D2D')

        dw      = Drawing(w*mm, h*mm)
        base_y  = 18*mm
        chart_h = (h - 28)*mm   # 62mm of bar space

        def ht(val): return (max(val, 0) / rev) * chart_h if rev > 0 else 0

        avail = (w - 20)*mm
        bw    = min(36*mm, avail / 4)
        gap   = (avail - bw * 3) / 2
        def bx(i): return 10*mm + i*(bw + gap)

        def label_in(x, y_bot, bar_h, text, color=WHITE):
            """Label centred horizontally and vertically in a bar segment."""
            if bar_h > 7*mm:
                dw.add(String(x + bw/2, y_bot + bar_h/2 - 1*mm, text,
                              fontSize=6.5, fillColor=color,
                              textAnchor='middle', fontName='Helvetica-Bold'))

        def axis_label(x, text):
            dw.add(String(x + bw/2, base_y - 9*mm, text,
                          fontSize=6, fillColor=GRAY, textAnchor='middle'))

        full_h = ht(rev)
        gp_h   = ht(gross)
        cogs_h = ht(cogs)
        net_h  = ht(max(net, 0))
        opex_h = ht(opex)
        pad_h  = full_h - net_h - opex_h  # faded COGS top to equalise bar heights

        # Bar 1: Revenue
        dw.add(Rect(bx(0), base_y, bw, full_h, fillColor=TEAL, strokeColor=None))
        label_in(bx(0), base_y, full_h, f'Revenue £{rev/1000:.0f}k')
        axis_label(bx(0), 'Revenue')

        # Bar 2: GP (teal) + COGS (red) — same total height as bar 1
        dw.add(Rect(bx(1), base_y,       bw, gp_h,   fillColor=TEAL,     strokeColor=None))
        dw.add(Rect(bx(1), base_y+gp_h,  bw, cogs_h, fillColor=RED_TEXT,  strokeColor=None))
        label_in(bx(1), base_y,      gp_h,   f'GP £{gross/1000:.0f}k')
        label_in(bx(1), base_y+gp_h, cogs_h, f'COGS £{cogs/1000:.0f}k')
        axis_label(bx(1), 'Cost Breakdown')

        # Bar 3: NP (navy) + OpEx (amber) + faded COGS pad — same total height
        dw.add(Rect(bx(2), base_y,               bw, net_h,  fillColor=NAVY,      strokeColor=None))
        dw.add(Rect(bx(2), base_y+net_h,         bw, opex_h, fillColor=AMBER,     strokeColor=None))
        if pad_h > 0:
            dw.add(Rect(bx(2), base_y+net_h+opex_h, bw, pad_h, fillColor=COGS_FADE, strokeColor=None))
        label_in(bx(2), base_y,               net_h,  f'NP £{net/1000:.0f}k')
        label_in(bx(2), base_y+net_h,         opex_h, f'OpEx £{opex/1000:.0f}k')
        if pad_h > 7*mm:
            label_in(bx(2), base_y+net_h+opex_h, pad_h, f'COGS £{cogs/1000:.0f}k')
        axis_label(bx(2), 'Profit Breakdown')

        # Baseline
        dw.add(Line(8*mm, base_y, (w-5)*mm, base_y, strokeColor=BORDER, strokeWidth=0.5))

        # Legend — 2 rows × 2 cols, horizontally centred, clear of axis labels
        legend_items = [
            (TEAL,      'Gross Profit'),
            (RED_TEXT,  'COGS'),
            (AMBER,     'Operating Expenses'),
            (NAVY,      'Net Profit'),
        ]
        col_w   = 52*mm
        start_x = (w*mm - col_w * 2) / 2
        for i, (col, lbl) in enumerate(legend_items):
            row   = i // 2          # 0 = top row, 1 = bottom row
            col_i = i % 2
            lx    = start_x + col_i * col_w
            ly    = 5*mm - row * 4*mm   # top row at 5mm, bottom row at 1mm
            dw.add(Rect(lx, ly, 6, 6, fillColor=col, strokeColor=None))
            dw.add(String(lx + 9, ly + 0.5, lbl, fontSize=6, fillColor=GRAY, textAnchor='start'))

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
            [Paragraph('Corporation Tax Estimate (UK)', s('txh', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE, leading=12)),
             Paragraph('', ST_TD), Paragraph('', ST_TD)],
            [Paragraph('Net Profit', ST_TD_L),
             Paragraph(fmt(np_val), ST_TD), Paragraph('', ST_TD)],
            [Paragraph(f'Estimated Tax ({rate_note})', ST_TD_L),
             Paragraph(f'({fmt(tax_est)})', s('txr', fontSize=8, textColor=RED_TEXT, alignment=TA_RIGHT, leading=11)),
             Paragraph('', ST_TD)],
            [Paragraph('Estimated Profit After Tax', s('txb', fontName='Helvetica-Bold', fontSize=9, textColor=NAVY, leading=13)),
             Paragraph(fmt(after_tax), s('txbr', fontName='Helvetica-Bold', fontSize=9, textColor=NAVY, alignment=TA_RIGHT, leading=13)),
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
        bname = str(d.get('business_name', 'Client Business'))
        period = str(d.get('period', ''))

        # Firm name / logo
        try:
            if is_wl and wl_logo and wl_logo.upper() not in ('NA','N/A','','NONE'):
                import urllib.request, tempfile
                from reportlab.platypus import Image as RLImage
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                urllib.request.urlretrieve(wl_logo, tmp.name)
                firm_c = RLImage(tmp.name, width=55*mm, height=12*mm, kind='proportional')
            elif is_wl:
                firm_c = Paragraph(prepared_by, s('cvf', fontName='Helvetica-Bold', fontSize=18, textColor=WHITE, leading=24))
            else:
                firm_c = Paragraph('FinReportAI', s('cvf', fontName='Helvetica-Bold', fontSize=18, textColor=GOLD, leading=24))
        except:
            firm_c = Paragraph(prepared_by, s('cvf2', fontName='Helvetica-Bold', fontSize=18, textColor=WHITE, leading=24))

        has_tag = is_wl and wl_tagline and wl_tagline.upper() not in ('NA','N/A','NONE','')
        tag_c = Paragraph(wl_tagline, s('cvtg', fontSize=9, textColor=colors.HexColor('#9BB5D4'), leading=13)) \
                if has_tag else Spacer(1, 1)

        conf_pill = Table([[Paragraph('CONFIDENTIAL',
            s('cvcf', fontName='Helvetica-Bold', fontSize=8, textColor=NAVY, leading=10, alignment=TA_CENTER))]],
            colWidths=[32*mm])
        conf_pill.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,-1),GOLD),
            ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
            ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
        ]))

        # Divider line
        rule = Table([['']], colWidths=[143*mm], rowHeights=[1])
        rule.setStyle(TableStyle([
            ('LINEABOVE',(0,0),(-1,0),0.5,colors.HexColor('#2D4A6B')),
            ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),
            ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
        ]))

        ref_para = Paragraph(
            f'Ref: {report_ref}   ·   Prepared by {prepared_by}   ·   Confidential',
            s('cvmeta', fontSize=7.5, textColor=colors.HexColor('#6B7280'), leading=11))

        # Rows + explicit heights summing to 280mm
        # (A4 frame = 297 - 0 topMargin - 12 bottomMargin = 285mm; leave 5mm buffer)
        rows = [
            [Spacer(1,1)],       # 0  top space        28mm
            [firm_c],            # 1  firm name         14mm
            [tag_c],             # 2  tagline           10mm
            [Spacer(1,1)],       # 3  gap               36mm
            [Paragraph(bname, s('cvbiz', fontName='Helvetica-Bold', fontSize=26, textColor=WHITE, leading=34))],  # 4  biz name 22mm
            [Spacer(1,1)],       # 5  small gap          4mm
            [Paragraph('Financial Report', s('cvtype', fontSize=12, textColor=colors.HexColor('#9BB5D4'), leading=17))],  # 6 10mm
            [Paragraph(period, s('cvper', fontSize=10, textColor=colors.HexColor('#9BB5D4'), leading=14))],  # 7 9mm
            [Paragraph('GBP (£)', s('cvgbp', fontSize=8.5, textColor=colors.HexColor('#5B7A9A'), leading=12))],  # 8 8mm
            [Spacer(1,1)],       # 9  pre-rule gap       8mm
            [rule],              # 10 divider             3mm
            [Spacer(1,1)],       # 11 post-rule          14mm
            [conf_pill],         # 12 conf badge         14mm
            [Spacer(1,1)],       # 13 stretch            84mm
            [ref_para],          # 14 ref line           10mm
            [Spacer(1,1)],       # 15 bottom buffer       6mm
        ]
        # Sum: 28+14+10+36+22+4+10+9+8+8+3+14+14+84+10+6 = 280mm
        heights = [
            28*mm, 14*mm, 10*mm, 36*mm,
            22*mm,  4*mm, 10*mm,  9*mm,
             8*mm,  8*mm,  3*mm, 14*mm,
            14*mm, 84*mm, 10*mm,  6*mm,
        ]

        cover_t = Table(rows, colWidths=[175*mm], rowHeights=heights)
        cover_t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), C_PRIMARY),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('LEFTPADDING', (0,0), (-1,-1), 14*mm),
            ('RIGHTPADDING', (0,0), (-1,-1), 8*mm),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        return [cover_t, PageBreak()]
    except Exception:
        return []

# ── Table of contents ─────────────────────────────────────────────────────────

def toc_elements(sections, C_ACCENT):
    try:
        items = [
            Paragraph('Contents', s('toch', fontName='Helvetica-Bold', fontSize=14, textColor=NAVY, leading=20)),
            Spacer(1, 8*mm),
        ]
        for i, sec in enumerate(sections, 1):
            row_t = Table([[
                Paragraph(str(i), s(f'tocn{i}', fontName='Helvetica-Bold', fontSize=9, textColor=C_ACCENT, leading=15)),
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

def glossary_section(C_ACCENT):
    try:
        terms = [
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
        rows = [[Paragraph('Term', ST_TH_L), Paragraph('Definition', ST_TH_L)]]
        for i, (term, defn) in enumerate(terms):
            rows.append([
                Paragraph(term, s(f'gt{i}', fontName='Helvetica-Bold', fontSize=8, textColor=NAVY, leading=13)),
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

# ── Dynamic P&L table ─────────────────────────────────────────────────────────

def pl_table(d, periods, periods_keys, revenue_items, cogs_items, opex_items):
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
        return [Paragraph(txt,s('cat',fontName='Helvetica-Bold',fontSize=7.5,textColor=TEAL,leading=11))] + ['']*(ncols+1)
    def blank():
        return [Paragraph(' ',s('sp',fontSize=2,leading=2))] + [' ']*(ncols+1)

    hdr = [th('', False)]
    for p in periods: hdr.append(th(str(p)[:6]))
    hdr.append(th('Total'))

    def item_row(item, bold=False, indent=True):
        vals = item.get('values', [])
        row = [label(item.get('label','—'), indent=indent, bold=bold)]
        for i in range(ncols):
            v = vals[i] if i < len(vals) else None
            if bold and not has_val(v):
                row.append(Paragraph('—', ST_BOLD_R if bold else ST_TD))
            else:
                row.append(money(v, bold))
        row.append(money(item.get('total'), bold or True))
        return row

    rows = [hdr]
    cat_rows = []
    teal_rows = []

    if revenue_items:
        rows.append(cat('REVENUE')); cat_rows.append(len(rows)-1)
        for it in revenue_items: rows.append(item_row(it))
        tr = {'label':'Total Revenue','values':[d.get('revenue_'+k) for k in periods_keys] if show_periods else [],'total':d.get('total_revenue')}
        rows.append(item_row(tr, bold=True, indent=False)); teal_rows.append(len(rows)-1)
        rows.append(blank())

    if cogs_items or has_val(d.get('total_cogs')):
        rows.append(cat('COST OF GOODS SOLD')); cat_rows.append(len(rows)-1)
        for it in cogs_items: rows.append(item_row(it))
        cogs_total = d.get('total_cogs')
        if not has_val(cogs_total) and cogs_items:
            ssum = sum(clean(it.get('total')) or 0 for it in cogs_items)
            cogs_total = ssum if ssum>0 else None
        rows.append(item_row({'label':'Total COGS','values':[],'total':cogs_total}, bold=True, indent=False))
        teal_rows.append(len(rows)-1)
        rows.append(blank())

    if has_val(d.get('gross_profit')):
        gp = {'label':'GROSS PROFIT','values':[d.get('gross_profit_'+k) for k in periods_keys] if show_periods else [],'total':d.get('gross_profit')}
        rows.append(item_row(gp, bold=True, indent=False)); teal_rows.append(len(rows)-1)
        if has_val(d.get('gross_margin')):
            rows.append([label('Gross Margin %', sub=True)] + [td('—')]*ncols + [td(fmtp(d.get('gross_margin')))])
        rows.append(blank())

    if opex_items or has_val(d.get('total_opex')):
        rows.append(cat('OPERATING EXPENSES')); cat_rows.append(len(rows)-1)
        for it in opex_items: rows.append(item_row(it))
        opex_total = d.get('total_opex')
        if not has_val(opex_total) and opex_items:
            ssum = sum(clean(it.get('total')) or 0 for it in opex_items)
            opex_total = ssum if ssum>0 else None
        rows.append(item_row({'label':'Total Operating Expenses','values':[],'total':opex_total}, bold=True, indent=False))
        teal_rows.append(len(rows)-1)
        rows.append(blank())

    np_row = {'label':'NET PROFIT','values':[d.get('net_profit_'+k) for k in periods_keys] if show_periods else [],'total':d.get('net_profit')}
    rows.append(item_row(np_row, bold=True, indent=False))
    net_row_idx = len(rows)-1
    if has_val(d.get('net_margin')):
        nm_vals = [fmtp(d.get('net_margin_'+k)) for k in periods_keys] if show_periods else []
        rows.append([label('Net Margin %', sub=True)] + [td(x) for x in nm_vals] + [td(fmtp(d.get('net_margin')))])

    colw = [60*mm] + [(115*mm)/(ncols+1)]*(ncols+1)
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
    ]
    for ci in cat_rows: style.append(('SPAN',(0,ci),(-1,ci)))
    for ti in teal_rows: style.append(('BACKGROUND',(0,ti),(-1,ti),TEAL_LITE))
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
                st = s('chg',fontName='Helvetica-Bold' if bold else 'Helvetica',fontSize=7.5,textColor=col,alignment=TA_RIGHT,leading=11)
                return Paragraph(txt,st)
        except: pass
        return Paragraph('—',ST_TD)
    def label(txt, indent=False, bold=False, sub=False):
        p='    ' if indent else ''
        st=ST_BOLD if bold else (s('sub',fontSize=7.5,textColor=GRAY,leading=11) if sub else ST_TD_L)
        return Paragraph(p+txt,st)
    def cat(txt):
        ncols_total = len(periods)+3
        return [Paragraph(txt,s('cat',fontName='Helvetica-Bold',fontSize=7.5,textColor=C_ACCENT,leading=11))] + ['']*(ncols_total-1)
    def blank():
        ncols_total = len(periods)+3
        return [Paragraph(' ',s('sp',fontSize=2,leading=2))] + [' ']*(ncols_total-1)

    ncols = len(periods)
    prev_period_label = str(d.get('previous_period','Prev'))[:8]

    def get_prev_total(items_list, label_text):
        for it in items_list:
            if it.get('label','').lower() == label_text.lower():
                return it.get('total')
        return None

    hdr = [th('',False)]
    for p in periods: hdr.append(th(p[:3]))
    hdr += [th('Current'), th(prev_period_label), th('Chg %')]

    def item_row(item, prev_items, bold=False, indent=True):
        vals = item.get('values',[])
        row = [label(item.get('label','—'),indent=indent,bold=bold)]
        for i in range(ncols):
            v = vals[i] if i<len(vals) else None
            if bold and not has_val(v):
                row.append(Paragraph('—',ST_BOLD_R if bold else ST_TD))
            else:
                row.append(money(v,bold))
        curr_total = item.get('total')
        prev_total = get_prev_total(prev_items, item.get('label',''))
        row.append(money(curr_total,bold))
        row.append(money(prev_total,bold))
        row.append(pct_change(curr_total,prev_total,bold))
        return row

    rows = [hdr]
    teal_rows=[]

    if revenue_items:
        rows.append(cat('REVENUE'))
        for it in revenue_items: rows.append(item_row(it,prev_revenue_items))
        tr_curr=d.get('total_revenue'); tr_prev=d.get('prev_total_revenue')
        tr_row=[label('Total Revenue',bold=True)]
        for k in periods_keys: tr_row.append(money(d.get('revenue_'+k),True))
        tr_row+=[money(tr_curr,True),money(tr_prev,True),pct_change(tr_curr,tr_prev,True)]
        rows.append(tr_row); teal_rows.append(len(rows)-1)
        rows.append(blank())

    if cogs_items or has_val(d.get('total_cogs')):
        rows.append(cat('COST OF GOODS SOLD'))
        for it in cogs_items: rows.append(item_row(it,prev_cogs_items))
        tc_curr=d.get('total_cogs'); tc_prev=d.get('prev_total_cogs')
        rows.append([label('Total COGS',bold=True)]+['—']*ncols+[money(tc_curr,True),money(tc_prev,True),pct_change(tc_curr,tc_prev,True)])
        teal_rows.append(len(rows)-1)
        rows.append(blank())

    if has_val(d.get('gross_profit')):
        gp_curr=d.get('gross_profit'); gp_prev=d.get('prev_gross_profit')
        rows.append([label('GROSS PROFIT',bold=True)]+[money(d.get('gross_profit_'+k),True) for k in periods_keys]+[money(gp_curr,True),money(gp_prev,True),pct_change(gp_curr,gp_prev,True)])
        teal_rows.append(len(rows)-1)
        if has_val(d.get('gross_margin')):
            rows.append([label('Gross Margin %',sub=True)]+['—']*ncols+[td(fmtp(d.get('gross_margin'))),td(fmtp(d.get('prev_gross_margin'))),td('—')])
        rows.append(blank())

    if opex_items or has_val(d.get('total_opex')):
        rows.append(cat('OPERATING EXPENSES'))
        for it in opex_items: rows.append(item_row(it,prev_opex_items))
        to_curr=d.get('total_opex'); to_prev=d.get('prev_total_opex')
        rows.append([label('Total OpEx',bold=True)]+['—']*ncols+[money(to_curr,True),money(to_prev,True),pct_change(to_curr,to_prev,True)])
        teal_rows.append(len(rows)-1)
        rows.append(blank())

    np_curr=d.get('net_profit'); np_prev=d.get('prev_net_profit')
    np_row=[label('NET PROFIT',bold=True)]
    for k in periods_keys: np_row.append(money(d.get('net_profit_'+k),True))
    np_row+=[money(np_curr,True),money(np_prev,True),pct_change(np_curr,np_prev,True)]
    rows.append(np_row)
    net_idx=len(rows)-1
    if has_val(d.get('net_margin')):
        rows.append([label('Net Margin %',sub=True)]+[td(fmtp(d.get('net_margin_'+k))) for k in periods_keys]+[td(fmtp(d.get('net_margin'))),td(fmtp(d.get('prev_net_margin'))),td('—')])

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
    ]
    for ti in teal_rows: style_cmds.append(('BACKGROUND',(0,ti),(-1,ti),TEAL_LITE))
    t.setStyle(TableStyle(style_cmds))
    return t

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

    doc=SimpleDocTemplate(buf,pagesize=A4,leftMargin=17*mm,rightMargin=17*mm,topMargin=0,bottomMargin=12*mm)

    periods_raw = d.get('periods','')
    if isinstance(periods_raw, list):
        periods_full = [str(p) for p in periods_raw if str(p).strip()]
    else:
        periods_full = [p.strip() for p in str(periods_raw).split(',') if p.strip()]
    periods_full = periods_full[:6]
    periods = [p[:3] for p in periods_full]
    periods_keys = [p.lower().replace(' ','') for p in periods_full]

    revenue_items = get_list(d, 'revenue_items')
    cogs_items    = get_list(d, 'cogs_items')
    opex_items    = get_list(d, 'opex_items')
    prev_revenue_items = get_list(d, 'prev_revenue_items')
    prev_cogs_items    = get_list(d, 'prev_cogs_items')
    prev_opex_items    = get_list(d, 'prev_opex_items')
    is_comparison = has_val(d.get('prev_total_revenue')) and str(d.get('prev_total_revenue','')).upper() not in ('NA','N/A','NONE','')

    period_rev = [d.get('revenue_'+k) for k in periods_keys]
    opex_with_totals = [it for it in opex_items if has_val(it.get('total'))]
    total_r = clean(d.get('total_revenue'))

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
    if has_val(d.get('net_profit')) and (clean(d.get('net_profit')) or 0) > 0:
        toc_sections.append('Corporation Tax Estimate')
    if d.get('analysis'):
        toc_sections.append('Key Trends & Analysis')
    raw_flags = str(d.get('flags',''))
    flag_lines = [f.strip() for f in raw_flags.replace('FLAGSEP','\n').split('\n') if '|' in f and len(f.strip())>3]
    if flag_lines:
        toc_sections.append('Flags & Items to Watch')
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

    # ── Slim page header (replaces the old full-width navy banner) ────────────
    slim_hdr = Table([[
        Paragraph(str(d.get('business_name', '')),
            s('sh', fontName='Helvetica-Bold', fontSize=9, textColor=WHITE, leading=13)),
        Paragraph(f"{d.get('period', '')}  ·  {prepared_by}",
            s('shr', fontSize=8, textColor=colors.HexColor('#9BB5D4'), leading=11, alignment=TA_RIGHT)),
    ]], colWidths=[90*mm, 85*mm])
    slim_hdr.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),C_PRIMARY),
        ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
        ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
    ]))
    story.append(slim_hdr)
    story.append(Spacer(1,5*mm))

    # ── Executive Summary ─────────────────────────────────────────────────────
    intro_parts = [section_header('Executive Summary', C_ACCENT), Spacer(1,3*mm)]
    if is_wl:
        intro_text = f"This report has been prepared by {wl_name} for {d.get('business_name','the client')} covering the period {str(d.get('period','')).split('—')[0].strip()}. It is intended for internal management use only."
        intro_parts += [Paragraph(intro_text, s('intro',fontSize=8.5,textColor=colors.HexColor('#6B7280'),leading=13,fontName='Helvetica')),Spacer(1,3*mm)]
    intro_parts += [Paragraph(str(d.get('executive_summary','No summary provided.')),ST_BODY),Spacer(1,4*mm)]
    story.append(KeepTogether(intro_parts))

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
    kpi_row=Table([kpis],colWidths=[38*mm]*4)
    kpi_row.setStyle(TableStyle([
        ('LEFTPADDING',(0,0),(-1,-1),2),('RIGHTPADDING',(0,0),(-1,-1),2),
        ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),
    ]))
    story.append(KeepTogether([kpi_row,Spacer(1,5*mm)]))

    # ── Revenue Performance & Margins ─────────────────────────────────────────
    if periods and any(has_val(v) for v in period_rev):
        chart = bar_chart(periods, period_rev, show_trend=True)
        margin_rows=[
            [Paragraph('Margin Analysis',s('ma',fontName='Helvetica-Bold',fontSize=8,textColor=NAVY,leading=12))],
            [Spacer(1,2*mm)],
        ]
        if has_val(d.get('gross_margin')):
            margin_rows += [[Paragraph('Gross Margin',ST_SMALL)],[margin_bar(d.get('gross_margin'),'Average',TEAL)],[Spacer(1,1*mm)]]
        nm_period = [(p, d.get('net_margin_'+k)) for p,k in zip(periods,periods_keys) if has_val(d.get('net_margin_'+k))]
        if nm_period:
            margin_rows += [[Paragraph('Net Margin by Period',ST_SMALL)]]
            palette=[RED_TEXT,GOLD,GREEN_TEXT,TEAL,colors.HexColor('#0B6E60'),NAVY]
            for i,(p,v) in enumerate(nm_period):
                margin_rows += [[margin_bar(v, p, palette[i%len(palette)])],[Spacer(1,1*mm)]]
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
        story.append(KeepTogether([
            section_header('Revenue Performance & Margins', C_ACCENT),
            Spacer(1,3*mm), combined, Spacer(1,5*mm),
        ]))

    # ── Expense Breakdown + Pie chart ─────────────────────────────────────────
    if opex_with_totals:
        cards=[]
        for it in opex_with_totals[:5]:
            tv = clean(it.get('total'))
            pct = (tv/total_r*100) if (total_r and total_r>0) else None
            cards.append(exp_card(it.get('label','')[:16], tv, pct))
        exp_row=Table([cards],colWidths=[33*mm]*len(cards))
        exp_row.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),2),('RIGHTPADDING',(0,0),(-1,-1),2),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))

        exp_section = [
            section_header('Operating Expense Breakdown', C_ACCENT),
            Spacer(1,3*mm),
        ]

        # Pie chart centred below expense cards
        try:
            if HAS_PIE and len(opex_with_totals) >= 2:
                pie = expense_pie_chart(
                    [it.get('label','') for it in opex_with_totals],
                    [it.get('total') for it in opex_with_totals],
                )
                if pie:
                    side_pad = (175*mm - 80*mm) / 2
                    pie_row = Table([[Spacer(1,1), pie, Spacer(1,1)]],
                                    colWidths=[side_pad, 80*mm, side_pad])
                    pie_row.setStyle(TableStyle([
                        ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),
                        ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
                        ('VALIGN',(0,0),(-1,-1),'TOP'),
                    ]))
                    exp_section += [exp_row, Spacer(1, 6*mm), pie_row, Spacer(1, 5*mm)]
                else:
                    exp_section += [exp_row, Spacer(1, 5*mm)]
            else:
                exp_section += [exp_row, Spacer(1, 5*mm)]
        except Exception:
            exp_section += [exp_row, Spacer(1, 5*mm)]

        story.append(KeepTogether(exp_section))

    # ── P&L Table ─────────────────────────────────────────────────────────────
    if revenue_items or cogs_items or opex_items or has_val(d.get('total_revenue')):
        story.append(KeepTogether([section_header('Full Profit & Loss Statement', C_ACCENT),Spacer(1,3*mm)]))
        if is_comparison:
            story.append(comparison_pl_table(d, periods, periods_keys, revenue_items, cogs_items, opex_items, prev_revenue_items, prev_cogs_items, prev_opex_items, C_ACCENT))
        else:
            story.append(pl_table(d, periods, periods_keys, revenue_items, cogs_items, opex_items))
        story.append(Spacer(1,5*mm))

        # Waterfall
        try:
            wf = waterfall_chart(d.get('total_revenue'), d.get('total_cogs'), d.get('total_opex'), d.get('net_profit'))
            if wf:
                story.append(KeepTogether([
                    section_header('P&L Waterfall', C_ACCENT),
                    Spacer(1,3*mm), wf, Spacer(1,5*mm),
                ]))
        except Exception:
            pass

        # ── Corporation Tax Estimate (after P&L) ─────────────────────────────
        try:
            tax_t = tax_estimate_section(d.get('net_profit'), C_ACCENT)
            if tax_t:
                story.append(KeepTogether([
                    section_header('Corporation Tax Estimate', C_ACCENT),
                    Spacer(1,3*mm), tax_t, Spacer(1,5*mm),
                ]))
        except Exception:
            pass

    # ── Key Trends ────────────────────────────────────────────────────────────
    if d.get('analysis'):
        story.append(KeepTogether([
            section_header('Key Trends & Analysis', C_ACCENT),Spacer(1,3*mm),
            Paragraph(str(d.get('analysis')),ST_BODY),
            Spacer(1,5*mm),
        ]))

    # ── Flags ─────────────────────────────────────────────────────────────────
    if flag_lines:
        story.append(KeepTogether([section_header('Flags & Items to Watch', C_ACCENT),Spacer(1,3*mm)]))
        for i,fl in enumerate(flag_lines):
            parts = fl.split('|')
            if len(parts) >= 3:
                severity=parts[0].strip(); title=parts[1].strip(); body=parts[2].strip()
            elif len(parts) == 2:
                severity='WATCH'; title='Flag'; body=parts[1].strip()
            else:
                severity='WATCH'; title='Flag'; body=fl.strip()
            story.append(KeepTogether([flag_card(i+1,title,body,severity),Spacer(1,2*mm)]))
        story.append(Spacer(1,4*mm))

    # ── Outlook ───────────────────────────────────────────────────────────────
    if d.get('outlook'):
        story.append(KeepTogether([
            section_header('Outlook', C_ACCENT),Spacer(1,3*mm),
            Paragraph(str(d.get('outlook')),ST_BODY),
            Spacer(1,4*mm),
        ]))

    # ── Glossary ──────────────────────────────────────────────────────────────
    try:
        gloss = glossary_section(C_ACCENT)
        if gloss:
            story.append(KeepTogether([
                section_header('Glossary of Financial Terms', C_ACCENT),
                Spacer(1,3*mm), gloss, Spacer(1,5*mm),
            ]))
    except Exception:
        pass

    # ── Footer ────────────────────────────────────────────────────────────────
    contact_str = f" &nbsp;·&nbsp; {wl_contact}" if wl_contact and wl_contact.upper() not in ('NA','N/A','NONE','') else ''
    disclaimer_row = []
    if wl_disclaimer and wl_disclaimer.upper() not in ('NA','N/A','NONE',''):
        disclaimer_row = [Paragraph(wl_disclaimer,s('disc',fontSize=7,textColor=colors.HexColor('#9CA3AF'),alignment=TA_CENTER,leading=10))]
    period_short = str(d.get('period','')).split('—')[0].strip()
    if is_wl and contact_str:
        line1 = f"Prepared by {prepared_by}{contact_str}"
        line2 = f"{period_short} &nbsp;·&nbsp; Ref: {report_ref} &nbsp;·&nbsp; Confidential"
        main_footer = [
            Paragraph(line1,s('ftxt',fontSize=6,textColor=colors.HexColor('#6B7280'),alignment=TA_CENTER,leading=9)),
            Paragraph(line2,s('ftxt2',fontSize=6,textColor=colors.HexColor('#6B7280'),alignment=TA_CENTER,leading=9)),
        ]
    else:
        main_footer = [Paragraph(f"Prepared by {prepared_by} &nbsp;·&nbsp; {period_short} &nbsp;·&nbsp; Ref: {report_ref} &nbsp;·&nbsp; Confidential",s('ftxt',fontSize=6,textColor=colors.HexColor('#6B7280'),alignment=TA_CENTER,leading=9))]
    ft_rows = []
    if disclaimer_row:
        for item in disclaimer_row: ft_rows.append([item])
    for item in main_footer: ft_rows.append([item])
    ft=Table(ft_rows,colWidths=[175*mm])
    ft.setStyle(TableStyle([('LINEABOVE',(0,0),(-1,0),0.5,BORDER),('TOPPADDING',(0,0),(-1,-1),5),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
    story.append(ft)

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
            self.setFont('Helvetica', 7)
            self.setFillColor(colors.HexColor('#6B7280'))
            self.drawCentredString(A4[0]/2, 5*mm, f'Page {self._pageNumber} of {page_count}')

    doc.build(story, canvasmaker=PageNumCanvas)
    buf.seek(0)
    return buf

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
