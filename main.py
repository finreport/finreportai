from flask import Flask, request, send_file
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect, String, Line

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
ST_FLAG_H  = s('flagh', fontName='Helvetica-Bold', fontSize=8, textColor=DARK, leading=12)
ST_FLAG_B  = s('flagb', fontSize=8, textColor=colors.HexColor('#374151'), leading=12)

def clean(n):
    try: return float(str(n).replace(',','').replace('£','').replace('%','').replace('$','').strip())
    except: return 0.0

def fmt(n):
    v = clean(n)
    return f'£{v:,.0f}' if v else str(n)

def fmtp(n):
    v = clean(n)
    if v > 1: v = v/100
    return f'{v:.1%}'

def bar_chart(labels, values, w=100, h=44):
    vals = [clean(v) for v in values]
    maxv = max(vals+[1])*1.15
    dw = Drawing(w*mm, h*mm)
    bw=12*mm; gap=8*mm; base_y=8*mm; chart_h=(h-12)*mm
    cols=[TEAL,colors.HexColor('#0B6E60'),colors.HexColor('#084F45')]
    for i,(v,c,l) in enumerate(zip(vals,cols,labels)):
        x=10*mm+i*(bw+gap); bh=(v/maxv)*chart_h if maxv>0 else 1
        dw.add(Rect(x,base_y,bw,max(bh,1),fillColor=c,strokeColor=None))
        dw.add(String(x+bw/2,base_y-7*mm,l,fontSize=6.5,fillColor=GRAY,textAnchor='middle'))
        dw.add(String(x+bw/2,base_y+bh+1.5*mm,f'£{v/1000:.0f}k',fontSize=6.5,fillColor=NAVY,textAnchor='middle',fontName='Helvetica-Bold'))
    dw.add(Line(8*mm,base_y,w*mm-5*mm,base_y,strokeColor=BORDER,strokeWidth=0.5))
    return dw

def margin_bar(pct_val, label, color, w=65, h=10):
    v = clean(pct_val)
    if v > 1: v = v/100
    dw=Drawing(w*mm,h*mm); track_w=(w-4)*mm; fill_w=track_w*min(v,1.0)
    dw.add(Rect(2*mm,3*mm,track_w,4*mm,fillColor=BORDER,strokeColor=None,rx=2,ry=2))
    dw.add(Rect(2*mm,3*mm,fill_w,4*mm,fillColor=color,strokeColor=None,rx=2,ry=2))
    dw.add(String(2*mm,0.5*mm,label,fontSize=6,fillColor=GRAY,textAnchor='start'))
    dw.add(String((w-2)*mm,0.5*mm,f'{v:.1%}',fontSize=6.5,fillColor=color,textAnchor='end',fontName='Helvetica-Bold'))
    return dw

def kpi_card(value, label, change, pos=True):
    chg_col=GREEN_TEXT if pos else RED_TEXT
    chg_s=s('cs',fontName='Helvetica-Bold',fontSize=7.5,textColor=chg_col,leading=10,alignment=TA_CENTER)
    data=[[Paragraph(str(value),ST_KPI_V)],[Paragraph(str(label),ST_KPI_L)],[Paragraph(str(change),chg_s)]]
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

def flag_card(num, body):
    data=[[[Paragraph('!',s('ico',fontName='Helvetica-Bold',fontSize=10,textColor=AMBER_TEXT,alignment=TA_CENTER,leading=12)),
             Paragraph('Watch',s('sev',fontName='Helvetica-Bold',fontSize=7,textColor=AMBER_TEXT,alignment=TA_CENTER,leading=9))],
            [Paragraph(f'{num}. Flag',ST_FLAG_H),Spacer(1,2),Paragraph(body,ST_FLAG_B)]]]
    t=Table(data,colWidths=[14*mm,161*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(0,0),AMBER_SOFT),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
        ('LEFTPADDING',(0,0),(0,0),3),('RIGHTPADDING',(0,0),(0,0),3),
        ('LEFTPADDING',(1,0),(1,0),8),('RIGHTPADDING',(1,0),(1,0),4),
        ('BOX',(0,0),(-1,-1),0.5,BORDER),
    ]))
    return t

def exp_card(lbl, q1, pct_rev, trend):
    tc = RED_TEXT if trend=='up' else GREEN_TEXT if trend=='down' else GRAY
    ts = '▲' if trend=='up' else '▼' if trend=='down' else '●'
    data=[
        [Paragraph(lbl,s('el',fontName='Helvetica-Bold',fontSize=8,textColor=NAVY,leading=11))],
        [Paragraph(fmt(q1),s('ev',fontName='Helvetica-Bold',fontSize=14,textColor=NAVY,leading=18))],
        [Paragraph(f'{pct_rev:.1f}% of revenue',s('ep',fontSize=7,textColor=GRAY,leading=10))],
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

def pl_table(d):
    def th(txt, right=True): return Paragraph(txt, ST_TH if right else ST_TH_L)
    def td(txt, right=True): return Paragraph(str(txt), ST_TD if right else ST_TD_L)
    def money(v, bold=False): return Paragraph(fmt(v), ST_BOLD_R if bold else ST_TD)
    def label(txt, indent=False, bold=False, sub=False):
        p='    ' if indent else ''
        st=ST_BOLD if bold else (s('sub',fontSize=7.5,textColor=GRAY,leading=11) if sub else ST_TD_L)
        return Paragraph(p+txt,st)
    def cat(txt):
        return [Paragraph(txt,s('cat',fontName='Helvetica-Bold',fontSize=7.5,textColor=TEAL,leading=11)),'','','','']

    feb_r=d.get('revenue_feb','0'); mar_r=d.get('revenue_mar','0'); apr_r=d.get('revenue_apr','0')
    total_r=d.get('total_revenue','0')
    food=d.get('food_sales','0'); drink=d.get('drink_sales','0')
    cogs=d.get('total_cogs','0'); gp=d.get('gross_profit','0')
    gm=d.get('gross_margin','0')
    rent=d.get('rent','0'); wages=d.get('wages','0'); utils=d.get('utilities','0')
    mktg=d.get('marketing','0'); misc=d.get('miscellaneous','0')
    opex=d.get('total_opex','0'); np_=d.get('net_profit','0'); nm=d.get('net_margin','0')

    rows=[
        [th('',False),th('Feb'),th('Mar'),th('Apr'),th('Q1 Total')],
        cat('REVENUE'),
        [label('Food Sales',indent=True),td('—'),td('—'),td('—'),money(food)],
        [label('Drink Sales',indent=True),td('—'),td('—'),td('—'),money(drink)],
        [label('Total Revenue',bold=True),money(feb_r,True),money(mar_r,True),money(apr_r,True),money(total_r,True)],
        [Paragraph('')],'','','','',
        cat('COST OF GOODS SOLD'),
        [label('Total COGS',bold=True),td('—'),td('—'),td('—'),money(cogs,True)],
        [Paragraph('')],'','','','',
        [label('GROSS PROFIT',bold=True),td('—'),td('—'),td('—'),money(gp,True)],
        [label('Gross Margin %',sub=True),td('—'),td('—'),td('—'),td(fmtp(gm))],
        [Paragraph('')],'','','','',
        cat('OPERATING EXPENSES'),
        [label('Rent & Rates',indent=True),td('—'),td('—'),td('—'),money(rent)],
        [label('Staff Wages',indent=True),td('—'),td('—'),td('—'),money(wages)],
        [label('Utilities',indent=True),td('—'),td('—'),td('—'),money(utils)],
        [label('Marketing',indent=True),td('—'),td('—'),td('—'),money(mktg)],
        [label('Miscellaneous',indent=True),td('—'),td('—'),td('—'),money(misc)],
        [label('Total OpEx',bold=True),td('—'),td('—'),td('—'),money(opex,True)],
        [Paragraph('')],'','','','',
        [label('NET PROFIT',bold=True),td('—'),td('—'),td('—'),money(np_,True)],
        [label('Net Margin %',sub=True),td('—'),td('—'),td('—'),td(fmtp(nm))],
    ]

    cw=[60*mm,28*mm,28*mm,28*mm,28*mm]
    t=Table(rows,colWidths=cw,repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),NAVY),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE,OFFWHITE]),
        ('BACKGROUND',(0,4),(-1,4),TEAL_LITE),
        ('BACKGROUND',(0,9),(-1,9),TEAL_LITE),
        ('BACKGROUND',(0,18),(-1,18),TEAL_LITE),
        ('BACKGROUND',(0,20),(-1,20),colors.HexColor('#FFF7E6')),
        ('LINEBELOW',(0,0),(-1,0),1,TEAL),
        ('LINEBELOW',(0,4),(-1,4),0.5,BORDER),
        ('LINEBELOW',(0,9),(-1,9),0.5,BORDER),
        ('LINEBELOW',(0,18),(-1,18),0.5,BORDER),
        ('LINEBELOW',(0,20),(-1,-1),1.5,NAVY),
        ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
        ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
    ]))
    return t

def build_report(d):
    buf=io.BytesIO()
    doc=SimpleDocTemplate(buf,pagesize=A4,leftMargin=17*mm,rightMargin=17*mm,topMargin=0,bottomMargin=12*mm)
    story=[]

    # HEADER
    conf_pill=Table([[Paragraph('CONFIDENTIAL',s('cf',fontName='Helvetica-Bold',fontSize=7,textColor=NAVY,leading=9,alignment=TA_CENTER))]],colWidths=[22*mm])
    conf_pill.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),GOLD),('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4)]))
    hdr_inner=Table([
        [Paragraph(d.get('business_name','Client Business'),s('ht',fontName='Helvetica-Bold',fontSize=22,textColor=WHITE,leading=28))],
        [Paragraph(f"Quarterly Financial Report &nbsp;·&nbsp; {d.get('period','Q1')} &nbsp;·&nbsp; GBP (£)",s('hs',fontSize=9.5,textColor=colors.HexColor('#9BB5D4'),leading=14))],
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
        Paragraph(d.get('executive_summary','No summary provided.'),ST_BODY),
        Spacer(1,4*mm),
    ]))

    # KPI CARDS
    kpis=[
        kpi_card(fmt(d.get('total_revenue','0')),'Total Revenue','Q1 Period',True),
        kpi_card(fmt(d.get('net_profit','0')),'Net Profit','Q1 Period',True),
        kpi_card(fmtp(d.get('gross_margin','0')),'Gross Margin','Q1 Average',True),
        kpi_card(fmtp(d.get('net_margin','0')),'Net Margin','Q1 Average',True),
    ]
    kpi_row=Table([kpis],colWidths=[38*mm]*4)
    kpi_row.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),2),('RIGHTPADDING',(0,0),(-1,-1),2),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
    story.append(KeepTogether([kpi_row,Spacer(1,5*mm)]))

    # REVENUE CHART + MARGINS
    rev_vals=[d.get('revenue_feb','0'),d.get('revenue_mar','0'),d.get('revenue_apr','0')]
    if any(clean(v)>0 for v in rev_vals):
        chart=bar_chart(['Feb','Mar','Apr'],rev_vals)
        gm=clean(d.get('gross_margin','0')); nm_v=clean(d.get('net_margin','0'))
        nm_feb=clean(d.get('net_margin_feb','0')); nm_mar=clean(d.get('net_margin_mar','0')); nm_apr=clean(d.get('net_margin_apr','0'))
        if gm>1: gm=gm/100
        if nm_v>1: nm_v=nm_v/100
        if nm_feb>1: nm_feb=nm_feb/100
        if nm_mar>1: nm_mar=nm_mar/100
        if nm_apr>1: nm_apr=nm_apr/100
        food_v=clean(d.get('food_sales','0')); drink_v=clean(d.get('drink_sales','0')); total_v=food_v+drink_v
        food_pct=food_v/total_v if total_v>0 else 0; drink_pct=drink_v/total_v if total_v>0 else 0
        margin_rows=[
            [Paragraph('Margin Analysis',s('ma',fontName='Helvetica-Bold',fontSize=8,textColor=NAVY,leading=12))],
            [Spacer(1,2*mm)],
            [Paragraph('Gross Margin',ST_SMALL)],[margin_bar(gm,'Q1 Average',TEAL)],
            [Spacer(1,1*mm)],
            [Paragraph('Net Margin by Month',ST_SMALL)],
            [margin_bar(nm_feb,'February',RED_TEXT)],[Spacer(1,1*mm)],
            [margin_bar(nm_mar,'March',GOLD)],[Spacer(1,1*mm)],
            [margin_bar(nm_apr,'April',GREEN_TEXT)],
            [Spacer(1,2*mm)],
            [Paragraph('Revenue Mix (Q1)',ST_SMALL)],
            [margin_bar(food_pct,f'Food Sales {food_pct:.0%}',TEAL)],[Spacer(1,1*mm)],
            [margin_bar(drink_pct,f'Drink Sales {drink_pct:.0%}',colors.HexColor('#0B6E60'))],
        ]
        m_t=Table(margin_rows,colWidths=[70*mm])
        m_t.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
        combined=Table([[chart,m_t]],colWidths=[100*mm,75*mm])
        combined.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
        story.append(KeepTogether([section_header('Revenue Performance & Margins'),Spacer(1,3*mm),combined,Spacer(1,5*mm)]))

    # EXPENSE BREAKDOWN CARDS
    total_r=clean(d.get('total_revenue','1')) or 1
    rent_v=clean(d.get('rent','0')); wages_v=clean(d.get('wages','0'))
    utils_v=clean(d.get('utilities','0')); mktg_v=clean(d.get('marketing','0'))
    misc_v=clean(d.get('miscellaneous','0'))
    if any(v>0 for v in [rent_v,wages_v,utils_v,mktg_v,misc_v]):
        exp_cards=[
            exp_card('Rent & Rates',rent_v,rent_v/total_r*100,'stable'),
            exp_card('Staff Wages',wages_v,wages_v/total_r*100,'up'),
            exp_card('Utilities',utils_v,utils_v/total_r*100,'down'),
            exp_card('Marketing',mktg_v,mktg_v/total_r*100,'up'),
            exp_card('Miscellaneous',misc_v,misc_v/total_r*100,'stable'),
        ]
        exp_row=Table([exp_cards],colWidths=[33*mm]*5)
        exp_row.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),2),('RIGHTPADDING',(0,0),(-1,-1),2),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
        story.append(KeepTogether([section_header('Operating Expense Breakdown'),Spacer(1,3*mm),exp_row,Spacer(1,5*mm)]))

    # P&L TABLE
    story.append(KeepTogether([section_header('Full Profit & Loss Statement'),Spacer(1,3*mm)]))
    story.append(pl_table(d))
    story.append(Spacer(1,5*mm))

    # KEY TRENDS
    story.append(KeepTogether([
        section_header('Key Trends & Analysis'),Spacer(1,3*mm),
        Paragraph(d.get('analysis','No analysis provided.'),ST_BODY),
        Spacer(1,5*mm),
    ]))

    # FLAGS
    raw_flags=d.get('flags','')
    flag_lines=[f.strip() for f in raw_flags.replace('FLAG:','\nFLAG:').split('\n') if 'FLAG:' in f]
    story.append(KeepTogether([section_header('Flags & Items to Watch'),Spacer(1,3*mm)]))
    if flag_lines:
        for i,fl in enumerate(flag_lines):
            text=fl.replace('FLAG:','').strip()
            story.append(KeepTogether([flag_card(i+1,text),Spacer(1,2*mm)]))
    else:
        story.append(Paragraph(raw_flags,ST_BODY))
    story.append(Spacer(1,4*mm))

    # OUTLOOK
    story.append(KeepTogether([
        section_header('Outlook'),Spacer(1,3*mm),
        Paragraph(d.get('outlook','No outlook provided.'),ST_BODY),
        Spacer(1,4*mm),
    ]))

    # FOOTER
    ft_data=[[Paragraph(f"Prepared by FinReportAI &nbsp;·&nbsp; {d.get('period','')} &nbsp;·&nbsp; All figures GBP (£) &nbsp;·&nbsp; Confidential",ST_FOOTER)]]
    ft=Table(ft_data,colWidths=[175*mm])
    ft.setStyle(TableStyle([('LINEABOVE',(0,0),(-1,0),0.5,BORDER),('TOPPADDING',(0,0),(-1,-1),5),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
    story.append(ft)

    doc.build(story)
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
