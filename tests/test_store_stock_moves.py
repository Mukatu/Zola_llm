"""Tests STOCK-1 — mouvements de stock : valorisation PMP (moteur) + endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

import openpyxl
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.agents.erp.inventory import (
    ArticleStock,
    StockInsuffisant,
    appliquer_mouvement,
    pilotage_stock,
)
from zolaos.api.main import create_app
from zolaos.core.settings import Settings
from zolaos.db.session import get_session
from zolaos.db.store_models import StoreBase


def _settings() -> Settings:
    return Settings(
        POSTGRES_PASSWORD_APP="x", POSTGRES_PASSWORD_MIGRATIONS="x", JWT_SECRET="x" * 32
    )


@asynccontextmanager
async def _client(tmp_path):  # type: ignore[no-untyped-def]
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/stock.db")
    async with engine.begin() as conn:
        await conn.run_sync(StoreBase.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override():
        async with factory() as s:
            yield s

    app = create_app(settings=_settings())
    app.dependency_overrides[get_session] = _override
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    try:
        yield client
    finally:
        await client.aclose()
        await engine.dispose()


# ----------------------------------------------------------------- moteur (pur)


def test_pmp_entree_moyenne_ponderee() -> None:
    # 10 @ 100, puis 10 @ 200 → PMP = 150, qté 20
    r1 = appliquer_mouvement(
        type="entree",
        quantite=Decimal("10"),
        quantite_actuelle=Decimal("0"),
        pmp_actuel=Decimal("0"),
        cout_unitaire=Decimal("100"),
    )
    assert r1.nouvelle_quantite == Decimal("10.000")
    assert r1.nouveau_pmp_xaf == Decimal("100.00")
    r2 = appliquer_mouvement(
        type="entree",
        quantite=Decimal("10"),
        quantite_actuelle=Decimal("10"),
        pmp_actuel=Decimal("100"),
        cout_unitaire=Decimal("200"),
    )
    assert r2.nouvelle_quantite == Decimal("20.000")
    assert r2.nouveau_pmp_xaf == Decimal("150.00")


def test_sortie_au_pmp_et_insuffisance() -> None:
    r = appliquer_mouvement(
        type="sortie",
        quantite=Decimal("5"),
        quantite_actuelle=Decimal("20"),
        pmp_actuel=Decimal("150"),
    )
    assert r.nouvelle_quantite == Decimal("15.000")
    assert r.valeur_mouvement_xaf == Decimal("750.00")  # 5 * 150
    assert r.nouveau_pmp_xaf == Decimal("150.00")  # inchangé

    try:
        appliquer_mouvement(
            type="sortie",
            quantite=Decimal("100"),
            quantite_actuelle=Decimal("15"),
            pmp_actuel=Decimal("150"),
        )
        raise AssertionError("attendu StockInsuffisant")
    except StockInsuffisant:
        pass


# ----------------------------------------------------------------- endpoints


async def test_stock_move_validate_updates_item(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        await ac.post(
            "/v1/erp/stock",
            json={"sku": "SKU1", "libelle": "Vis", "quantite_actuelle": "0"},
        )

        # entrée 10 @ 100 (brouillon puis validée)
        mv = (
            await ac.post(
                "/v1/erp/stock-moves",
                json={
                    "reference": "MV-001",
                    "type": "entree",
                    "sku": "SKU1",
                    "quantite": "10",
                    "cout_unitaire_xaf": "100",
                    "date_mouvement": "2026-06-01",
                },
            )
        ).json()
        assert mv["statut"] == "brouillon"
        r = await ac.post(f"/v1/erp/stock-moves/{mv['id']}/validate")
        assert r.status_code == 200, r.text
        art = r.json()["article"]
        assert art["quantite_actuelle"] == "10.000"
        assert art["pmp_xaf"] == "100.00"
        assert art["valeur_stock_xaf"] == "1000.00"

        # double validation → 409
        assert (await ac.post(f"/v1/erp/stock-moves/{mv['id']}/validate")).status_code == 409

        # entrée 10 @ 200 → PMP 150, stock valorisé 3000
        mv2 = (
            await ac.post(
                "/v1/erp/stock-moves",
                json={
                    "reference": "MV-002",
                    "type": "entree",
                    "sku": "SKU1",
                    "quantite": "10",
                    "cout_unitaire_xaf": "200",
                    "date_mouvement": "2026-06-02",
                },
            )
        ).json()
        art2 = (await ac.post(f"/v1/erp/stock-moves/{mv2['id']}/validate")).json()["article"]
        assert art2["pmp_xaf"] == "150.00"
        assert art2["valeur_stock_xaf"] == "3000.00"


async def test_sortie_insuffisante_rejetee(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        await ac.post(
            "/v1/erp/stock",
            json={"sku": "SKU2", "libelle": "Boulon", "quantite_actuelle": "0"},
        )
        mv = (
            await ac.post(
                "/v1/erp/stock-moves",
                json={
                    "reference": "MV-003",
                    "type": "sortie",
                    "sku": "SKU2",
                    "quantite": "5",
                    "date_mouvement": "2026-06-03",
                },
            )
        ).json()
        assert (await ac.post(f"/v1/erp/stock-moves/{mv['id']}/validate")).status_code == 422


async def test_double_validation_au_dela_du_seuil(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        await ac.post(
            "/v1/erp/stock", json={"sku": "SKU3", "libelle": "Moteur", "quantite_actuelle": "0"}
        )
        mv = (
            await ac.post(
                "/v1/erp/stock-moves",
                json={
                    "reference": "MV-100",
                    "type": "entree",
                    "sku": "SKU3",
                    "quantite": "10",
                    "cout_unitaire_xaf": "100",  # valeur 1000 > seuil forcé 100
                    "date_mouvement": "2026-06-01",
                },
            )
        ).json()
        # N1 : au-dessus du seuil → non appliqué, requiert N2
        r1 = await ac.post(f"/v1/erp/stock-moves/{mv['id']}/validate?seuil_xaf=100")
        assert r1.status_code == 200
        assert r1.json()["applique"] is False
        assert r1.json()["requiert_n2"] is True
        assert r1.json()["move"]["statut"] == "valide_n1"
        # stock encore à 0
        items = (await ac.get("/v1/erp/stock")).json()["items"]
        assert items[0]["quantite_actuelle"] == "0.000"
        # N2 : deuxième validation → appliqué
        r2 = await ac.post(f"/v1/erp/stock-moves/{mv['id']}/validate?seuil_xaf=100")
        assert r2.json()["applique"] is True
        assert r2.json()["article"]["quantite_actuelle"] == "10.000"


async def test_inventaire_physique_genere_ajustements(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        await ac.post(
            "/v1/erp/stock", json={"sku": "SKU4", "libelle": "Câble", "quantite_actuelle": "5"}
        )
        body = (
            await ac.post(
                "/v1/erp/stock/inventory",
                json={"comptages": [{"sku": "SKU4", "quantite_comptee": "3"}]},
            )
        ).json()
        assert body["nb_ecarts"] == 1
        ligne = body["resultats"][0]
        assert Decimal(ligne["ecart"]) == Decimal("-2")
        # l'ajustement (brouillon) appliqué aligne le stock théorique sur le compté
        art = (await ac.post(f"/v1/erp/stock-moves/{ligne['ajustement_id']}/validate")).json()[
            "article"
        ]
        assert art["quantite_actuelle"] == "3.000"


async def test_alertes_peremption(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        await ac.post(
            "/v1/erp/stock", json={"sku": "SKU5", "libelle": "Vaccin", "quantite_actuelle": "0"}
        )
        proche = (date.today() + timedelta(days=10)).isoformat()
        mv = (
            await ac.post(
                "/v1/erp/stock-moves",
                json={
                    "reference": "MV-200",
                    "type": "entree",
                    "sku": "SKU5",
                    "quantite": "50",
                    "cout_unitaire_xaf": "100",
                    "lot": "L-2026-A",
                    "date_peremption": proche,
                    "date_mouvement": date.today().isoformat(),
                },
            )
        ).json()
        await ac.post(f"/v1/erp/stock-moves/{mv['id']}/validate")
        alertes = (await ac.get("/v1/erp/stock/peremption?horizon_jours=30")).json()["alertes"]
        assert len(alertes) == 1
        assert alertes[0]["sku"] == "SKU5" and alertes[0]["lot"] == "L-2026-A"
        assert alertes[0]["niveau"] == "proche"


async def test_reception_bc_genere_entree_stock(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        po_id = (
            await ac.post(
                "/v1/erp/purchase-orders",
                json={
                    "id_externe": "BC9",
                    "numero": "BC-009",
                    "fournisseur": "Alpha",
                    "date_emission": "2026-06-01",
                    "statut": "confirme",
                    "montant_ht_xaf": "1000",
                    "montant_ttc_xaf": "1180",
                },
            )
        ).json()["id"]
        r = await ac.post(
            f"/v1/erp/purchase-orders/{po_id}/receipt",
            json={"entrees": [{"sku": "SKU6", "quantite": "10", "cout_unitaire_xaf": "100"}]},
        )
        assert r.status_code == 200, r.text
        entrees = r.json()["entrees_stock"]
        assert len(entrees) == 1
        assert entrees[0]["type"] == "entree" and entrees[0]["statut"] == "brouillon"
        # le mouvement est bien dans le grand-livre
        moves = (await ac.get("/v1/erp/stock-moves?sku=SKU6")).json()["moves"]
        assert len(moves) == 1


# ----------------------------------------------------------------- pilotage (STOCK-4)


def test_pilotage_stock_abc_rupture_dormant() -> None:
    arts = [
        ArticleStock(
            sku="A",
            quantite_actuelle=Decimal("10"),
            conso_moyenne_jour=Decimal("2"),
            pmp_xaf=Decimal("1000"),
            stock_securite=Decimal("5"),
        ),
        ArticleStock(  # rupture
            sku="B",
            quantite_actuelle=Decimal("0"),
            conso_moyenne_jour=Decimal("1"),
            pmp_xaf=Decimal("100"),
            stock_securite=Decimal("2"),
        ),
        ArticleStock(  # dormant (conso 0, stock > 0)
            sku="C",
            quantite_actuelle=Decimal("5"),
            conso_moyenne_jour=Decimal("0"),
            pmp_xaf=Decimal("50"),
            stock_securite=Decimal("0"),
        ),
    ]
    p = pilotage_stock(arts)
    assert p.nb_articles == 3
    assert p.nb_rupture == 1
    assert p.dormant_nb == 1
    assert p.valorisation_totale_xaf == Decimal("10250.00")  # 10000 + 0 + 250
    a = next(x for x in p.par_article if x.sku == "A")
    assert a.classe_abc == "A"
    assert a.couverture_jours == Decimal("5.0")  # 10 / 2
    assert a.rotation_annuelle == Decimal("73.00")  # 2 * 365 / 10


async def test_stock_pilotage_endpoint_and_export(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        await ac.post(
            "/v1/erp/stock",
            json={
                "sku": "P1",
                "libelle": "Pièce A",
                "quantite_actuelle": "10",
                "conso_moyenne_jour": "2",
            },
        )
        # PMP via une entrée validée
        mv = (
            await ac.post(
                "/v1/erp/stock-moves",
                json={
                    "reference": "MV-P1",
                    "type": "entree",
                    "sku": "P1",
                    "quantite": "0",
                    "cout_unitaire_xaf": "1000",
                    "date_mouvement": "2026-06-01",
                },
            )
        ).json()
        await ac.post(f"/v1/erp/stock-moves/{mv['id']}/validate")

        body = (await ac.get("/v1/erp/stock/pilotage")).json()["pilotage"]
        assert body["nb_articles"] == 1
        assert (
            body["repartition_abc"]["A"]
            + body["repartition_abc"]["B"]
            + body["repartition_abc"]["C"]
            == 1
        )

        r = await ac.get("/v1/erp/stock/pilotage/export")
        assert r.status_code == 200
        assert "spreadsheetml" in r.headers["content-type"]
        wb = openpyxl.load_workbook(BytesIO(r.content))
        assert {"Synthèse", "Par article"} <= set(wb.sheetnames)
