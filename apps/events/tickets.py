"""The printed ticket for a confirmed event booking.

Drawn on reportlab's canvas rather than with platypus flowables, because a ticket is a fixed
piece of artwork: every line is placed by hand. It follows the site's look - black ink on white
stock, one typeface, no decoration beyond the hairlines and the tear - and carries a QR code
that points at the gate-check page for the booking.
"""
from io import BytesIO

import qrcode
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django.utils.dateformat import format as format_date
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

# The paper tokens, as close as a PDF gets: ink on white stock with a hairline rule.
INK = HexColor('#111111')
MUTED = HexColor('#55534E')
LINE = HexColor('#DEDBD4')
TINT = HexColor('#F4F2EE')
STOCK = HexColor('#FFFFFF')

BODY = 'Helvetica'
BOLD = 'Helvetica-Bold'

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CARD_W = PAGE_W - 2 * MARGIN
MIN_CARD_H = 92 * mm  # tall enough for the stub; the card grows if the face needs more
STUB_W = 58 * mm
PAD = 10 * mm
QR_SIZE = 34 * mm

TITLE_SIZES = (26, 22, 18, 15)
TITLE_LEAD = 1.12
ROW_LEAD = 5 * mm
ROW_GAP = 2.4 * mm
LABEL_TO_TITLE = 13 * mm
TITLE_TO_RULE = 5 * mm
RULE_TO_ROWS = 9 * mm

# Helvetica has no taka sign, so money is written out.
CURRENCY = 'BDT'


def ticket_filename(booking):
    return f'EventEase-ticket-{booking.reference}.pdf'


def ticket_pdf(booking, verify_url):
    """Return the ticket for one booking as PDF bytes.

    `verify_url` is what the QR code holds: the absolute address of the gate-check page.
    """
    buffer = BytesIO()
    sheet = canvas.Canvas(buffer, pagesize=A4)
    sheet.setTitle(f'EventEase ticket {booking.reference}')
    sheet.setAuthor('EventEase')

    face = _face_plan(booking, CARD_W - STUB_W - 2 * PAD)
    card_height = max(MIN_CARD_H, face['height'] + 2 * PAD)
    card_top = PAGE_H - MARGIN - 14 * mm

    _masthead(sheet, PAGE_H - MARGIN - 4 * mm)
    _card(sheet, booking, verify_url, card_top, card_height, face)
    _terms(sheet, booking, card_top - card_height - 16 * mm)
    _footer(sheet, booking)

    sheet.showPage()
    sheet.save()
    return buffer.getvalue()


# ---------------------------------------------------------------- drawing pieces

def _masthead(sheet, baseline):
    _label(sheet, 'EventEase', MARGIN, baseline, size=11, colour=INK)
    _label(sheet, 'Event ticket', PAGE_W - MARGIN, baseline, align='right')


def _face_plan(booking, width):
    """Measure the face of the card before anything is drawn.

    A long title or a long address has to make the card taller rather than run off the
    bottom of it, so the wrapping is worked out first and the height falls out of it.
    """
    size, title_lines = _fitted(booking.event.title, width, sizes=TITLE_SIZES, max_lines=2)
    rows = [(name, _wrap(str(value), BOLD, 10, width - 30 * mm)) for name, value in _ticket_rows(booking)]

    height = (LABEL_TO_TITLE + len(title_lines) * size * TITLE_LEAD + TITLE_TO_RULE + RULE_TO_ROWS
              + sum(len(lines) * ROW_LEAD + ROW_GAP for _, lines in rows))
    return {'size': size, 'title_lines': title_lines, 'rows': rows, 'height': height}


def _card(sheet, booking, verify_url, top, height, face):
    bottom = top - height
    tear = MARGIN + CARD_W - STUB_W

    sheet.setFillColor(STOCK)
    sheet.setStrokeColor(LINE)
    sheet.setLineWidth(0.8)
    sheet.rect(MARGIN, bottom, CARD_W, height, stroke=1, fill=1)

    # The stub is tinted so the tear reads as a perforation rather than a stray line.
    sheet.setFillColor(TINT)
    sheet.rect(tear, bottom, STUB_W, height, stroke=0, fill=1)
    sheet.setStrokeColor(MUTED)
    sheet.setDash(1.5, 2.5)
    sheet.line(tear, bottom + 4 * mm, tear, top - 4 * mm)
    sheet.setDash()

    _card_face(sheet, booking, face, left=MARGIN + PAD, right=tear - PAD, top=top - PAD)
    _card_stub(sheet, booking, verify_url, left=tear, top=top - PAD)


def _card_face(sheet, booking, face, left, right, top):
    cursor = top

    _label(sheet, f'Admit {booking.attendees_count}', left, cursor - 4)
    cursor -= LABEL_TO_TITLE

    sheet.setFont(BOLD, face['size'])
    sheet.setFillColor(INK)
    for line in face['title_lines']:
        sheet.drawString(left, cursor, line)
        cursor -= face['size'] * TITLE_LEAD
    cursor -= TITLE_TO_RULE

    sheet.setStrokeColor(LINE)
    sheet.setLineWidth(0.8)
    sheet.line(left, cursor, right, cursor)
    cursor -= RULE_TO_ROWS

    for name, lines in face['rows']:
        cursor = _row(sheet, name, lines, left, cursor)


def _ticket_rows(booking):
    """What the gate and the ticket holder both need to see, in reading order."""
    event = booking.event
    payment = _payment(booking)
    when = format_date(timezone.localtime(event.start_date), 'D j M Y, g:i A')
    where = ', '.join(part for part in [event.venue_name, event.venue_address] if part) or 'To be announced'
    holder = booking.attendee_name or booking.user.get_full_name() or booking.user.username

    if event.is_free or not booking.total_amount:
        paid = 'Free event'
    else:
        paid = f'{CURRENCY} {booking.total_amount:,.2f}'
        if payment:
            paid += f' by {payment.get_payment_method_display()}'

    return [
        ('When', when),
        ('Where', where),
        ('Ticket holder', holder),
        ('Paid', paid),
        ('Booking', f'{booking.reference} ({booking.get_status_display().lower()})'),
        ('Transaction', payment.transaction_id if payment and payment.transaction_id else 'Not applicable'),
    ]


def _card_stub(sheet, booking, verify_url, left, top):
    centre = left + STUB_W / 2
    _label(sheet, 'Scan at the gate', centre, top - 4, align='centre')

    qr_x = centre - QR_SIZE / 2
    qr_y = top - 12 * mm - QR_SIZE
    sheet.drawImage(_qr_image(verify_url), qr_x, qr_y, QR_SIZE, QR_SIZE)

    sheet.setFont(BOLD, 13)
    sheet.setFillColor(INK)
    sheet.drawCentredString(centre, qr_y - 9 * mm, booking.reference)

    tickets = booking.attendees_count
    sheet.setFont(BODY, 8.5)
    sheet.setFillColor(MUTED)
    sheet.drawCentredString(centre, qr_y - 15 * mm, f'{tickets} ticket' + ('' if tickets == 1 else 's'))
    sheet.drawCentredString(centre, qr_y - 20 * mm, format_date(timezone.localtime(booking.event.start_date), 'j M Y'))


def _terms(sheet, booking, top):
    cursor = top
    _label(sheet, 'On the day', MARGIN, cursor)
    cursor -= 7 * mm

    notes = [
        'Doors open 30 minutes before the start time and close 30 minutes after it.',
        'Bring photo ID in the name printed on this ticket.',
        'The QR code is scanned once. A photo of it on a phone works as well as paper.',
    ]
    if booking.event.contact_email:
        notes.append(f'Questions about the event: {booking.event.contact_email}')

    for note in notes:
        sheet.setFont(BODY, 9.5)
        sheet.setFillColor(MUTED)
        sheet.drawString(MARGIN, cursor, '—')
        sheet.setFillColor(INK)
        for line in _wrap(note, BODY, 9.5, CARD_W - 8 * mm):
            sheet.drawString(MARGIN + 8 * mm, cursor, line)
            cursor -= 5.2 * mm
        cursor -= 1.6 * mm


def _footer(sheet, booking):
    issued = format_date(timezone.localtime(timezone.now()), 'j M Y, g:i A')
    sheet.setFont(BODY, 7.5)
    sheet.setFillColor(MUTED)
    sheet.drawString(MARGIN, MARGIN, f'Issued by EventEase on {issued}')
    sheet.drawRightString(PAGE_W - MARGIN, MARGIN, booking.reference)


# ---------------------------------------------------------------- small helpers

def _payment(booking):
    """The payment for this booking, or None: a free booking never has one."""
    try:
        return booking.payment
    except ObjectDoesNotExist:
        return None


def _label(sheet, text, x, y, size=7.5, colour=MUTED, align='left'):
    """A small letterspaced capital label, the same device the site uses above a block.

    Letter spacing belongs to a text object rather than the canvas, so the alignment is
    worked out here: the tracking makes the string wider than stringWidth alone reports.
    """
    text = text.upper()
    tracking = 1.6
    width = stringWidth(text, BOLD, size) + tracking * max(len(text) - 1, 0)
    start = {'left': x, 'right': x - width, 'centre': x - width / 2}[align]

    label = sheet.beginText(start, y)
    label.setFont(BOLD, size)
    label.setFillColor(colour)
    label.setCharSpace(tracking)
    label.textOut(text)
    label.setCharSpace(0)  # Tc survives BT/ET, so every later line would inherit the tracking
    sheet.drawText(label)


def _row(sheet, name, lines, left, top):
    """One label-and-value line, already wrapped; returns the next free baseline."""
    value_x = left + 30 * mm
    sheet.setFont(BODY, 9)
    sheet.setFillColor(MUTED)
    sheet.drawString(left, top, name)

    sheet.setFont(BOLD, 10)
    sheet.setFillColor(INK)
    cursor = top
    for line in lines:
        sheet.drawString(value_x, cursor, line)
        cursor -= ROW_LEAD
    return cursor - ROW_GAP


def _wrap(text, font, size, width):
    """Break text into lines that fit `width`, measured in the font it will be drawn in."""
    lines, line = [], ''
    for word in text.split():
        trial = f'{line} {word}'.strip()
        if not line or stringWidth(trial, font, size) <= width:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines or ['']


def _fitted(text, width, sizes, max_lines):
    """The largest of `sizes` at which `text` wraps into `max_lines` or fewer."""
    for size in sizes:
        lines = _wrap(text, BOLD, size, width)
        if len(lines) <= max_lines:
            return size, lines
    smallest = sizes[-1]
    return smallest, _wrap(text, BOLD, smallest, width)[:max_lines]


def _qr_image(payload):
    """A QR code as something reportlab can draw. Error correction M survives a crease."""
    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    code.add_data(payload)
    code.make(fit=True)

    buffer = BytesIO()
    code.make_image(fill_color='black', back_color='white').save(buffer, format='PNG')
    buffer.seek(0)
    return ImageReader(buffer)
