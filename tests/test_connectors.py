"""Tests du Connector Framework (Phase 4 §2.4).

Couvre : mapping déclaratif, auth pluggable, connecteurs csv_excel / generic_sql
/ generic_rest (respx), registry déclaratif, SDK custom, webhook, et le garde-fou
de dépendance optionnelle (SOAP sans zeep).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import respx
from httpx import Response
from pydantic import SecretStr
from sqlalchemy import create_engine, text

from zolaos.connectors import (
    ApiKeyAuth,
    BasicAuth,
    Capability,
    CapabilityNotSupported,
    Employee,
    FieldMapping,
    HRConnector,
    IPAllowlist,
    JournalEntry,
    JournalLine,
    MappingError,
)
from zolaos.connectors.csv_excel import CsvExcelConnector
from zolaos.connectors.generic_rest import GenericRestConnector
from zolaos.connectors.generic_soap import GenericSoapConnector
from zolaos.connectors.generic_sql import GenericSqlConnector
from zolaos.connectors.base import ConnectorAuthError, ConnectorConfigError
from zolaos.connectors.custom_sdk.example import ExampleMemoryConnector
from zolaos.connectors.registry import (
    available_connectors,
    create_connector,
    register_connector,
)


# ============================================================ mapping

def test_mapping_apply_transforms() -> None:
    m = FieldMapping.from_dict(
        {
            "entity": "employee",
            "fields": {
                "id_externe": {"from": "id"},
                "nom_complet": {"from": "full_name", "transform": "strip"},
                "email": {"from": "mail", "transform": "lower"},
                "salaire_base_xaf": {"from": "sal", "transform": "to_decimal"},
                "actif": {"from": "is_active", "transform": "to_bool", "default": True},
            },
        }
    )
    out = m.apply({"id": "E1", "full_name": " Awa ", "mail": "A@X.CG", "sal": "300 000"})
    assert out["nom_complet"] == "Awa"
    assert out["email"] == "a@x.cg"
    assert out["salaire_base_xaf"] == Decimal("300000")
    assert out["actif"] is True
    assert out["country"] == "cg"  # défaut multi-pays


def test_mapping_unknown_transform_raises() -> None:
    with pytest.raises(MappingError):
        FieldMapping.from_dict(
            {"entity": "x", "fields": {"a": {"from": "b", "transform": "nope"}}}
        )


def test_mapping_from_yaml(tmp_path: Path) -> None:
    p = tmp_path / "m.yaml"
    p.write_text(
        "entity: employee\ncountry_default: ga\nfields:\n  nom_complet: { from: name }\n",
        encoding="utf-8",
    )
    m = FieldMapping.from_yaml(p)
    assert m.apply({"name": "Z"}) == {"nom_complet": "Z", "country": "ga"}


# ============================================================ auth

def test_auth_apikey_and_basic_headers() -> None:
    h: dict[str, str] = {}
    ApiKeyAuth(SecretStr("k"), header_name="X-Tok").apply_headers(h)
    BasicAuth("user", SecretStr("pwd")).apply_headers(h)
    assert h["X-Tok"] == "k"
    assert h["Authorization"].startswith("Basic ")


def test_ip_allowlist() -> None:
    al = IPAllowlist(["10.0.0.0/8", "192.168.1.5"])
    assert al.is_allowed("10.2.3.4")
    assert al.is_allowed("192.168.1.5")
    assert not al.is_allowed("8.8.8.8")
    assert not al.is_allowed("pas-une-ip")


# ============================================================ capacités

def test_capability_derivation_and_guard() -> None:
    class HROnly(HRConnector):
        name = "hr_only"

        async def list_employees(self, **f):  # type: ignore[no-untyped-def]
            return []

    c = HROnly()
    assert c.supports(Capability.LIST_EMPLOYEES)
    assert not c.supports(Capability.READ_INVOICE)
    with pytest.raises(CapabilityNotSupported):
        c._ensure(Capability.READ_INVOICE)


# ============================================================ csv_excel

async def test_csv_connector_list_employees(tmp_path: Path) -> None:
    f = tmp_path / "emp.csv"
    f.write_text("id,full_name\nE1,Awa Loemba\nE2,Paul Nkodia\n", encoding="utf-8")
    m = FieldMapping.from_dict(
        {"entity": "employee", "fields": {"id_externe": {"from": "id"}, "nom_complet": {"from": "full_name"}}}
    )
    conn = CsvExcelConnector(config={"path": str(f)}, mapping=m)
    async with conn:
        emps = await conn.list_employees()
    assert [e.nom_complet for e in emps] == ["Awa Loemba", "Paul Nkodia"]


async def test_csv_push_journal_entry(tmp_path: Path) -> None:
    out = tmp_path / "ecr.csv"
    conn = CsvExcelConnector(config={"path": str(tmp_path / "x"), "journal_output_path": str(out)})
    je = JournalEntry(
        date_ecriture=date(2026, 1, 5), journal="VT", libelle="Vente",
        lignes=[JournalLine(compte="411", libelle="c", debit_xaf=Decimal("1000")),
                JournalLine(compte="701", libelle="v", credit_xaf=Decimal("1000"))],
    )
    path = await conn.push_journal_entry(je)
    assert Path(path).exists()
    assert "411" in out.read_text(encoding="utf-8")


async def test_csv_push_unbalanced_rejected(tmp_path: Path) -> None:
    out = tmp_path / "ecr.csv"
    conn = CsvExcelConnector(config={"path": "x", "journal_output_path": str(out)})
    je = JournalEntry(
        date_ecriture=date(2026, 1, 5), journal="VT", libelle="X",
        lignes=[JournalLine(compte="411", libelle="c", debit_xaf=Decimal("1000"))],
    )
    with pytest.raises(ConnectorConfigError):
        await conn.push_journal_entry(je)


# ============================================================ generic_sql

async def test_generic_sql_sqlite(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    eng = create_engine(f"sqlite:///{db}")
    with eng.begin() as cx:
        cx.execute(text("CREATE TABLE emp(id_externe TEXT, nom_complet TEXT)"))
        cx.execute(text("INSERT INTO emp VALUES ('E9','Sylvie Ondongo')"))
    eng.dispose()
    conn = GenericSqlConnector(
        config={"dsn": f"sqlite:///{db}", "queries": {"employees": "SELECT id_externe, nom_complet FROM emp"}}
    )
    async with conn:
        assert await conn.healthcheck() is True
        emps = await conn.list_employees()
    assert emps[0].nom_complet == "Sylvie Ondongo"


# ============================================================ generic_rest (respx)

async def test_generic_rest_full_cycle() -> None:
    with respx.mock:
        respx.get("http://erp.test/api/employees").mock(
            return_value=Response(200, json=[{"id_externe": "E1", "nom_complet": "Ngoma"}])
        )
        respx.get("http://erp.test/api/invoices/INV1").mock(
            return_value=Response(200, json={
                "id_externe": "INV1", "numero": "INV1", "tiers": "ACME",
                "date_emission": "2026-01-01", "montant_ht_xaf": "100", "montant_ttc_xaf": "118"})
        )
        respx.post("http://erp.test/api/journal").mock(return_value=Response(201, json={"id": "JE9"}))
        conn = GenericRestConnector(config={
            "base_url": "http://erp.test/api",
            "endpoints": {"employees": "/employees", "invoice_by_id": "/invoices/{id}", "journal": "/journal"},
        })
        async with conn:
            emps = await conn.list_employees()
            assert emps[0].nom_complet == "Ngoma"
            inv = await conn.read_invoice("INV1")
            assert inv.tiers == "ACME"
            jid = await conn.push_journal_entry(JournalEntry(
                date_ecriture=date(2026, 1, 1), journal="OD", libelle="x",
                lignes=[JournalLine(compte="6", libelle="a", debit_xaf=Decimal("1")),
                        JournalLine(compte="7", libelle="b", credit_xaf=Decimal("1"))]))
            assert jid == "JE9"


# ============================================================ registry + custom SDK

async def test_registry_create_and_custom(tmp_path: Path) -> None:
    assert "csv_excel" in available_connectors()
    f = tmp_path / "e.csv"
    f.write_text("id_externe,nom_complet\nA1,Ngoma\n", encoding="utf-8")
    conn = create_connector({"type": "csv_excel", "config": {"path": str(f)}})
    async with conn:
        assert (await conn.list_employees())[0].nom_complet == "Ngoma"

    register_connector("example_memory", ExampleMemoryConnector)
    assert "example_memory" in available_connectors()
    c2 = create_connector({"type": "example_memory", "config": {"rows": [{"id_externe": "Z", "nom_complet": "Custom"}]}})
    assert (await c2.list_employees())[0].nom_complet == "Custom"


def test_registry_unknown_type_raises() -> None:
    with pytest.raises(ConnectorConfigError):
        create_connector({"type": "inexistant"})


# ============================================================ webhook

def test_webhook_signature_and_ip() -> None:
    import hashlib
    import hmac
    import json

    body = json.dumps({"id_externe": "F1", "numero": "INV-1", "tiers": "ACME",
                       "date_emission": "2026-02-01", "montant_ht_xaf": "1000", "montant_ttc_xaf": "1180"}).encode()
    sig = hmac.new(b"topsecret", body, hashlib.sha256).hexdigest()
    from zolaos.connectors.webhook import WebhookConnector

    wc = WebhookConnector(config={"secret": SecretStr("topsecret"), "entity": "invoice", "allowlist": ["10.0.0.0/8"]})
    inv = wc.ingest(body=body, signature=sig, ip="10.2.3.4")
    assert inv.numero == "INV-1"
    with pytest.raises(ConnectorAuthError):
        wc.ingest(body=body, signature="bad", ip="10.2.3.4")
    with pytest.raises(ConnectorAuthError):
        wc.ingest(body=body, signature=sig, ip="8.8.8.8")


# ============================================================ dépendance optionnelle

async def test_soap_missing_dependency_is_explicit() -> None:
    # zeep n'est pas une dépendance par défaut : erreur claire, pas d'ImportError opaque.
    with pytest.raises(ConnectorConfigError):
        await GenericSoapConnector(config={"wsdl": "http://x?wsdl"}).connect()
