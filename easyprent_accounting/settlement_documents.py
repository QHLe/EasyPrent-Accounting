"""One settlement document model consumed by the PDF and ODS renderers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import html
from io import BytesIO
import sqlite3

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .config import AppConfig
from .ods_template import render_settlement_template
from .settings import get_application_settings
from .settlements import Settlements, calculate_settlement_snapshot


ALLOCATION_LABELS = {
    "area": "Miteigentumsanteile (MEA)",
    "unit_count": "Einheiten",
    "occupants": "Personen",
}


@dataclass(frozen=True, slots=True)
class SettlementDocumentLine:
    label: str
    category: str
    allocation_method: str
    period_amount: str
    basis_value: str
    basis_total: str
    share: str
    allocation_periods: tuple[dict[str, str], ...]
    charge_type: str
    recurrence: str
    interval_name: str | None
    consumption_unit: str | None
    consumption_value: str | None
    tenant_consumption_value: str | None

    def template_item(self) -> dict:
        item = {
            "label": self.label,
            "expense_category": self.category,
            "allocation_method": self.allocation_method,
            "period_amount": self.period_amount,
            "basis_value": self.basis_value,
            "basis_total": self.basis_total,
            "share": self.share,
            "allocation_periods": list(self.allocation_periods),
            "charge_type": self.charge_type,
            "recurrence": self.recurrence,
            "interval_name": self.interval_name,
            "tenant_consumption_value": self.tenant_consumption_value,
        }
        if self.consumption_unit is not None:
            item["consumption_unit"] = self.consumption_unit
        if self.consumption_value is not None:
            item["consumption_value"] = self.consumption_value
        return item


@dataclass(frozen=True, slots=True)
class SettlementDocumentPayment:
    booking_date: str
    description: str
    amount: str


@dataclass(frozen=True, slots=True)
class SettlementDocumentModel:
    tenant_name: str
    tenant_street: str
    tenant_city_line: str
    object_label: str
    object_lines: tuple[str, ...]
    property_name: str
    property_street: str
    property_city_line: str
    organization_name: str
    sender_name: str
    sender_street: str
    sender_city_line: str
    created_on: str
    billing_period_start: str
    billing_period_end: str
    period_label: str
    line_items: tuple[SettlementDocumentLine, ...]
    allocated_costs: str
    advances_paid: str
    balance: str
    advance_payments: tuple[SettlementDocumentPayment, ...]


def _money(value: str) -> str:
    return f"{Decimal(value):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".") + " €"


class SettlementDocuments:
    """Build a shared document projection, then render it with either adapter."""

    def __init__(self, connection: sqlite3.Connection, config: AppConfig | None = None):
        self.connection = connection
        self.config = config

    def model_for_period(
        self,
        property_id: int | None,
        lease_id: int,
        period_start: str,
        period_end: str,
        unit_id: int | None = None,
        payment_split_guids: set[str] | None = None,
    ) -> SettlementDocumentModel:
        snapshot = Settlements(self.connection).snapshot_for_period(
            property_id, period_start, period_end, unit_id, payment_split_guids
        )
        settlement = calculate_settlement_snapshot(snapshot)
        result = next((row for row in settlement["results"] if row["lease_id"] == lease_id), None)
        if result is None:
            raise ValueError("lease is not part of the selected settlement period")
        details = self.connection.execute(
            """
            SELECT p.name AS property_name,
                   p.street AS property_street, p.postal_code AS property_postal_code,
                   p.city AS property_city, o.name AS organization_name,
                   t.full_name AS tenant_name,
                   t.alternate_street, t.alternate_postal_code, t.alternate_city,
                   u.label AS unit_label, u.street AS unit_street,
                   u.postal_code AS unit_postal_code, u.city AS unit_city,
                   r.label AS room_label,
                   b.street AS building_street,
                   b.postal_code AS building_postal_code, b.city AS building_city
            FROM leases l JOIN tenants t ON t.id = l.tenant_id
            JOIN units u ON u.id = l.unit_id
            LEFT JOIN rooms r ON r.id = l.room_id
            LEFT JOIN buildings b ON b.id = u.building_id
            LEFT JOIN properties p ON p.id = b.property_id
            LEFT JOIN organizations o ON o.id = p.organization_id
            WHERE l.id = ? AND (? IS NULL OR p.id = ?) AND (? IS NULL OR u.id = ?)
            """,
            (lease_id, property_id, property_id, unit_id, unit_id),
        ).fetchone()
        if details is None:
            raise ValueError("lease not found for selected settlement object")

        unit_street = str(details["unit_street"] or details["building_street"] or details["property_street"] or "")
        unit_postal_code = str(details["unit_postal_code"] or details["building_postal_code"] or details["property_postal_code"] or "")
        unit_city = str(details["unit_city"] or details["building_city"] or details["property_city"] or "")
        has_alternate = all(details[field] for field in ("alternate_street", "alternate_postal_code", "alternate_city"))
        tenant_street = str(details["alternate_street"] if has_alternate else unit_street)
        tenant_postal_code = str(details["alternate_postal_code"] if has_alternate else unit_postal_code)
        tenant_city = str(details["alternate_city"] if has_alternate else unit_city)
        tenant_city_line = " ".join(part for part in (tenant_postal_code, tenant_city) if part)
        property_city_line = " ".join(
            str(part) for part in (details["property_postal_code"], details["property_city"]) if part
        )
        settings = get_application_settings(self.connection) if self.config else {}
        sender_name = (
            str(settings.get("sender_name") or self.config.sender.name or details["organization_name"] or "")
            if self.config else str(details["organization_name"] or "")
        )
        sender_street = (
            str(settings.get("sender_street") or self.config.sender.street or "")
            if self.config else str(details["property_street"] or "")
        )
        sender_city_line = (
            str(settings.get("sender_city") or self.config.sender.city or "")
            if self.config else property_city_line
        )
        lines = tuple(
            SettlementDocumentLine(
                label=str(item["label"]), category=str(item["expense_category"]),
                allocation_method=str(item["allocation_method"]),
                period_amount=str(item["period_amount"]),
                basis_value=str(item["basis_value"]), basis_total=str(item["basis_total"]),
                share=str(item["share"]),
                allocation_periods=tuple(item["allocation_periods"]),
                charge_type=str(item["charge_type"]), recurrence=str(item["recurrence"]),
                interval_name=item["interval_name"],
                consumption_unit=item.get("consumption_unit"),
                consumption_value=item.get("consumption_value"),
                tenant_consumption_value=item.get("tenant_consumption_value"),
            ) for item in result["line_items"]
        )
        payments = tuple(
            SettlementDocumentPayment(
                booking_date=payment.booking_date.strftime("%d.%m.%Y"),
                description=payment.description,
                amount=f"{-payment.amount:.2f}",
            )
            for payment in snapshot.payments if payment.lease_id == lease_id
        )
        start = date.fromisoformat(result["billing_period_start"])
        end = date.fromisoformat(result["billing_period_end"])
        return SettlementDocumentModel(
            tenant_name=str(result["tenant_name"]),
            tenant_street=tenant_street,
            tenant_city_line=tenant_city_line,
            object_label=str(details["room_label"] or details["unit_label"]),
            object_lines=(str(result["unit_label"]), unit_street,
                          " ".join(part for part in (unit_postal_code, unit_city) if part)),
            property_name=str(details["property_name"] or ""),
            property_street=str(details["property_street"] or ""),
            property_city_line=property_city_line,
            organization_name=str(details["organization_name"] or ""),
            sender_name=sender_name, sender_street=sender_street,
            sender_city_line=sender_city_line,
            created_on=date.today().strftime("%d.%m.%Y"),
            billing_period_start=result["billing_period_start"],
            billing_period_end=result["billing_period_end"],
            period_label=f"{start:%d.%m.%Y} – {end:%d.%m.%Y}",
            line_items=lines,
            allocated_costs=result["allocated_costs"],
            advances_paid=result["advances_paid"],
            balance=result["balance"],
            advance_payments=payments,
        )

    def pdf_for_period(
        self, property_id: int | None, lease_id: int,
        period_start: str, period_end: str, unit_id: int | None = None,
    ) -> tuple[bytes, str]:
        model = self.model_for_period(property_id, lease_id, period_start, period_end, unit_id)
        stream = BytesIO()
        document = SimpleDocTemplate(stream, pagesize=A4, leftMargin=18 * mm,
                                     rightMargin=18 * mm, topMargin=18 * mm)
        styles = getSampleStyleSheet()
        story = [
            Paragraph(html.escape(model.organization_name), styles["Normal"]),
            Paragraph(html.escape(f"{model.property_street}, {model.property_city_line}"), styles["Normal"]),
            Spacer(1, 15 * mm),
            Paragraph(html.escape(model.tenant_name), styles["Normal"]),
            Paragraph(html.escape(model.tenant_street), styles["Normal"]),
            Paragraph(html.escape(model.tenant_city_line), styles["Normal"]),
            Paragraph(html.escape(f"Mietobjekt: {model.object_label}"), styles["Normal"]),
            Spacer(1, 10 * mm),
            Paragraph("Nebenkostenabrechnung", styles["Title"]),
            Paragraph(f"Abrechnungszeitraum: {model.billing_period_start} bis {model.billing_period_end}", styles["Normal"]),
            Spacer(1, 5 * mm),
        ]
        rows = [["Kostenart", "Schlüssel", "Jahreskosten", "Mietzeitraum", "Ihr Anteil"]]
        for item in model.line_items:
            rows.append([
                item.label,
                ALLOCATION_LABELS.get(item.allocation_method, item.allocation_method)
                + f" ({item.basis_value} / {item.basis_total})",
                _money(item.period_amount), _money(item.period_amount), _money(item.share),
            ])
        rows.append(["", "Umlagefähige Kosten", "", "", _money(model.allocated_costs)])
        table = Table(rows, colWidths=[42 * mm, 41 * mm, 29 * mm, 29 * mm, 28 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf2")),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("LEADING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(table)
        document.build(story)
        safe_tenant = "".join(char if char.isalnum() else "-" for char in model.tenant_name)
        return stream.getvalue(), f"Nebenkostenabrechnung-{safe_tenant}-{period_start[:4]}.pdf"

    def ods_for_period(
        self, property_id: int | None, lease_id: int,
        period_start: str, period_end: str, unit_id: int | None = None,
        payment_split_guids: set[str] | None = None,
    ) -> tuple[bytes, str]:
        if self.config is None:
            raise ValueError("ODS rendering requires application configuration")
        model = self.model_for_period(
            property_id, lease_id, period_start, period_end, unit_id, payment_split_guids
        )
        contents = render_settlement_template(
            template_path=self.config.settlement_template,
            sender_name=model.sender_name,
            sender_street=model.sender_street,
            sender_city_line=model.sender_city_line,
            tenant_name=model.tenant_name,
            tenant_street=model.tenant_street,
            tenant_city_line=model.tenant_city_line,
            object_lines=list(model.object_lines),
            created_on=model.created_on,
            period_label=model.period_label,
            line_items=[item.template_item() for item in model.line_items],
            allocated_costs=model.allocated_costs,
            advances_paid=model.advances_paid,
            balance=model.balance,
            advance_payments=[
                {"booking_date": payment.booking_date, "description": payment.description,
                 "amount": payment.amount}
                for payment in model.advance_payments
            ],
        )
        safe_tenant = "".join(char if char.isalnum() else "-" for char in model.tenant_name)
        return contents, f"Nebenkostenabrechnung-{safe_tenant}-{period_start[:4]}.ods"

    def ods_for_run(self, settlement_id: str, lease_id: int) -> tuple[bytes, str]:
        run = self.connection.execute(
            "SELECT * FROM settlement_runs WHERE id = ?", (settlement_id,)
        ).fetchone()
        if run is None:
            raise ValueError("settlement run not found")
        considered = {
            str(row["split_guid"])
            for row in self.connection.execute(
                "SELECT split_guid FROM settlement_payment_assignments "
                "WHERE settlement_id = ? AND status = 'considered'",
                (settlement_id,),
            ).fetchall()
        }
        return self.ods_for_period(
            run["property_id"], lease_id, run["period_start"], run["period_end"],
            run["unit_id"], considered,
        )
