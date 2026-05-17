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

def fmt(n):
    try: return f'£{float(str(n).replace(",","").replace("£","")):,.0f}'
    except: return str(n)

def bar_chart(feb, mar, apr, w=100, h=44):
    try: feb,mar,apr = float(str(feb).replace(",","").replace("£","")),float(str(mar).replace(",","").replace("£","")),float(str(apr).replace(",","").replace("£",""))
    except: feb,mar,apr = 0,0,0
    maxv = max(feb,mar,apr,1)*1.15
    dw = Drawing(w*mm, h*mm)
    bw=12*mm; gap=8*mm; base_y=8*mm; chart_h=(h-12)*mm
    cols=[TEAL,colors.HexColor('#0B6E60'),colors.HexColor('#084F45')]
    for i,(v,c,l) in enumerate(zip([feb,mar,apr],cols,['Feb','Mar','Apr'])):
        x=10*mm+i*(bw+gap); bh=(v/maxv)*chart_h
        dw.add(Rect(x,base_y,bw,bh,fillColor=c,strokeColor=None))
        dw.add(String(x+bw/2,base_y-7*mm,l,fontSize=6.5,fillColor=GRAY,textAnchor='middle'))
        dw.add(String(x+bw/2,base_y+bh+1.5*mm,f'£{v/1000:.0f}k',fontSize=6.5,fillColor=NAVY,textAnchor='middle',fontName='Helvetica-Bold'))
    dw.add(Line(8*mm,base_y,w*mm-5*mm,base_y,strokeColor=BORDER,strokeWidth=0.5))
    return dw

def margin_bar(pct_val, label, color, w=65, h=10):
    try: pct_val=float(str(pct_val).replace('%',''))/100 if '%' in str(pct_val) else float(pct_val)
    except: pct_val=0
    dw=Drawing(w*mm,h*mm); track_w=(w-4)*mm; fill_w=track_w*min(pct_val,1.0)
    dw.add(Rect(2*mm,3*mm,track_w,4*mm,fillColor=BORDER,strokeColor=None,rx=2,ry=2))
    dw.add(Rect(2*mm,3*mm,fill_w,4*mm,fillColor=color,strokeColor=None,rx=2,ry=2))
    dw.add(String(2*mm,0.5*mm,label,fontSize=6,fillColor=GRAY,textAnchor='start'))
    dw.add(String((w-2)*mm,0.5*mm,f'{pct_val:.1%}',fontSize=6.5,fillColor=color,textAnchor='end',fontName='Helvetica-Bold'))
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

def flag_card(num, category, body, severity):
    color_map={
        'Positive':(GREEN_TEXT,GREEN_SOFT,'✓'),
        'Watch':(AMBER_TEXT,AMBER_SOFT,'!'),
        'Risk':(RED_TEXT,RED_SOFT,'✕'),
        'Info':(TEAL,TEAL_LITE,'i'),
    }
    tc,bg,icon=color_map.get(severity,(GRAY,OFFWHITE,'•'))
    icon_s=s('ico',fontName='Helvetica-Bold',fontSize=10,textColor=tc,alignment=TA_CENTER,leading=12)
    sev_s=s('sev',fontName='Helvetica-Bold',fontSize=7,textColor=tc,alignment=TA_CENTER,leading=9)
    data=[[[Paragraph(icon,icon_s),Paragraph(severity,sev_s)],
            [Paragraph(f'{num}. {category}',ST_FLAG_H),Spacer(1,2),Paragraph(body,ST_FLAG_B)]]]
    t=Table(data,colWidths=[14*mm,161*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(0,0),bg),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
        ('LEFTPADDING',(0,0),(0,0),3),('RIGHTPADDING',(0,0),(0,0),3),
        ('LEFTPADDING',(1,0),(1,0),8),('RIGHTPADDING',(1,0),(1,0),4),
        ('BOX',(0,0),(-1,-1),0.5,BORDER),
    ]))
    return t

def build_report(d):
    buf=io.BytesIO()
    doc=SimpleDocTemplate(buf,pagesize=A4,leftMargin=17*mm,rightMargin=17*mm,topMargin=0,bottomMargin=12*mm)
    story=[]

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

    story.append(KeepTogether([
        section_header('Executive Summary'),Spacer(1,3*mm),
        Paragraph(d.get('executive_summary','No summary provided.'),ST_BODY),
        Spacer(1,4*mm),
    ]))

    kpis=[
        kpi_card(d.get('total_revenue','N/A'),'Total Revenue','Q1 Period',True),
        kpi_card(d.get('net_profit','N/A'),'Net Profit','Q1 Period',True),
        kpi_card(d.get('gross_margin','N/A'),'Gross Margin','Q1 Average',True),
        kpi_card(d.get('net_margin','N/A'),'Net Margin','Q1 Average',True),
    ]
    kpi_row=Table([kpis],colWidths=[38*mm]*4)
    kpi_row.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),2),('RIGHTPADDING',(0,0),(-1,-1),2),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
    story.append(KeepTogether([kpi_row,Spacer(1,5*mm)]))

    story.append(KeepTogether([
        section_header('Key Trends & Analysis'),Spacer(1,3*mm),
        Paragraph(d.get('analysis','No analysis provided.'),ST_BODY),
        Spacer(1,5*mm),
    ]))

    raw_flags=d.get('flags','')
    flag_lines=[f.strip() for f in raw_flags.split('\n') if f.strip().startswith('FLAG:')]
    story.append(KeepTogether([section_header('Flags & Items to Watch'),Spacer(1,3*mm)]))
    if flag_lines:
        for i,fl in enumerate(flag_lines):
            text=fl.replace('FLAG:','').strip()
            story.append(KeepTogether([flag_card(i+1,'Flag',text,'Watch'),Spacer(1,2*mm)]))
    else:
        story.append(Paragraph(raw_flags,ST_BODY))
    story.append(Spacer(1,4*mm))

    story.append(KeepTogether([
        section_header('Outlook'),Spacer(1,3*mm),
        Paragraph(d.get('outlook','No outlook provided.'),ST_BODY),
        Spacer(1,4*mm),
    ]))

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
