"""Connector Framework générique ZolaOS (V2.2 §2.4).

Couche d'abstraction unique pour brancher ZolaOS à des systèmes externes.
API publique : modèles canoniques, interface connecteur, auth, mapping.
"""

from __future__ import annotations

from zolaos.connectors.auth import (
    ApiKeyAuth,
    AuthStrategy,
    BasicAuth,
    CertificateAuth,
    IPAllowlist,
    NoAuth,
    OAuth2Auth,
)
from zolaos.connectors.base import (
    AccountingConnector,
    BaseConnector,
    Capability,
    CapabilityNotSupported,
    ConnectorAuthError,
    ConnectorConfigError,
    ConnectorConnectionError,
    ConnectorError,
    FinanceConnector,
    HRConnector,
    InvoiceConnector,
    JournalConnector,
)
from zolaos.connectors.mapping import FieldMapping, FieldRule, MappingError
from zolaos.connectors.models import (
    BankTransaction,
    Employee,
    Invoice,
    JournalEntry,
    JournalLine,
)

__all__ = [
    # base / capacités
    "BaseConnector",
    "HRConnector",
    "InvoiceConnector",
    "JournalConnector",
    "AccountingConnector",
    "FinanceConnector",
    "Capability",
    # erreurs
    "ConnectorError",
    "ConnectorConfigError",
    "ConnectorAuthError",
    "ConnectorConnectionError",
    "CapabilityNotSupported",
    # auth
    "AuthStrategy",
    "NoAuth",
    "ApiKeyAuth",
    "BasicAuth",
    "OAuth2Auth",
    "CertificateAuth",
    "IPAllowlist",
    # mapping
    "FieldMapping",
    "FieldRule",
    "MappingError",
    # modèles
    "Employee",
    "Invoice",
    "JournalEntry",
    "JournalLine",
    "BankTransaction",
]
