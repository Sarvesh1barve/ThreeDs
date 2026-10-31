from io import BytesIO
from zoneinfo import ZoneInfo
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def order_pdf(order, masked: bool = False) -> bytes:
    out = BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm)
    styles = getSampleStyleSheet()
    phone = order.customer_phone
    if masked and len(phone) > 7:
        phone = phone[:3] + "•••••" + phone[-3:]
    title = "Order acknowledgement / Proforma"
    story = [Paragraph("Three D's", styles["Title"]), Paragraph(title, styles["Heading2"]), Spacer(1, 5*mm)]
    ist = order.created_at.replace(tzinfo=order.created_at.tzinfo or ZoneInfo("UTC")).astimezone(ZoneInfo("Asia/Kolkata"))
    story += [Paragraph(f"Order: <b>{order.public_id}</b><br/>Date: {ist:%d %b %Y, %I:%M %p} IST<br/>Customer: {order.customer_name}<br/>Mobile: {phone}<br/>Fulfilment: {order.fulfillment}<br/>Payment: {order.payment_status}", styles["BodyText"]), Spacer(1, 7*mm)]
    data = [["Item", "Qty", "Unit", "Amount"]]
    for item in order.items:
        label = item.product_name + (f" — {item.personalization}" if item.personalization else "")
        data.append([Paragraph(label, styles["BodyText"]), str(item.quantity), f"₹{item.unit_price_paise/100:,.2f}", f"₹{item.line_total_paise/100:,.2f}"])
    data += [["", "", "Subtotal", f"₹{order.subtotal_paise/100:,.2f}"], ["", "", "Delivery", f"₹{order.delivery_fee_paise/100:,.2f}"], ["", "", "Total", f"₹{order.total_paise/100:,.2f}"]]
    table = Table(data, colWidths=[90*mm, 18*mm, 29*mm, 29*mm], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#7356c9")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#ddd6de")), ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("ALIGN", (1,1), (-1,-1), "RIGHT"), ("VALIGN", (0,0), (-1,-1), "TOP"), ("TOPPADDING", (0,0), (-1,-1), 7), ("BOTTOMPADDING", (0,0), (-1,-1), 7)]))
    story += [table, Spacer(1, 8*mm), Paragraph("This is an order acknowledgement/proforma, not a tax invoice or proof of payment. Payment status is shown above.", styles["Italic"])]
    if order.note:
        story += [Spacer(1, 5*mm), Paragraph(f"Note: {order.note}", styles["BodyText"])]
    doc.build(story)
    return out.getvalue()

