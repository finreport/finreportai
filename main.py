from flask import Flask, request, send_file
import io, json
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.pdfgen import canvas

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
    """Extract a float from any messy value. Returns None if not a number."""
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
    """Return a list of {label, value, ...} dicts from data, tolerating various shapes."""
    raw = d.get(key)
    if raw is None: return []
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw or raw.upper() in ('NA','N/A','NONE','NULL'): return []
        try: raw = json.loads(raw)
        except: return []
    if isinstance(raw, dict): raw = [raw]
    if not isinstance(raw, list): return []
    out = []
    for item in raw:
        if isinstance(item, dict):
            out.append(item)
    return out

# ── Chart helpers ───────────────────────────────────────────────────────────
def bar_chart(labels, values, w=100, h=44):
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
        dw.add(String(x+bw/2, base_y+bh+1.5*mm, lab, fontSize=6.5, fillColor=NAVY, textAnchor='middle', fontName='Helvetica-Bold'))
    dw.add(Line(8*mm, base_y, w*mm-5*mm, base_y, strokeColor=BORDER, strokeWidth=0.5))
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
    short_sub = str(sub).split('—')[0].strip() if '—' in str(sub) else str(sub)
    data=[[Paragraph(str(value),ST_KPI_V)],[Paragraph(str(label),ST_KPI_L)],[Paragraph(short_sub,sub_s)]]
    t=Table(data,colWidths=[38*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),WHITE),('BOX',(0,0),(-1,-1),0.75,BORDER),
        ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
        ('LEFTPADDING',(0,0),(-1,-1),2),('RIGHTPADDING',(0,0),(-1,-1),2),
    ]))
    return t

def section_header(title):
    data=[[Paragraph(title.upper(),ST_SECTION)]]
    t=Table(data,colWidths=[175*mm])
    t.setStyle(TableStyle([
        ('LINEBELOW',(0,0),(-1,-1),1,TEAL),
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

def exp_card(lbl, val, pct_rev, trend):
    trend = str(trend).lower().strip() if trend else 'stable'
    tc = RED_TEXT if trend=='up' else GREEN_TEXT if trend=='down' else GRAY
    ts = '▲' if trend=='up' else '▼' if trend=='down' else '●'
    data=[
        [Paragraph(str(lbl),s('el',fontName='Helvetica-Bold',fontSize=8,textColor=NAVY,leading=11))],
        [Paragraph(fmt(val),s('ev',fontName='Helvetica-Bold',fontSize=13,textColor=NAVY,leading=17))],
        [Paragraph(f'{pct_rev:.1f}% of revenue' if pct_rev is not None else '',s('ep',fontSize=7,textColor=GRAY,leading=10))],
        [Paragraph(f'{ts} {trend.title()}',s('et',fontName='Helvetica-Bold',fontSize=7.5,textColor=tc,leading=10))],
    ]
    t=Table(data,colWidths=[33*mm])
    t.setStyle(TableStyle([
        ('BOX',(0,0),(-1,-1),0.5,BORDER),
        ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
        ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),4),
        ('BACKGROUND',(0,0),(-1,-1),OFFWHITE),
    ]))
    return t

# ── Dynamic P&L table ─────────────────────────────────────────────────────────
def pl_table(d, periods, revenue_items, cogs_items, opex_items):
    """Build a P&L table dynamically. periods is a list like ['Feb','Mar','Apr'].
    Each *_items entry is a dict: {label, values:[...per period], total}."""
    ncols = len(periods)
    show_periods = ncols > 0

    def th(txt, right=True): return Paragraph(txt, ST_TH if right else ST_TH_L)
    def td(txt, right=True): return Paragraph(str(txt), ST_TD if right else ST_TD_L)
    def money(v, bold=False):
        return Paragraph(fmt(v), ST_BOLD_R if bold else ST_TD)
    def label(txt, indent=False, bold=False, sub=False):
        p='    ' if indent else ''
        st=ST_BOLD if bold else (s('sub',fontSize=7.5,textColor=GRAY,leading=11) if sub else ST_TD_L)
        return Paragraph(p+str(txt),st)
    def cat(txt):
        return [Paragraph(txt,s('cat',fontName='Helvetica-Bold',fontSize=7.5,textColor=TEAL,leading=11))] + ['']*(ncols+1)
    def blank():
        return [Paragraph(' ',s('sp',fontSize=2,leading=2))] + [' ']*(ncols+1)

    # header
    hdr = [th('', False)]
    for p in periods: hdr.append(th(str(p)[:6]))
    hdr.append(th('Total'))

    def item_row(item, bold=False, indent=True):
        vals = item.get('values', [])
        row = [label(item.get('label','—'), indent=indent, bold=bold)]
        for i in range(ncols):
            v = vals[i] if i < len(vals) else None
            row.append(money(v, bold))
        row.append(money(item.get('total'), bold or True))
        return row

    rows = [hdr]
    cat_rows = []  # track indices for styling
    teal_rows = []

    # REVENUE
    if revenue_items:
        rows.append(cat('REVENUE')); cat_rows.append(len(rows)-1)
        for it in revenue_items:
            rows.append(item_row(it))
        # total revenue
        tr = {'label':'Total Revenue','values':[d.get('revenue_'+p.lower()) for p in periods] if show_periods else [], 'total': d.get('total_revenue')}
        rows.append(item_row(tr, bold=True, indent=False)); teal_rows.append(len(rows)-1)
        rows.append(blank())

    # COGS
    if cogs_items or has_val(d.get('total_cogs')):
        rows.append(cat('COST OF GOODS SOLD')); cat_rows.append(len(rows)-1)
        for it in cogs_items:
            rows.append(item_row(it))
        cogs_total = d.get('total_cogs')
        if not has_val(cogs_total) and cogs_items:
            ssum = sum(clean(it.get('total')) or 0 for it in cogs_items)
            cogs_total = ssum if ssum>0 else None
        tc = {'label':'Total COGS','values':[],'total':cogs_total}
        rows.append(item_row(tc, bold=True, indent=False)); teal_rows.append(len(rows)-1)
        rows.append(blank())

    # GROSS PROFIT
    if has_val(d.get('gross_profit')):
        gp = {'label':'GROSS PROFIT','values':[d.get('gross_profit_'+p.lower()) for p in periods] if show_periods else [],'total':d.get('gross_profit')}
        rows.append(item_row(gp, bold=True, indent=False)); teal_rows.append(len(rows)-1)
        if has_val(d.get('gross_margin')):
            gm_row = [label('Gross Margin %', sub=True)] + [td('—')]*ncols + [td(fmtp(d.get('gross_margin')))]
            rows.append(gm_row)
        rows.append(blank())

    # OPERATING EXPENSES
    if opex_items or has_val(d.get('total_opex')):
        rows.append(cat('OPERATING EXPENSES')); cat_rows.append(len(rows)-1)
        for it in opex_items:
            rows.append(item_row(it))
        opex_total = d.get('total_opex')
        if not has_val(opex_total) and opex_items:
            ssum = sum(clean(it.get('total')) or 0 for it in opex_items)
            opex_total = ssum if ssum>0 else None
        to = {'label':'Total Operating Expenses','values':[],'total':opex_total}
        rows.append(item_row(to, bold=True, indent=False)); teal_rows.append(len(rows)-1)
        rows.append(blank())

    # NET PROFIT
    np_row = {'label':'NET PROFIT','values':[d.get('net_profit_'+p.lower()) for p in periods] if show_periods else [],'total':d.get('net_profit')}
    rows.append(item_row(np_row, bold=True, indent=False))
    net_row_idx = len(rows)-1
    if has_val(d.get('net_margin')):
        nm_vals = [fmtp(d.get('net_margin_'+p.lower())) for p in periods] if show_periods else []
        nm_row = [label('Net Margin %', sub=True)] + [td(x) for x in nm_vals] + [td(fmtp(d.get('net_margin')))]
        rows.append(nm_row)

    colw = [60*mm] + [ (115*mm)/(ncols+1) ]*(ncols+1)
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
    for ci in cat_rows:
        style.append(('SPAN',(0,ci),(-1,ci)))
    for ti in teal_rows:
        style.append(('BACKGROUND',(0,ti),(-1,ti),TEAL_LITE))
    t.setStyle(TableStyle(style))
    return t

def build_report(d):
    buf=io.BytesIO()
    doc=SimpleDocTemplate(buf,pagesize=A4,leftMargin=17*mm,rightMargin=17*mm,topMargin=0,bottomMargin=12*mm)
    story=[]

    # Periods (dynamic — Claude tells us which periods exist)
    periods_raw = d.get('periods','')
    if isinstance(periods_raw, list):
        periods = [str(p) for p in periods_raw if str(p).strip()]
    else:
        periods = [p.strip() for p in str(periods_raw).split(',') if p.strip()]
    periods = periods[:6]  # cap

    revenue_items = get_list(d, 'revenue_items')
    cogs_items    = get_list(d, 'cogs_items')
    opex_items    = get_list(d, 'opex_items')

    # HEADER
    conf_pill=Table([[Paragraph('CONFIDENTIAL',s('cf',fontName='Helvetica-Bold',fontSize=7,textColor=NAVY,leading=9,alignment=TA_CENTER))]],colWidths=[22*mm])
    conf_pill.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),GOLD),('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4)]))
    hdr_inner=Table([
        [Paragraph(str(d.get('business_name','Client Business')),s('ht',fontName='Helvetica-Bold',fontSize=22,textColor=WHITE,leading=28))],
        [Paragraph(f"{d.get('period','')} &nbsp;·&nbsp; GBP (£)",s('hs',fontSize=9.5,textColor=colors.HexColor('#9BB5D4'),leading=14))],
        [Spacer(1,3*mm)],[conf_pill],
    ],colWidths=[175*mm])
    hdr_inner.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
    hdr_outer=Table([[hdr_inner]],colWidths=[175*mm])
    hdr_outer.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),NAVY),('TOPPADDING',(0,0),(-1,-1),14),('BOTTOMPADDING',(0,0),(-1,-1),14),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
    story.append(hdr_outer)
    story.append(Spacer(1,5*mm))

    # EXECUTIVE SUMMARY
    story.append(KeepTogether([
        section_header('Executive Summary'),Spacer(1,3*mm),
        Paragraph(str(d.get('executive_summary','No summary provided.')),ST_BODY),
        Spacer(1,4*mm),
    ]))

    # KPI CARDS — only show ones with data
    kpi_defs = [
        (fmt(d.get('total_revenue')),'Total Revenue', d.get('period','')),
        (fmt(d.get('net_profit')),'Net Profit', d.get('period','')),
        (fmtp(d.get('gross_margin')),'Gross Margin','Average'),
        (fmtp(d.get('net_margin')),'Net Margin','Average'),
    ]
    kpis = [kpi_card(v,l,sub) for (v,l,sub) in kpi_defs]
    kpi_row=Table([kpis],colWidths=[38*mm]*4)
    kpi_row.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),2),('RIGHTPADDING',(0,0),(-1,-1),2),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
    story.append(KeepTogether([kpi_row,Spacer(1,5*mm)]))

    # REVENUE CHART + MARGINS — only if we have period revenue
    period_rev = [d.get('revenue_'+p.lower()) for p in periods]
    if periods and any(has_val(v) for v in period_rev):
        chart=bar_chart(periods, period_rev)
        margin_rows=[
            [Paragraph('Margin Analysis',s('ma',fontName='Helvetica-Bold',fontSize=8,textColor=NAVY,leading=12))],
            [Spacer(1,2*mm)],
        ]
        if has_val(d.get('gross_margin')):
            margin_rows += [[Paragraph('Gross Margin',ST_SMALL)],[margin_bar(d.get('gross_margin'),'Average',TEAL)],[Spacer(1,1*mm)]]
        # net margin by period
        nm_period = [(p, d.get('net_margin_'+p.lower())) for p in periods if has_val(d.get('net_margin_'+p.lower()))]
        if nm_period:
            margin_rows += [[Paragraph('Net Margin by Period',ST_SMALL)]]
            palette=[RED_TEXT,GOLD,GREEN_TEXT,TEAL,colors.HexColor('#0B6E60'),NAVY]
            for i,(p,v) in enumerate(nm_period):
                margin_rows += [[margin_bar(v, p, palette[i%len(palette)])],[Spacer(1,1*mm)]]
        # revenue mix from revenue_items totals
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
        story.append(KeepTogether([section_header('Revenue Performance & Margins'),Spacer(1,3*mm),combined,Spacer(1,5*mm)]))

    # EXPENSE BREAKDOWN CARDS — dynamic from opex_items
    total_r = clean(d.get('total_revenue'))
    opex_with_totals = [it for it in opex_items if has_val(it.get('total'))]
    if opex_with_totals:
        cards=[]
        for it in opex_with_totals[:5]:
            tv = clean(it.get('total'))
            pct = (tv/total_r*100) if (total_r and total_r>0) else None
            cards.append(exp_card(it.get('label','')[:16], tv, pct, it.get('trend','stable')))
        # pad to keep layout tidy
        exp_row=Table([cards],colWidths=[33*mm]*len(cards))
        exp_row.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),2),('RIGHTPADDING',(0,0),(-1,-1),2),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
        story.append(KeepTogether([section_header('Operating Expense Breakdown'),Spacer(1,3*mm),exp_row,Spacer(1,5*mm)]))

    # P&L TABLE
    if revenue_items or cogs_items or opex_items or has_val(d.get('total_revenue')):
        story.append(KeepTogether([section_header('Full Profit & Loss Statement'),Spacer(1,3*mm)]))
        story.append(pl_table(d, periods, revenue_items, cogs_items, opex_items))
        story.append(Spacer(1,5*mm))

    # KEY TRENDS
    if d.get('analysis'):
        story.append(KeepTogether([
            section_header('Key Trends & Analysis'),Spacer(1,3*mm),
            Paragraph(str(d.get('analysis')),ST_BODY),
            Spacer(1,5*mm),
        ]))

    # FLAGS
    raw_flags = str(d.get('flags',''))
    flag_lines = [f.strip() for f in raw_flags.replace('FLAGSEP','\n').split('\n') if '|' in f]
    if flag_lines:
        story.append(KeepTogether([section_header('Flags & Items to Watch'),Spacer(1,3*mm)]))
        for i,fl in enumerate(flag_lines):
            parts = fl.split('|')
            if len(parts) >= 3:
                severity = parts[0].strip()
                title    = parts[1].strip()
                body     = parts[2].strip()
            elif len(parts) == 2:
                severity = 'WATCH'
                title    = 'Flag'
                body     = parts[1].strip()
            else:
                severity = 'WATCH'
                title    = 'Flag'
                body     = fl.strip()
            story.append(KeepTogether([flag_card(i+1,title,body,severity),Spacer(1,2*mm)]))
        story.append(Spacer(1,4*mm))

    # OUTLOOK
    if d.get('outlook'):
        story.append(KeepTogether([
            section_header('Outlook'),Spacer(1,3*mm),
            Paragraph(str(d.get('outlook')),ST_BODY),
            Spacer(1,4*mm),
        ]))

    # FOOTER
    ft_data=[[Paragraph(f"Prepared by FinReportAI &nbsp;·&nbsp; {d.get('period','')} &nbsp;·&nbsp; All figures GBP (£) &nbsp;·&nbsp; Confidential",ST_FOOTER)]]
    ft=Table(ft_data,colWidths=[175*mm])
    ft.setStyle(TableStyle([('LINEABOVE',(0,0),(-1,0),0.5,BORDER),('TOPPADDING',(0,0),(-1,-1),5),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
    story.append(ft)

class PageNumCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []
    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()
    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)
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
    return send_file(buf,mimetype='application/pdf',as_attachment=True,download_name='report.pdf')

@app.route('/healthz')
def health():
    return {'status':'ok'}

if __name__=='__main__':
    app.run(host='0.0.0.0',port=8000)
